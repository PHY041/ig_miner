"""Instagram internal API interactions."""

import logging
import random
import re
import time
from datetime import datetime

import requests as http

from .constants import IG_APP_ID, IG_BASE_URL, SHORTCODE_ALPHABET

log = logging.getLogger(__name__)


def ig_headers(cookies: dict, referer: str = IG_BASE_URL + "/") -> dict:
    """Build request headers that mimic a real browser session."""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "x-ig-app-id": IG_APP_ID,
        "x-csrftoken": cookies.get("csrftoken", ""),
        "x-requested-with": "XMLHttpRequest",
        "x-asbd-id": "129477",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": referer,
    }


def shortcode_to_media_pk(code: str) -> int:
    """Convert Instagram shortcode (e.g. 'CxR2a4Nv3') to numeric media PK."""
    pk = 0
    for char in code:
        pk = pk * 64 + SHORTCODE_ALPHABET.index(char)
    return pk


def parse_media(media: dict) -> dict:
    """Extract structured data from a media object in the sections API response."""
    user = media.get("user") or {}
    caption_obj = media.get("caption") or {}
    caption = caption_obj.get("text") or ""
    location = media.get("location") or {}

    images = (media.get("image_versions2") or {}).get("candidates", [])
    best_img = max(images, key=lambda x: x.get("width", 0)) if images else {}

    taken_at = media.get("taken_at")
    posted_at = None
    if taken_at:
        try:
            posted_at = datetime.fromtimestamp(taken_at).isoformat()
        except (ValueError, OSError):
            pass

    return {
        "code": media.get("code", ""),
        "id": media.get("code", ""),
        "username": user.get("username", ""),
        "user_id": str(user.get("pk", "")),
        "full_name": user.get("full_name", ""),
        "is_verified": user.get("is_verified", False),
        "caption": caption,
        "hashtags": re.findall(r"#\w+", caption),
        "likes": media.get("like_count") or 0,
        "comments_count": media.get("comment_count") or 0,
        "views": media.get("play_count") or media.get("view_count"),
        "media_type": media.get("media_type", 1),
        "image_url": best_img.get("url", ""),
        "image_width": best_img.get("width", 0),
        "image_height": best_img.get("height", 0),
        "posted_at": posted_at,
        "location_name": location.get("name"),
        "location_lat": location.get("lat"),
        "location_lng": location.get("lng"),
        "word_count": len(caption.split()),
    }


def fetch_hashtag_posts(
    hashtag: str,
    cookies: dict,
    max_pages: int = 20,
    tab: str = "top",
) -> list[dict]:
    """Fetch posts for a hashtag using Instagram's sections API.

    Args:
        hashtag: Hashtag to scrape (without #).
        cookies: Instagram session cookies.
        max_pages: Maximum pagination pages (each ~24 posts).
        tab: 'top' for popular/viral, 'recent' for newest.

    Returns:
        List of parsed post dicts.
    """
    headers = ig_headers(cookies)
    all_posts = []
    seen_codes: set[str] = set()
    next_cursor = None

    for page in range(max_pages):
        data: dict = {"tab": tab}
        if next_cursor:
            data["max_id"] = next_cursor

        try:
            r = http.post(
                f"{IG_BASE_URL}/api/v1/tags/{hashtag}/sections/",
                headers=headers,
                cookies=cookies,
                data=data,
                timeout=15,
            )
        except http.exceptions.RequestException as e:
            log.warning(f"  Request failed page {page + 1}: {e}")
            break

        if r.status_code == 429:
            wait = random.uniform(30, 60)
            log.warning(f"  Rate limited! Waiting {wait:.0f}s...")
            time.sleep(wait)
            continue

        if not r.ok:
            log.warning(f"  Page {page + 1}: HTTP {r.status_code}")
            break

        result = r.json()
        page_posts = []

        for sec in result.get("sections", []):
            for m in sec.get("layout_content", {}).get("medias", []):
                media = m.get("media", {})
                code = media.get("code")
                if not code or code in seen_codes:
                    continue
                seen_codes.add(code)
                page_posts.append(parse_media(media))

        all_posts.extend(page_posts)
        more = result.get("more_available", False)
        next_cursor = result.get("next_max_id")

        log.info(
            f"  Page {page + 1}/{max_pages}: +{len(page_posts)} "
            f"(total: {len(all_posts)}, more={more})"
        )

        if not more:
            break

        time.sleep(random.uniform(1.5, 3.0))

    return all_posts


def fetch_comments(
    post_code: str,
    cookies: dict,
    max_pages: int = 3,
) -> list[dict]:
    """Fetch comments for a post.

    Args:
        post_code: Instagram post shortcode.
        cookies: Session cookies.
        max_pages: Max comment pages to fetch.

    Returns:
        List of comment dicts.
    """
    media_pk = shortcode_to_media_pk(post_code)
    headers = ig_headers(
        cookies, referer=f"{IG_BASE_URL}/p/{post_code}/"
    )
    all_comments = []
    min_id = None

    for page in range(max_pages):
        params: dict = {"can_support_threading": "true"}
        if min_id:
            params["min_id"] = min_id

        try:
            r = http.get(
                f"{IG_BASE_URL}/api/v1/media/{media_pk}/comments/",
                headers=headers,
                cookies=cookies,
                params=params,
                timeout=15,
            )
        except http.exceptions.RequestException:
            break

        if r.status_code == 429:
            time.sleep(random.uniform(30, 60))
            continue
        if not r.ok:
            break

        content_type = r.headers.get("content-type", "")
        if "json" not in content_type:
            log.warning(f"Comments {post_code}: got HTML instead of JSON")
            break

        result = r.json()
        for c in result.get("comments", []):
            user = c.get("user") or {}
            created = c.get("created_at")
            posted_at = None
            if created:
                try:
                    posted_at = datetime.fromtimestamp(created).isoformat()
                except (ValueError, OSError):
                    pass

            all_comments.append({
                "id": str(c.get("pk", "")),
                "post_id": post_code,
                "username": user.get("username", ""),
                "text": c.get("text", ""),
                "likes": c.get("comment_like_count") or 0,
                "posted_at": posted_at,
            })

        if not result.get("has_more_comments"):
            break
        min_id = result.get("next_min_id")
        if not min_id:
            break
        time.sleep(random.uniform(1.0, 2.0))

    return all_comments


def fetch_user_profile(username: str, cookies: dict) -> dict | None:
    """Fetch full user profile via Instagram web API.

    Args:
        username: Instagram username.
        cookies: Session cookies.

    Returns:
        User profile dict or None if failed.
    """
    headers = ig_headers(cookies)
    try:
        r = http.get(
            f"{IG_BASE_URL}/api/v1/users/web_profile_info/",
            params={"username": username},
            headers=headers,
            cookies=cookies,
            timeout=15,
        )
    except http.exceptions.RequestException:
        return None

    if not r.ok:
        return None

    user = (r.json().get("data") or {}).get("user")
    if not user:
        return None

    return {
        "username": username,
        "full_name": user.get("full_name") or "",
        "bio": user.get("biography") or "",
        "followers": (user.get("edge_followed_by") or {}).get("count"),
        "following": (user.get("edge_follow") or {}).get("count"),
        "post_count": (
            (user.get("edge_owner_to_timeline_media") or {}).get("count")
        ),
        "is_verified": user.get("is_verified", False),
        "is_private": user.get("is_private", False),
        "profile_pic_url": (
            user.get("profile_pic_url_hd") or user.get("profile_pic_url")
        ),
    }
