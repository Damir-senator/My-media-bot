import requests
import subprocess
import json
import uuid
import time
import logging
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

DOWNLOAD_DIR = Path("/app/downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_IMAGES = 10
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
REQUEST_TIMEOUT = 15
SUBPROCESS_TIMEOUT = 120

logger = logging.getLogger(__name__)


class MediaDownloadError(Exception):
    pass


def _expand_url(url: str) -> str:
    try:
        r = requests.get(
            url,
            allow_redirects=True,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        return r.url
    except Exception:
        return url


def _get_json(url: str) -> dict:
    result = subprocess.run(
        ["yt-dlp", "-J", url, "--user-agent", "Mozilla/5.0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )

    if result.returncode != 0:
        raise MediaDownloadError(result.stderr[:300])

    return json.loads(result.stdout)


def _download_image(url: str, path: Path) -> bool:
    try:
        r = requests.get(
            url,
            stream=True,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        r.raise_for_status()

        size = 0
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                size += len(chunk)
                if size > MAX_IMAGE_SIZE:
                    return False
                f.write(chunk)

        return path.exists() and path.stat().st_size > 0
    except Exception:
        return False


def download_media(url: str) -> Dict:
    expanded = _expand_url(url)
    data = _get_json(expanded)
    media_id = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"

    # ---------- VIDEO ----------
    if data.get("duration"):
        video_path = DOWNLOAD_DIR / f"{media_id}.mp4"

        subprocess.run(
            [
                "yt-dlp",
                expanded,
                "-f", "bv*+ba/b",
                "--merge-output-format", "mp4",
                "--remux-video", "mp4",
                "--postprocessor-args", "ffmpeg:-movflags +faststart",
                "--max-filesize", str(MAX_VIDEO_SIZE),
                "--user-agent", "Mozilla/5.0",
                "-o", str(video_path),
            ],
            timeout=SUBPROCESS_TIMEOUT,
        )

        if not video_path.exists():
            raise MediaDownloadError("Video not created")

        return {"type": "video", "path": str(video_path)}

    # ---------- PHOTO POSTS ----------
    images = []

    image_blocks = (
        data.get("image_post_info", {}).get("images")
        or data.get("aweme_detail", {})
            .get("image_post_info", {})
            .get("images")
    )

    if not image_blocks:
        raise MediaDownloadError("No images found")

    for i, img in enumerate(image_blocks[:MAX_IMAGES], start=1):
        urls = img.get("display_image", {}).get("url_list")
        if not urls:
            continue

        img_path = DOWNLOAD_DIR / f"{media_id}_{i}.jpg"
        if _download_image(urls[-1], img_path):
            images.append(str(img_path))

    if not images:
        raise MediaDownloadError("Images download failed")

    return {"type": "images", "paths": images}