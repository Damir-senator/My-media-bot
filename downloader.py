import os
import yt_dlp
import logging
import uuid
from urllib.parse import urlparse, urlunparse

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def clean_url(url):
    """Removes query parameters from the URL to avoid issues with tracking IDs."""
    try:
        parsed = urlparse(url)
        # Reconstruct URL without query parameters
        cleaned = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        return cleaned
    except Exception:
        return url

def download_media(url, output_dir="downloads"):
    """
    Downloads video/photo from the given URL using yt-dlp.
    Optimized for TikTok and YouTube Shorts.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    cleaned_url = clean_url(url)
    logger.info(f"Processing URL: {cleaned_url}")

    # Generate unique filename to prevent collisions
    unique_filename = str(uuid.uuid4())
    
    # Standard stable options for TikTok/YouTube
    ydl_opts = {
        'outtmpl': f'{output_dir}/{unique_filename}.%(ext)s',
        'format': 'bestvideo+bestaudio/best',  # Best quality
        'merge_output_format': 'mp4',          # Ensure mp4 output
        'noplaylist': True,                    # Single video only
        'quiet': True,                         # Less noise in logs
        'no_warnings': True,
        'geo_bypass': True,                    # Bypass geo-restrictions
        
        # Use iPhone User-Agent (Most stable for TikTok)
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(cleaned_url, download=True)
            
            if 'requested_downloads' in info_dict:
                filename = info_dict['requested_downloads'][0]['filepath']
            else:
                filename = ydl.prepare_filename(info_dict)
                
            logger.info(f"Download success: {filename}")
            return filename
            
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return None
