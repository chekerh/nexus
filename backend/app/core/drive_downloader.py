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
    
    # Use the newer Google Drive API download URL
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    if progress_callback:
        progress_callback("Drive: Requesting file...")
    
    # First request to get cookies and check for confirmation
    response = session.get(download_url, stream=True, allow_redirects=True)
    
    # Check for virus scan warning or large file confirmation
    content_type = response.headers.get('content-type', '')
    
    # Google Drive returns HTML page for virus scan warnings
    if 'text/html' in content_type or response.headers.get('content-length') == '0':
        # Read first chunk to check if it's HTML warning
        first_chunk = next(response.iter_content(2048), b'')
        
        if b'confirm' in first_chunk or b'virus' in first_chunk or b'download_warning' in first_chunk:
            if progress_callback:
                progress_callback("Drive: Confirming download (virus scan warning)...")
            
            # Get confirm token from cookies
            confirm_token = None
            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    confirm_token = value
                    break
            
            # If no cookie, try to extract from HTML
            if not confirm_token:
                match = re.search(r'confirm=([a-zA-Z0-9_\-]+)', first_chunk.decode('utf-8', errors='ignore'))
                if match:
                    confirm_token = match.group(1)
            
            if confirm_token:
                confirm_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={confirm_token}"
                response = session.get(confirm_url, stream=True, allow_redirects=True)
            else:
                # Try alternative approach - get confirm from form
                confirm_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
                response = session.get(confirm_url, stream=True, allow_redirects=True)
    
    # Check if we got actual file data
    content_type = response.headers.get('content-type', '')
    total_size = int(response.headers.get('content-length', 0))
    
    if total_size == 0 and 'text/html' in content_type:
        if progress_callback:
            progress_callback("Drive: ERROR - Could not download file. File may be too large or require permissions.")
        return None
    
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
    
    # Verify downloaded file is not empty
    if downloaded == 0:
        if progress_callback:
            progress_callback("Drive: ERROR - Downloaded file is empty")
        if os.path.exists(output_path):
            os.remove(output_path)
        return None
    
    return output_path
