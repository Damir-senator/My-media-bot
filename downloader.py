import os
import uuid
import subprocess
import json
import logging
import urllib.request
import socket

DOWNLOAD_DIR = "/app/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

# таймауты для сетевых операций
socket.setdefaulttimeout(15)

def _run_json(url: str) -> dict:
    """Получаем JSON от yt-dlp"""
    result = subprocess.run(
        ["yt-dlp", "-J", url],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)

def _download_image(url: str, path: str):
    urllib.request.urlretrieve(url, path)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise RuntimeError("Image download failed")

def download_media(url: str) -> dict:
    data = _run_json(url)
    media_id = str(uuid.uuid4())

    # ---------- VIDEO ----------
    if data.get("formats"):
        video_path = os.path.join(DOWNLOAD_DIR, f"{media_id}.mp4")

        subprocess.run(
            [
                "yt-dlp",
                url,
                "-f", "bv*+ba/b",
                "--merge-output-format", "mp4",
                "--remux-video", "mp4",
                "--postprocessor-args", "ffmpeg:-movflags +faststart",
                "-o", video_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
            raise RuntimeError("Video file not created")

        return {
            "type": "video",
            "path": video_path,
        }

    image_paths = []

    # ---------- PHOTO CAROUSEL ----------
    entries = data.get("entries")
    if isinstance(entries, list):
        for i, entry in enumerate(entries, start=1):
            thumbs = entry.get("thumbnails") or []
            if not thumbs:
                continue

            img_url = thumbs[-1].get("url")
            if not img_url:
                continue

            img_path = os.path.join(DOWNLOAD_DIR, f"{media_id}_{i}.jpg")
            _download_image(img_url, img_path)
            image_paths.append(img_path)

    # ---------- SINGLE IMAGE FALLBACK ----------
    if not image_paths:
        thumbs = data.get("thumbnails") or []
        if thumbs:
            img_url = thumbs[-1].get("url")
            if img_url:
                img_path = os.path.join(DOWNLOAD_DIR, f"{media_id}_1.jpg")
                _download_image(img_url, img_path)
                image_paths.append(img_path)

    if not image_paths:
        raise RuntimeError("No downloadable media found")

    logger.info("Downloaded %d images", len(image_paths))

    return {
        "type": "images",
        "paths": image_paths,
    }