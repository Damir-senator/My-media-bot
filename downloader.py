import os
import uuid
import subprocess
import logging

DOWNLOAD_DIR = "/app/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

def download_media(url: str) -> str:
    video_id = str(uuid.uuid4())
    output_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")

    command = [
        "yt-dlp",
        url,
        "-f", "mp4/best",
        "--merge-output-format", "mp4",
        "--remux-video", "mp4",
        "--no-playlist",
        "-o", output_path,
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp error: {result.stderr.decode()}")

    if not os.path.exists(output_path):
        raise RuntimeError("MP4 file not created")

    size = os.path.getsize(output_path)
    if size < 100_000:  # <100 KB = мусор
        raise RuntimeError("Downloaded file is too small")

    logger.info("Downloaded video: %s (%d bytes)", output_path, size)

    return output_path