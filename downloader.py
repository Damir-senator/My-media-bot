import uuid
import os
import subprocess
import logging

DOWNLOAD_DIR = "/app/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

def download_media(url: str) -> str:
    filename = f"{uuid.uuid4()}.mp4"
    output_path = os.path.join(DOWNLOAD_DIR, filename)

    command = [
        "yt-dlp",
        url,

        # 🎯 выбираем только mp4 + h264 если есть
        "-f", "bv*[vcodec^=avc1]/bv*+ba/b",

        # 🎥 контейнер mp4
        "--merge-output-format", "mp4",

        # ⚡ moov atom в начале файла (Telegram)
        "--postprocessor-args", "ffmpeg:-movflags +faststart",

        # 🧠 безопасное имя
        "-o", output_path,
    ]

    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,  # ❗ важно
        )
    except subprocess.CalledProcessError as e:
        logger.error("yt-dlp failed: %s", e.stderr.decode(errors="ignore"))
        raise

    return output_path