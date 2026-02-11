"""24/7 continuous scraping daemon."""

import logging
import os
import random
import signal
import time
from pathlib import Path

from .constants import DEFAULT_HASHTAGS
from .cookies import load_cookies, refresh_cookies
from .scraper import scrape_hashtag, scrape_comments_batch
from .storage.base import StorageBackend

log = logging.getLogger(__name__)


def run_daemon(
    storage: StorageBackend,
    cookie_file: str,
    hashtags: list[str] | None = None,
    target: int = 100_000,
    download_images: bool = True,
):
    """Run continuous scraping daemon.

    Args:
        storage: Storage backend.
        cookie_file: Path to cookies JSON.
        hashtags: Hashtags to cycle through. Defaults to DEFAULT_HASHTAGS.
        target: Stop scraping new posts at this count (still does comments).
        download_images: Whether to download images.
    """
    running = True

    def _stop(sig, frame):
        nonlocal running
        log.info(f"Received signal {sig}, finishing current hashtag then stopping...")
        running = False

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    pid_file = Path("igminer_daemon.pid")
    pid_file.write_text(str(os.getpid()))

    cookies = load_cookies(cookie_file)
    tags = hashtags or DEFAULT_HASHTAGS
    cycle = 0

    log.info("=" * 60)
    log.info("DAEMON MODE — 24/7 continuous scraping")
    log.info(f"Hashtags: {len(tags)}")
    log.info(f"Target:   {target:,} posts")
    log.info(f"PID:      {os.getpid()}")
    log.info("=" * 60)

    while running:
        cycle += 1
        db_count = storage.get_post_count()
        log.info(f"=== CYCLE {cycle} | DB: {db_count:,} / {target:,} ===")

        if db_count >= target:
            log.info(f"TARGET REACHED: {db_count:,} >= {target:,}")
            log.info("Switching to comment-only mode...")
            scrape_comments_batch(cookies, storage, limit=500)
            log.info("Sleeping 1 hour before next check...")
            time.sleep(3600)
            continue

        shuffled = tags.copy()
        random.shuffle(shuffled)

        # Phase 1: Top posts
        for tag in shuffled:
            if not running:
                break
            if storage.get_post_count() >= target:
                log.info(f"Target reached mid-cycle: {storage.get_post_count():,}")
                break
            try:
                scrape_hashtag(
                    tag, cookies, storage,
                    max_pages=20, tab="top",
                    download_images=download_images,
                    enrich_users=False,
                )
            except Exception as e:
                log.error(f"Error on #{tag}: {e}", exc_info=True)
                if "login" in str(e).lower() or "401" in str(e):
                    log.error("Session expired! Attempting cookie refresh...")
                    try:
                        cookies = refresh_cookies(cookie_file)
                    except Exception:
                        log.error("Cookie refresh failed. Sleeping 1h...")
                        time.sleep(3600)
                        cookies = load_cookies(cookie_file)

            time.sleep(random.uniform(10, 25))

        if not running:
            break

        # Phase 2: Comments
        log.info("--- Comment scraping pass ---")
        try:
            scrape_comments_batch(cookies, storage, limit=300)
        except Exception as e:
            log.error(f"Comment scraping error: {e}", exc_info=True)

        # Phase 3: Recent tab (smaller sample)
        if running and storage.get_post_count() < target:
            log.info("--- Recent tab pass ---")
            sample = random.sample(shuffled, min(15, len(shuffled)))
            for tag in sample:
                if not running:
                    break
                try:
                    scrape_hashtag(
                        tag, cookies, storage,
                        max_pages=10, tab="recent",
                        download_images=download_images,
                        enrich_users=False,
                    )
                except Exception as e:
                    log.error(f"Error on #{tag} (recent): {e}", exc_info=True)
                time.sleep(random.uniform(10, 20))

        db_count = storage.get_post_count()
        log.info(f"=== CYCLE {cycle} DONE | DB: {db_count:,} / {target:,} ===")

        if running and db_count < target:
            wait = random.uniform(300, 600)
            log.info(f"Cycle pause: {wait / 60:.0f} min before next cycle")
            time.sleep(wait)

    pid_file.unlink(missing_ok=True)
    storage.close()
    log.info("Daemon stopped gracefully.")
