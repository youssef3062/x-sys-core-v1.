import os
import requests
import logging
from flask import request, flash

# Logging
logger = logging.getLogger("brescan-frontend")

def api_url(path: str) -> str:
    """Build full API URL for a given path."""
    if path.startswith("http"):
        return path
    if not path.startswith("/"):
        path = "/" + path
    
    # improved dynamic base url resolution
    api_base = os.environ.get("BRESCAN_API_BASE")
    if not api_base:
        # Fallback to current request host to ensure we hit the same server instance
        try:
            api_base = request.host_url.rstrip('/')
        except Exception:
             api_base = "http://127.0.0.1:5000"
             
    return f"{api_base}{path}"

def handle_api_response(response, success_message=None):
    """Handle API responses consistently."""
    if response is None:
        return False, "Backend API unreachable. Please ensure api.py is running."
    
    try:
        data = response.json()
        if response.status_code == 200:
            if success_message:
                flash(success_message, "success")
            return True, data
        else:
            error_msg = data.get("error", f"API error: {response.status_code}")
            return False, error_msg
    except Exception as e:
        # Log the actual response for debugging
        logger.error(f"API response parsing failed: {e}. Status: {response.status_code}, URL: {response.url}, Content-Type: {response.headers.get('Content-Type')}")
        
        # If HTML is returned (e.g. 404/500), provide a hint
        msg = f"Unexpected API response (Status {response.status_code})"
        if "text/html" in response.headers.get("Content-Type", ""):
             msg += ". The server returned HTML instead of JSON (likely 404 Not Found or 500 Error)."
        
        return False, msg

def safe_get(path: str, params: dict = None, timeout: int = 10):
    try:
        url = api_url(path)
        logger.info(f"API GET: {url}")
        r = requests.get(url, params=params or {}, timeout=timeout)
        return r
    except Exception as e:
        logger.error(f"API GET failed: {e}")
        return None

def safe_post(path: str, json: dict = None, data: dict = None, files: dict = None, timeout: int = 30):
    try:
        url = api_url(path)
        logger.info(f"API POST: {url}")
        r = requests.post(url, json=json, data=data, files=files, timeout=timeout)
        return r
    except Exception as e:
        logger.error(f"API POST failed: {e}")
        return None
