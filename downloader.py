import os
import yt_dlp
import logging
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
    Returns the path to the downloaded file or None if failed.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Clean the URL first
    cleaned_url = clean_url(url)
    logger.info(f"Original URL: {url}")
    logger.info(f"Cleaned URL: {cleaned_url}")

    # Configure yt-dlp options with User-Agent spoofing
    ydl_opts = {
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'format': 'bestvideo+bestaudio/best',  # Best quality
        'merge_output_format': 'mp4',          # Ensure mp4 output for videos
        'noplaylist': True,                    # Download only single video
        'quiet': True,                         # Less verbose output
        'no_warnings': True,
        # Spoof User-Agent to look like an iPhone to avoid blocking
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'http_headers': {
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Downloading from: {cleaned_url}")
            info_dict = ydl.extract_info(cleaned_url, download=True)
            
            # Get the filename of the downloaded file
            if 'requested_downloads' in info_dict:
                filename = info_dict['requested_downloads'][0]['filepath']
            else:
                filename = ydl.prepare_filename(info_dict)
            
            logger.info(f"Download complete: {filename}")
            return filename
            
    except Exception as e:
        logger.error(f"Error downloading media: {e}")
        return None

if __name__ == "__main__":
    # Test with a sample URL
    test_url = "https://www.instagram.com/reel/DTSqMr-ErQz/?igsh=MTY1NGVzem1vNW10NQ==" 
    print(f"Testing download from: {test_url}")
    # result = download_media(test_url)
    # print(f"Result: {result}")
