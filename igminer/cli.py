"""Command-line interface for igminer."""

import argparse
import logging
import random
import sys
import time

from . import __version__
from .cookies import load_cookies, refresh_cookies
from .daemon import run_daemon
from .scraper import scrape_hashtag, scrape_comments_batch
from .storage import get_storage


def setup_logging(verbose: bool = False):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )


def main():
    parser = argparse.ArgumentParser(
        prog="igminer",
        description=(
            "Fast, undetectable Instagram scraper. "
            "Uses session cookies — no browser, no Selenium, no detection."
        ),
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"igminer {__version__}",
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # ── scrape ──
    p_scrape = sub.add_parser(
        "scrape", help="Scrape hashtags for posts, images, and metadata",
    )
    p_scrape.add_argument(
        "hashtags", nargs="+", help="Hashtags to scrape (without #)",
    )
    p_scrape.add_argument(
        "--pages", type=int, default=20,
        help="Max pages per hashtag (~24 posts/page, default: 20)",
    )
    p_scrape.add_argument(
        "--tab", choices=["top", "recent"], default="top",
        help="'top' for viral/popular, 'recent' for newest (default: top)",
    )
    p_scrape.add_argument(
        "--no-images", action="store_true", help="Skip image downloads",
    )
    p_scrape.add_argument(
        "--no-enrich", action="store_true", help="Skip user profile enrichment",
    )

    # ── comments ──
    p_comments = sub.add_parser(
        "comments", help="Scrape comments for posts already in storage",
    )
    p_comments.add_argument(
        "--limit", type=int, default=200,
        help="Max posts to scrape comments for (default: 200)",
    )

    # ── daemon ──
    p_daemon = sub.add_parser(
        "daemon", help="Run 24/7 continuous scraping",
    )
    p_daemon.add_argument(
        "--hashtags", nargs="+",
        help="Custom hashtag list (default: built-in travel hashtags)",
    )
    p_daemon.add_argument(
        "--target", type=int, default=100_000,
        help="Target post count (default: 100000)",
    )
    p_daemon.add_argument(
        "--no-images", action="store_true", help="Skip image downloads",
    )

    # ── auth ──
    sub.add_parser(
        "auth", help="Extract fresh cookies from Chrome",
    )

    # ── stats ──
    sub.add_parser(
        "stats", help="Show database statistics",
    )

    # ── Global options ──
    parser.add_argument(
        "--cookies", default="ig_cookies.json",
        help="Path to cookies JSON file (default: ig_cookies.json)",
    )
    parser.add_argument(
        "--storage", choices=["sqlite", "json", "supabase"], default="sqlite",
        help="Storage backend (default: sqlite)",
    )
    parser.add_argument(
        "--db", default="igminer.db",
        help="SQLite database path (default: igminer.db)",
    )
    parser.add_argument(
        "--output-dir", default="output",
        help="JSON output directory (default: output)",
    )
    parser.add_argument(
        "--supabase-url", help="Supabase project URL",
    )
    parser.add_argument(
        "--supabase-key", help="Supabase anon/service key",
    )
    parser.add_argument(
        "--supabase-schema", default="public",
        help="Supabase schema (default: public)",
    )
    parser.add_argument(
        "--supabase-bucket", help="Supabase storage bucket for images",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    setup_logging(args.verbose)

    # ── auth ──
    if args.command == "auth":
        refresh_cookies(args.cookies)
        return

    # ── Build storage ──
    storage_kwargs: dict = {}
    if args.storage == "sqlite":
        storage_kwargs["db_path"] = args.db
    elif args.storage == "json":
        storage_kwargs["output_dir"] = args.output_dir
    elif args.storage == "supabase":
        if not args.supabase_url or not args.supabase_key:
            parser.error("--supabase-url and --supabase-key required for supabase backend")
        storage_kwargs.update({
            "supabase_url": args.supabase_url,
            "supabase_key": args.supabase_key,
            "schema": args.supabase_schema,
            "bucket": args.supabase_bucket,
        })

    storage = get_storage(args.storage, **storage_kwargs)

    # ── stats ──
    if args.command == "stats":
        _print_stats(storage)
        storage.close()
        return

    # ── comments ──
    if args.command == "comments":
        cookies = load_cookies(args.cookies)
        scrape_comments_batch(cookies, storage, limit=args.limit)
        storage.close()
        return

    # ── daemon ──
    if args.command == "daemon":
        run_daemon(
            storage=storage,
            cookie_file=args.cookies,
            hashtags=args.hashtags,
            target=args.target,
            download_images=not args.no_images,
        )
        return

    # ── scrape ──
    if args.command == "scrape":
        cookies = load_cookies(args.cookies)
        log.info("=" * 60)
        log.info(f"igminer v{__version__}")
        log.info(f"Hashtags: {args.hashtags}")
        log.info(f"Pages:    {args.pages}/hashtag (~{args.pages * 24} posts)")
        log.info(f"Tab:      {args.tab}")
        log.info(f"Storage:  {args.storage}")
        log.info("=" * 60)

        for hashtag in args.hashtags:
            hashtag = hashtag.lstrip("#")
            try:
                scrape_hashtag(
                    hashtag, cookies, storage,
                    max_pages=args.pages,
                    tab=args.tab,
                    download_images=not args.no_images,
                    enrich_users=not args.no_enrich,
                )
            except KeyboardInterrupt:
                log.info("Interrupted — progress saved.")
                break
            except Exception as e:
                log.error(f"Error on #{hashtag}: {e}", exc_info=True)

            if len(args.hashtags) > 1:
                pause = random.uniform(5, 10)
                log.info(f"Pause: {pause:.0f}s before next hashtag")
                time.sleep(pause)

        storage.close()
        log.info("Done!")


log = logging.getLogger(__name__)


def _print_stats(storage):
    """Print database statistics."""
    count = storage.get_post_count()
    codes = storage.get_existing_codes()
    users = storage.get_enriched_users()

    print(f"\n  Posts:          {count:,}")
    print(f"  Unique codes:   {len(codes):,}")
    print(f"  Enriched users: {len(users):,}")
    print()


if __name__ == "__main__":
    main()
