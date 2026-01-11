import os
import uuid
import subprocess
import glob
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional
from contextlib import contextmanager
from dataclasses import dataclass

DOWNLOAD_DIR = Path("/app/downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

# Limits (Free tier)
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_IMAGES = 10
DOWNLOAD_TIMEOUT = 120
MIN_VIDEO_SIZE = 1024  # 1 KB minimum
MIN_IMAGE_SIZE = 512   # 512 bytes minimum
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
CLEANUP_AGE_SECONDS = 3600  # Remove files older than 1 hour


@dataclass
class MediaLimits:
    max_video_size: int = MAX_VIDEO_SIZE
    max_images: int = MAX_IMAGES
    timeout: int = DOWNLOAD_TIMEOUT


class MediaDownloadError(Exception):
    """Base exception for media download errors"""
    pass


class VideoValidationError(MediaDownloadError):
    """Video validation failed"""
    pass


class NoMediaFoundError(MediaDownloadError):
    """No downloadable media found"""
    pass


@contextmanager
def cleanup_on_error(paths: List[Path]):
    """Clean up files only if exception occurs"""
    try:
        yield
    except Exception as e:
        logger.error(f"Error during download, cleaning up {len(paths)} files: {e}")
        for p in paths:
            try:
                if p.exists():
                    p.unlink()
                    logger.debug(f"Deleted: {p}")
            except Exception as cleanup_err:
                logger.warning(f"Failed to delete {p}: {cleanup_err}")
        raise


def cleanup_old_files(max_age_seconds: int = CLEANUP_AGE_SECONDS) -> int:
    """Remove old files from download directory"""
    current_time = time.time()
    removed = 0
    
    for file_path in DOWNLOAD_DIR.glob("*"):
        try:
            if file_path.is_file() and (current_time - file_path.stat().st_mtime) > max_age_seconds:
                file_path.unlink()
                removed += 1
                logger.debug(f"Cleaned up old file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up {file_path}: {e}")
    
    if removed > 0:
        logger.info(f"Cleaned up {removed} old files")
    
    return removed


def _run(cmd: List[str], timeout: int = DOWNLOAD_TIMEOUT) -> subprocess.CompletedProcess:
    """Run subprocess with timeout and error handling"""
    try:
        logger.debug(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        
        if result.returncode != 0:
            logger.warning(f"Command failed with code {result.returncode}: {result.stderr[:200]}")
        
        return result
        
    except subprocess.TimeoutExpired as e:
        logger.error(f"Command timeout after {timeout}s")
        raise MediaDownloadError(f"Download timeout after {timeout} seconds")
    except FileNotFoundError:
        logger.error("yt-dlp executable not found")
        raise MediaDownloadError("yt-dlp not installed or not in PATH")


def _validate_video(path: Path) -> bool:
    """Validate video file size and integrity"""
    if not path.exists():
        logger.warning(f"Video file doesn't exist: {path}")
        return False

    size = path.stat().st_size
    
    if size < MIN_VIDEO_SIZE:
        logger.warning(f"Video too small: {size} bytes")
        return False
    
    if size > MAX_VIDEO_SIZE:
        logger.warning(f"Video exceeds limit: {size} > {MAX_VIDEO_SIZE} bytes")
        return False

    # Verify it's a valid video with ffprobe
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_type",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path)
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            text=True,
        )
        
        is_valid = probe.returncode == 0 and "video" in probe.stdout.lower()
        
        if not is_valid:
            logger.warning(f"ffprobe validation failed for {path}")
        
        return is_valid
        
    except subprocess.TimeoutExpired:
        logger.warning(f"ffprobe timeout for {path}")
        return False
    except FileNotFoundError:
        logger.warning("ffprobe not found, skipping validation")
        return True  # Fallback if ffprobe not available
    except Exception as e:
        logger.warning(f"ffprobe error: {e}")
        return True  # Fallback


def _try_video(url: str, media_id: str) -> Optional[Path]:
    """Attempt to download video"""
    video_path = DOWNLOAD_DIR / f"{media_id}.mp4"
    
    logger.info(f"Attempting video download: {url}")

    cmd = [
        "yt-dlp",
        url,
        "-f", "bv*[filesize<?50M]+ba/b[filesize<?50M]/best[filesize<?50M]",
        "--merge-output-format", "mp4",
        "--remux-video", "mp4",
        "--max-filesize", str(MAX_VIDEO_SIZE),
        "--no-playlist",
        "--no-warnings",
        "--quiet",
        "-o", str(video_path),
    ]

    result = _run(cmd)

    if result.returncode != 0:
        logger.info("Video download failed or not available")
        if video_path.exists():
            video_path.unlink()
        return None

    if not video_path.exists():
        logger.warning("yt-dlp succeeded but file not found")
        return None

    if _validate_video(video_path):
        logger.info(f"Video downloaded successfully: {video_path.stat().st_size} bytes")
        return video_path

    logger.warning("Video validation failed, removing file")
    if video_path.exists():
        video_path.unlink()

    return None


def _validate_image(path: Path) -> bool:
    """Validate image file"""
    if not path.exists():
        return False
    
    if path.stat().st_size < MIN_IMAGE_SIZE:
        logger.debug(f"Image too small: {path}")
        return False
    
    if path.suffix.lower() not in SUPPORTED_IMAGE_EXTS:
        logger.debug(f"Unsupported extension: {path}")
        return False
    
    return True


def _try_images(url: str, media_id: str) -> List[Path]:
    """Attempt to download thumbnails/images"""
    template = str(DOWNLOAD_DIR / f"{media_id}_%(autonumber)s.%(ext)s")
    
    logger.info(f"Attempting image download: {url}")

    cmd = [
        "yt-dlp",
        url,
        "--skip-download",
        "--write-thumbnail",
        "--convert-thumbnails", "jpg",
        "--no-playlist",
        "--no-warnings",
        "--quiet",
        "-o", template,
    ]

    result = _run(cmd)
    
    if result.returncode != 0:
        logger.info("Image download failed")

    # Collect valid images
    pattern = str(DOWNLOAD_DIR / f"{media_id}_*")
    files = []
    
    for path_str in glob.glob(pattern):
        path = Path(path_str)
        if _validate_image(path):
            files.append(path)
        else:
            # Remove invalid files
            try:
                path.unlink()
            except Exception:
                pass

    files.sort()
    result_files = files[:MAX_IMAGES]
    
    # Remove excess files
    for excess in files[MAX_IMAGES:]:
        try:
            excess.unlink()
        except Exception:
            pass
    
    logger.info(f"Downloaded {len(result_files)} valid images")
    
    return result_files


def download_media(url: str, limits: Optional[MediaLimits] = None) -> Dict:
    """
    Download media from URL
    
    Args:
        url: URL to download from
        limits: Optional custom limits
        
    Returns:
        Dict with 'type' and 'path'/'paths'
        
    Raises:
        MediaDownloadError: If download fails
        NoMediaFoundError: If no media found
    """
    if limits is None:
        limits = MediaLimits()
    
    # Clean up old files first
    cleanup_old_files()
    
    media_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    collected: List[Path] = []

    logger.info(f"Starting download for URL: {url[:100]}")

    with cleanup_on_error(collected):
        # Try video first
        video = _try_video(url, media_id)
        if video:
            collected.append(video)
            logger.info(f"Successfully downloaded video: {video}")
            return {
                "type": "video",
                "path": str(video),
                "size": video.stat().st_size
            }

        # Fall back to images
        images = _try_images(url, media_id)
        if images:
            collected.extend(images)
            logger.info(f"Successfully downloaded {len(images)} images")
            return {
                "type": "images",
                "paths": [str(p) for p in images],
                "count": len(images)
            }

        logger.error("No downloadable media found")
        raise NoMediaFoundError(f"No downloadable media found for URL: {url[:100]}")


# Optional: Add convenience function
def download_media_safe(url: str) -> Optional[Dict]:
    """Safe wrapper that returns None instead of raising"""
    try:
        return download_media(url)
    except MediaDownloadError as e:
        logger.error(f"Download failed: {e}")
        return None
