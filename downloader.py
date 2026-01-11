import os
import uuid
import subprocess
import json
import logging
import urllib.request
import socket
from pathlib import Path
from typing import Dict, List
from contextlib import contextmanager
from urllib.parse import urlparse
import ipaddress

# ---------------- CONFIG ----------------

DOWNLOAD_DIR = Path("/app/downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Telegram FREE limits
MAX_VIDEO_SIZE = 49 * 1024 * 1024      # ~49 MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024      # 10 MB per image
MAX_IMAGES = 10

NETWORK_TIMEOUT = 15
ALLOWED_SCHEMES = {"http", "https"}

logger = logging.getLogger(__name__)

# ---------------- ERRORS ----------------

class MediaDownloadError(Exception):
    """Base error for media downloading"""
    pass

# ---------------- HELPERS ----------------

@contextmanager
def temporary_timeout(seconds: int):
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(seconds)
    try:
        yield
    finally:
        socket.setdefaulttimeout(old)

def _validate_url(url: str):
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise MediaDownloadError("Unsupported URL scheme")

    if parsed.hostname:
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise MediaDownloadError("Private network access blocked")
        except ValueError:
            pass  # hostname, not IP

def _cleanup(paths: List[Path]):
    for p in paths:
        try:
            if p.exists():
                p.unlink()
        except Exception:
            logger.warning("Failed to cleanup %s", p)

def _run_json(url: str) -> dict:
    try:
        result = subprocess.run(
            ["yt-dlp", "-J", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=NETWORK_TIMEOUT,
            check=False,
        )

        if result.returncode != 0:
            raise MediaDownloadError(result.stderr[:200])

        return json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        raise MediaDownloadError("yt-dlp timed out")
    except json.JSONDecodeError:
        raise MediaDownloadError("Invalid JSON from yt-dlp")

def _download_image(url: str, path: Path):
    _validate_url(url)

    with temporary_timeout(NETWORK_TIMEOUT):
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (SaveAsBot Free)"}
        )

        with urllib.request.urlopen(req) as r:
            size = r.headers.get("Content-Length")
            if size and int(size) > MAX_IMAGE_SIZE:
                raise MediaDownloadError("Image too large")

            ctype = r.headers.get("Content-Type", "")
            if not ctype.startswith("image/"):
                raise MediaDownloadError("Invalid image type")

            data = r.read(MAX_IMAGE_SIZE + 1)
            if len(data) > MAX_IMAGE_SIZE:
                raise MediaDownloadError("Image exceeds size limit")

            path.write_bytes(data)

    if not path.exists() or path.stat().st_size == 0:
        raise MediaDownloadError("Image download failed")

# ---------------- MAIN ----------------

def download_media(url: str) -> Dict:
    _validate_url(url)

    downloaded: List[Path] = []

    try:
        data = _run_json(url)
        media_id = str(uuid.uuid4())

        # ---------- VIDEO ----------
        if data.get("duration") and data.get("formats"):
            video_path = DOWNLOAD_DIR / f"{media_id}.mp4"
            downloaded.append(video_path)

            subprocess.run(
                [
                    "yt-dlp",
                    url,
                    "-f", "bv*+ba/b",
                    "--merge-output-format", "mp4",
                    "--remux-video", "mp4",
                    "--postprocessor-args", "ffmpeg:-movflags +faststart",
                    "--max-filesize", str(MAX_VIDEO_SIZE),
                    "-o", str(video_path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=300,
                check=False,
            )

            if not video_path.exists() or video_path.stat().st_size == 0:
                raise MediaDownloadError("Video not created")

            if video_path.stat().st_size > MAX_VIDEO_SIZE:
                raise MediaDownloadError("Video exceeds Telegram limit")

            return {
                "type": "video",
                "path": str(video_path),
            }

        # ---------- PHOTO CAROUSEL ----------
        image_paths: List[Path] = []

        entries = data.get("entries")
        if isinstance(entries, list):
            for i, entry in enumerate(entries[:MAX_IMAGES], start=1):
                thumbs = entry.get("thumbnails") or []
                if not thumbs:
                    continue

                img_url = thumbs[-1].get("url")
                if not img_url:
                    continue

                img_path = DOWNLOAD_DIR / f"{media_id}_{i}.jpg"
                downloaded.append(img_path)

                try:
                    _download_image(img_url, img_path)
                    image_paths.append(img_path)
                except MediaDownloadError as e:
                    logger.warning("Image %d skipped: %s", i, e)

        # ---------- SINGLE IMAGE FALLBACK ----------
        if not image_paths:
            thumbs = data.get("thumbnails") or []
            if thumbs:
                img_url = thumbs[-1].get("url")
                img_path = DOWNLOAD_DIR / f"{media_id}_1.jpg"
                downloaded.append(img_path)
                _download_image(img_url, img_path)
                image_paths.append(img_path)

        if not image_paths:
            raise MediaDownloadError("No downloadable media found")

        return {
            "type": "images",
            "paths": [str(p) for p in image_paths],
        }

    except MediaDownloadError:
        _cleanup(downloaded)
        raise
    except Exception as e:
        _cleanup(downloaded)
        raise MediaDownloadError(str(e)) from e