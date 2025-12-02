"""Image caching and preloading utilities.

This module downloads images referenced in Google Sheets (course `image_url`,
`welcome_image_url`, `catalog_image_url`) into a local directory and provides
helpers to resolve a URL to a local file path when sending photos.
"""

import hashlib
import os
from typing import Dict, Optional

import requests

from config import IMAGES_DIR

# In-memory cache: original URL -> local file path
_IMAGE_CACHE: Dict[str, str] = {}


def _ensure_dir_exists() -> None:
    """Ensure the image cache directory exists."""
    os.makedirs(IMAGES_DIR, exist_ok=True)


def _normalize_url(url: str) -> str:
    """Normalize known CDN patterns (e.g. GitHub blob URLs) to direct image URLs."""
    if not url:
        return url
    # Handle GitHub blob URLs -> raw.githubusercontent.com
    # Example:
    # https://github.com/user/repo/blob/main/path.jpg?raw=true
    # -> https://raw.githubusercontent.com/user/repo/main/path.jpg
    if "github.com" in url and "/blob/" in url:
        try:
            # Strip query/fragment
            base = url.split("?", 1)[0].split("#", 1)[0]
            parts = base.split("github.com/", 1)[1].split("/blob/", 1)
            user_repo = parts[0]          # user/repo
            rest = parts[1]               # branch/path
            return f"https://raw.githubusercontent.com/{user_repo}/{rest}"
        except Exception:
            return url
    return url


def _filename_for_url(url: str) -> str:
    """Generate a stable local filename for a URL."""
    # Use SHA1 of URL for uniqueness, keep a simple extension if present
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    # Try to preserve extension if it looks like an image extension
    ext = ""
    dot_idx = url.rfind(".")
    if dot_idx != -1 and dot_idx < len(url) - 1:
        candidate = url[dot_idx:].split("?", 1)[0].split("#", 1)[0]
        if candidate.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            ext = candidate.lower()
    return f"{h}{ext}"


def _download_image(url: str) -> Optional[str]:
    """Download a single image URL into the cache directory. Returns local path or None."""
    if not url:
        return None

    normalized_url = _normalize_url(url)

    if url in _IMAGE_CACHE and os.path.exists(_IMAGE_CACHE[url]):
        return _IMAGE_CACHE[url]

    _ensure_dir_exists()
    filename = _filename_for_url(normalized_url)
    local_path = os.path.join(IMAGES_DIR, filename)

    # If file already exists on disk (e.g. from previous run), trust it
    if os.path.exists(local_path):
        _IMAGE_CACHE[url] = local_path
        return local_path

    try:
        resp = requests.get(normalized_url, timeout=15)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(resp.content)
        _IMAGE_CACHE[url] = local_path
        print(f"[images] Cached image {url} -> {local_path}")
        return local_path
    except Exception as e:
        print(f"[images] Failed to download image {url}: {e}")
        return None


def preload_images_for_bot(get_courses_data, texts: Dict[str, str]) -> None:
    """Download all images we know about at startup.

    - Course `image_url` from the Courses sheet
    - `welcome_image_url` and `catalog_image_url` from the Texts sheet
    """
    try:
        urls: set[str] = set()

        # Course images
        try:
            courses = get_courses_data()
            for c in courses or []:
                url = str(c.get("image_url") or "").strip()
                if url:
                    urls.add(url)
        except Exception as e:
            print(f"[images] Could not fetch courses for image preload: {e}")

        # Text-based images
        for key in ("welcome_image_url", "catalog_image_url"):
            url = str(texts.get(key) or "").strip()
            if url:
                urls.add(url)

        if not urls:
            print("[images] No image URLs found to preload.")
            return

        print(f"[images] Preloading {len(urls)} images into '{IMAGES_DIR}'")
        for url in urls:
            _download_image(url)
    except Exception as e:
        print(f"[images] FATAL: error during image preloading: {e}")


def get_local_image_path(url: str) -> Optional[str]:
    """Return local cached path for URL if available, downloading it on demand.

    Returns None if URL is empty or download fails.
    """
    if not url:
        return None
    # If we already downloaded in this process and file still exists, reuse it
    if url in _IMAGE_CACHE and os.path.exists(_IMAGE_CACHE[url]):
        return _IMAGE_CACHE[url]
    return _download_image(url)



