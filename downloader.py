import os
import uuid
import subprocess
import logging
import json
import glob

DOWNLOAD_DIR = "/app/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

def download_media(url: str) -> dict:
    media_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{media_id}_%(id)s.%(ext)s")
    info_path = os.path.join(DOWNLOAD_DIR, f"{media_id}.info.json")

    # 1️⃣ Получаем метаданные
    subprocess.run(
        [
            "yt-dlp",
            url,
            "--skip-download",
            "--write-info-json",
            "--no-playlist",
            "-o", output_template,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not os.path.exists(info_path):
        raise RuntimeError("Failed to fetch media info")

    with open(info_path, "r", encoding="utf-8") as f:
        info = json.load(f)

    # 2️⃣ ЕСЛИ ЭТО ВИДЕО (реальная проверка)
    formats = info.get("formats", [])
    has_video = any(
        f.get("vcodec") not in (None, "none")
        for f in formats
    )

    if has_video:
        video_path = os.path.join(DOWNLOAD_DIR, f"{media_id}.mp4")

        subprocess.run(
            [
                "yt-dlp",
                url,
                "-f", "mp4/best",
                "--merge-output-format", "mp4",
                "--remux-video", "mp4",
                "--no-playlist",
                "-o", video_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        if not os.path.exists(video_path):
            raise RuntimeError("Video file not created")

        return {
            "type": "video",
            "path": video_path,
        }

    # 3️⃣ ЕСЛИ ЭТО PHOTO POST (CAROUSEL)
    subprocess.run(
        [
            "yt-dlp",
            url,
            "--write-all-thumbnails",
            "--skip-download",
            "--no-playlist",
            "-o", output_template,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    images = sorted(
        glob.glob(os.path.join(DOWNLOAD_DIR, f"{media_id}_*.jpg")) +
        glob.glob(os.path.join(DOWNLOAD_DIR, f"{media_id}_*.png")) +
        glob.glob(os.path.join(DOWNLOAD_DIR, f"{media_id}_*.webp"))
    )

    if not images:
        raise RuntimeError("No images found in photo post")

    return {
        "type": "images",
        "paths": images,
    }