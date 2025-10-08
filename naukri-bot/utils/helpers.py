"""
Helper Functions - Common utilities
"""

import time
import random
import logging
import re

logger = logging.getLogger(__name__)


def smart_delay(min_delay=0.5, max_delay=1.0):
    """Human-like random delay"""
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)


def human_type(element, text, typing_delay=0.05):
    """Type text with human-like delays"""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(typing_delay * 0.5, typing_delay * 1.5))


def extract_job_id(url):
    """Extract job ID from URL"""
    try:
        match = re.search(r'jobId[=\-](\d+)', url)
        if match:
            return match.group(1)
        
        # Alternative patterns
        match = re.search(r'/job-listings-([^/?]+)', url)
        if match:
            return match.group(1)
        
        # Last resort: hash the URL
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:16]
        
    except Exception as e:
        logger.debug(f"Could not extract job ID: {e}")
        return None


def sanitize_filename(filename, max_length=100):
    """Sanitize filename for saving"""
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Limit length
    if len(filename) > max_length:
        filename = filename[:max_length]
    
    return filename


def is_external_url(url):
    """Check if URL is external (not Naukri)"""
    external_domains = [
        'linkedin.com',
        'indeed.com',
        'naukrigulf.com',
        'monster.com',
        'shine.com'
    ]
    
    return any(domain in url.lower() for domain in external_domains)