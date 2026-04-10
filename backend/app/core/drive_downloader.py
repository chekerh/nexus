"""Google Drive video downloader for Nexus-UGC."""
import re
import os
import uuid
import requests
from typing import Optional
from urllib.parse import urlparse, parse_qs


def extract_drive_file_id(url: str) -> Optional[str]:
    """Extract Google Drive file ID from various URL formats."""
    # Pattern 1: https://drive.google.com/file/d/{FILE_ID}/view
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    
    # Pattern 2: https://drive.google.com/open?id={FILE_ID}
    parsed = urlparse(url)
    if parsed.hostname and 'drive.google.com' in parsed.hostname:
        query = parse_qs(parsed.query)
        if 'id' in query:
            return query['id'][0]
    
    # Pattern 3: https://drive.google.com/uc?id={FILE_ID}
    match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    
    return None


def download_drive_file(url: str, output_dir: str, progress_callback=None) -> Optional[str]:
    """Download a file from Google Drive URL.
    
    Args:
        url: Google Drive share URL or direct link
        output_dir: Directory to save the downloaded file
        progress_callback: Optional callback function(message) for progress updates
        
    Returns:
        Path to the downloaded file, or None if download failed
    """
    file_id = extract_drive_file_id(url)
    if not file_id:
        return None
    
    if progress_callback:
        progress_callback(f"Drive: Extracted file ID {file_id[:8]}...")
    
    # Direct download URL
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    session = requests.Session()
    
    if progress_callback:
        progress_callback("Drive: Initiating download...")
    
    response = session.get(download_url, stream=True)
    
    # Check for confirmation page (large files trigger this)
    if response.headers.get('content-type', '').startswith('text/html'):
        # Need to confirm download for large files
        for key, value in response.cookies.items():
            if key.startswith('download_warning'):
                confirm_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={value}"
                if progress_callback:
                    progress_callback("Drive: Confirming large file download...")
                response = session.get(confirm_url, stream=True)
                break
    
    # Get filename from Content-Disposition header or use default
    filename = None
    if 'Content-Disposition' in response.headers:
        disposition = response.headers['Content-Disposition']
        match = re.search(r'filename="?([^"]+)"?', disposition)
        if match:
            filename = match.group(1)
    
    if not filename:
        filename = f"drive_video_{file_id}.mp4"
    
    # Ensure safe filename
    filename = re.sub(r'[^\w\-\.]', '_', filename)
    if not filename.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
        filename += '.mp4'
    
    output_path = os.path.join(output_dir, f"{uuid.uuid4()}_{filename}")
    
    # Download with progress
    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0
    chunk_size = 8192
    
    if progress_callback:
        progress_callback(f"Drive: Downloading {total_size / 1024 / 1024:.1f} MB...")
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and progress_callback and downloaded % (chunk_size * 100) == 0:
                    pct = (downloaded / total_size) * 100
                    progress_callback(f"Drive: Downloaded {pct:.1f}%...")
    
    if progress_callback:
        progress_callback(f"Drive: Download complete ({downloaded / 1024 / 1024:.1f} MB)")
    
    return output_path
