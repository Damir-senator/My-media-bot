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

    # Configure yt-dlp options with improved anti-blocking
    ydl_opts = {
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'format': 'bestvideo+bestaudio/best',  # Best quality
        'merge_output_format': 'mp4',          # Ensure mp4 output for videos
        'noplaylist': True,                    # Download only single video
        'quiet': True,                         # Less verbose output
        'no_warnings': True,
        
        # --- IMPROVED ANTI-BLOCKING SETTINGS ---
        # Use a generic Android User-Agent which is often less restricted than iPhone
        'user_agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
        
        # Add Referer header to mimic coming from the site itself
        'http_headers': {
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.instagram.com/',
            'Sec-Fetch-Mode': 'navigate',
        },
        
        # Force IPv4 (sometimes IPv6 addresses are blocked more often)
        'source_address': '0.0.0.0',
        
        # Geo-bypass (sometimes helps)
        'geo_bypass': True,
        
        # Add delay to avoid hitting rate limits too fast (optional, but safer)
        'sleep_interval': 1,
        'max_sleep_interval': 3,
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
