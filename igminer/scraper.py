"""Core scraping pipeline — orchestrates API calls and storage."""

import logging
import random
import time

import requests as http

from .api import fetch_hashtag_posts, fetch_comments, fetch_user_profile
from .storage.base import StorageBackend

log = logging.getLogger(__name__)


def download_image(image_url: str) -> bytes | None:
    """Download an image from Instagram CDN."""
    if not image_url:
        return None
    try:
        resp = http.get(
            image_url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
        )
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        log.warning(f"Image download failed: {e}")
    return None


def scrape_hashtag(
    hashtag: str,
    cookies: dict,
    storage: StorageBackend,
    max_pages: int = 20,
    tab: str = "top",
    download_images: bool = True,
    enrich_users: bool = True,
) -> int:
    """Full pipeline for one hashtag: fetch → store posts → download images → enrich users.

    Args:
        hashtag: Hashtag to scrape (without #).
        cookies: Instagram session cookies.
        storage: Storage backend instance.
        max_pages: Max pagination pages.
        tab: 'top' or 'recent'.
        download_images: Whether to download and store images.
        enrich_users: Whether to fetch full user profiles.

    Returns:
        Number of new posts stored.
    """
    existing_codes = storage.get_existing_codes()
    log.info(f"DB has {len(existing_codes)} existing posts")

    log.info(f"Fetching #{hashtag} (tab={tab}, max {max_pages} pages)...")
    posts = fetch_hashtag_posts(hashtag, cookies, max_pages, tab)

    new_posts = [p for p in posts if p["code"] not in existing_codes]
    log.info(
        f"#{hashtag}: {len(new_posts)} new / {len(posts)} total "
        f"({len(posts) - len(new_posts)} already in DB)"
    )

    if not new_posts:
        return 0

    users_seen: set[str] = set()
    stored = 0

    for i, post in enumerate(new_posts):
        username = post.get("username") or ""

        # Download + store image
        if download_images and post.get("image_url"):
            img_bytes = download_image(post["image_url"])
            if img_bytes:
                url = storage.store_image(img_bytes, f"{post['code']}.jpg")
                if url:
                    post["storage_url"] = url
                    post["local_image_path"] = url

        # Upsert user (minimal, for FK)
        if username:
            storage.upsert_user({
                "username": username,
                "full_name": post.get("full_name", ""),
                "is_verified": post.get("is_verified", False),
            })
            users_seen.add(username)

        # Upsert post
        storage.upsert_post(post)
        stored += 1

        if (i + 1) % 20 == 0:
            log.info(f"  Stored {i + 1}/{len(new_posts)} posts...")

        time.sleep(random.uniform(0.3, 0.8))

    log.info(f"Stored {stored} posts for #{hashtag}")

    # Enrich user profiles
    if enrich_users:
        enriched = storage.get_enriched_users()
        to_enrich = users_seen - enriched
        if to_enrich:
            log.info(f"Enriching {len(to_enrich)} user profiles...")
            for j, uname in enumerate(to_enrich):
                profile = fetch_user_profile(uname, cookies)
                if profile:
                    storage.upsert_user(profile)
                    log.info(
                        f"  [{j + 1}/{len(to_enrich)}] @{uname}: "
                        f"{profile.get('followers', 0):,} followers"
                    )
                else:
                    log.warning(f"  [{j + 1}/{len(to_enrich)}] @{uname}: failed")
                time.sleep(random.uniform(1.5, 3.0))

    return stored


def scrape_comments_batch(
    cookies: dict,
    storage: StorageBackend,
    limit: int = 200,
) -> int:
    """Scrape comments for top posts that don't have comments stored yet.

    Returns:
        Total number of comments stored.
    """
    to_scrape = storage.get_posts_needing_comments(limit)
    if not to_scrape:
        log.info("No posts need comment scraping")
        return 0

    log.info(f"Scraping comments for {len(to_scrape)} posts...")
    total = 0

    for i, post in enumerate(to_scrape):
        code = post["code"]
        comments = fetch_comments(code, cookies)
        if comments:
            for c in comments:
                c["post_id"] = code
                storage.upsert_comment(c)
            total += len(comments)
            log.info(f"  [{i + 1}/{len(to_scrape)}] {code}: {len(comments)} comments")
        else:
            log.info(f"  [{i + 1}/{len(to_scrape)}] {code}: 0 comments")

        time.sleep(random.uniform(1.5, 3.0))

    log.info(f"Comment scraping done: {total} comments stored")
    return total
