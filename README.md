# igminer

**Fast, undetectable Instagram scraper. No browser. No Selenium. No detection.**

```
pip install igminer
igminer auth            # one-time: extract cookies from Chrome
igminer scrape travel   # scrape #travel — posts, images, comments, users
```

> We scraped **20,000+ posts** with full metadata, images, and comments for an academic research project. Zero bans. Zero CAPTCHAs.

---

## Why igminer?

Every Instagram scraper in 2026 has the same problem: **they get detected and banned**.

- **Instaloader** — login required, aggressive rate limiting, accounts get locked
- **instagrapi** — 476 open issues, constant breakage, ChallengeRequired errors
- **Selenium/Playwright** — bot detection flags you in seconds

igminer takes a different approach: **it uses your real browser session**.

| | igminer | instaloader | instagrapi | Apify |
|---|---|---|---|---|
| Ban risk | Minimal | High | High | None (proxy) |
| Speed | ~500 posts/min | ~50/min | ~200/min | ~100/min |
| Images | Full resolution | Thumbnails | Full | Full |
| Comments | Yes | Limited | Yes | Yes |
| User profiles | Yes | Yes | Yes | Yes |
| Cost | Free | Free | Free | $49+/mo |
| Requires login | Cookie only | Full login | Full login | No |
| 24/7 daemon | Built-in | No | No | No |
| Detection | Undetectable* | Detectable | Detectable | Proxy-based |

*Uses the same session as your real browser — Instagram cannot distinguish automated requests from manual browsing.

---

## How it works

```
Chrome (logged in) → Extract session cookies → Pure HTTP requests
                                                    ↓
                                              Instagram API
                                              (same as browser)
                                                    ↓
                                          SQLite / JSON / Supabase
```

1. You log into Instagram in Chrome (once)
2. igminer extracts your session cookies
3. All requests use these cookies with proper browser headers
4. Instagram sees normal browsing activity from your account

No headless browser. No WebDriver. No fingerprint to detect.

---

## Quick start

### Install

```bash
pip install igminer
```

### Setup (one-time)

Log into Instagram in Chrome, then:

```bash
igminer auth
# Saved 11 cookies to ig_cookies.json
# sessionid: ...a8f3b2c1
```

### Scrape hashtags

```bash
# Scrape top posts for a hashtag (~480 posts with 20 pages)
igminer scrape travel --pages 20

# Multiple hashtags
igminer scrape tokyo osaka kyoto --pages 10

# Recent posts instead of top/viral
igminer scrape fashion --tab recent

# Text only (skip image downloads)
igminer scrape food --no-images
```

### Scrape comments

```bash
# Scrape comments for the top 200 posts in your database
igminer comments --limit 200
```

### Check stats

```bash
igminer stats
#   Posts:          4,821
#   Unique codes:   4,821
#   Enriched users: 1,203
```

### 24/7 daemon mode

```bash
# Run continuously — cycles through hashtags, scrapes comments, handles rate limits
igminer daemon --hashtags travel tokyo food photography --target 50000

# Run in background
nohup igminer daemon --target 100000 > daemon.log 2>&1 &
```

---

## What you get

For each post:
```json
{
  "code": "CxR2a4Nv3",
  "username": "traveler_jane",
  "caption": "Golden hour at the Great Wall #travel #china #sunset",
  "hashtags": ["#travel", "#china", "#sunset"],
  "likes": 12847,
  "comments_count": 234,
  "views": null,
  "image_url": "https://scontent-...",
  "location_name": "Great Wall of China",
  "location_lat": 40.4319,
  "location_lng": 116.5704,
  "posted_at": "2025-11-15T08:23:14",
  "word_count": 8
}
```

For each user:
```json
{
  "username": "traveler_jane",
  "full_name": "Jane Smith",
  "bio": "Travel photographer | 50 countries",
  "followers": 45200,
  "following": 892,
  "post_count": 1247,
  "is_verified": false
}
```

For each comment:
```json
{
  "id": "17890234567",
  "post_id": "CxR2a4Nv3",
  "username": "photo_enthusiast",
  "text": "Incredible shot! The lighting is perfect",
  "likes": 23,
  "posted_at": "2025-11-15T12:45:00"
}
```

---

## Storage backends

### SQLite (default — zero config)

```bash
igminer scrape travel
# Creates igminer.db in current directory
```

### JSON files

```bash
igminer scrape travel --storage json --output-dir ./data
# Creates data/posts_20260210_143022.json
```

### Supabase (cloud database + image hosting)

```bash
igminer scrape travel \
  --storage supabase \
  --supabase-url https://xxx.supabase.co \
  --supabase-key sb_... \
  --supabase-schema public \
  --supabase-bucket ig-images
```

<details>
<summary>Supabase SQL setup</summary>

```sql
CREATE TABLE ig_users (
  username TEXT PRIMARY KEY,
  full_name TEXT,
  bio TEXT,
  followers INTEGER,
  following INTEGER,
  post_count INTEGER,
  is_verified BOOLEAN DEFAULT FALSE,
  is_private BOOLEAN DEFAULT FALSE,
  profile_pic_url TEXT,
  scraped_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ig_posts (
  id TEXT PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  username TEXT REFERENCES ig_users(username),
  caption TEXT,
  hashtags TEXT[],
  image_url TEXT,
  storage_url TEXT,
  media_type INTEGER DEFAULT 1,
  likes INTEGER DEFAULT 0,
  comments_count INTEGER DEFAULT 0,
  views BIGINT,
  location_name TEXT,
  location_lat FLOAT,
  location_lng FLOAT,
  posted_at TIMESTAMPTZ,
  scraped_at TIMESTAMPTZ DEFAULT NOW(),
  word_count INTEGER DEFAULT 0
);

CREATE TABLE ig_comments (
  id TEXT PRIMARY KEY,
  post_id TEXT REFERENCES ig_posts(id),
  username TEXT REFERENCES ig_users(username),
  text TEXT,
  likes INTEGER DEFAULT 0,
  posted_at TIMESTAMPTZ
);

CREATE INDEX idx_posts_username ON ig_posts(username);
CREATE INDEX idx_posts_likes ON ig_posts(likes DESC);
CREATE INDEX idx_comments_post ON ig_comments(post_id);
```

</details>

---

## Python API

```python
from igminer.cookies import load_cookies
from igminer.api import fetch_hashtag_posts, fetch_comments, fetch_user_profile
from igminer.storage import get_storage

cookies = load_cookies("ig_cookies.json")
storage = get_storage("sqlite", db_path="my_data.db")

# Fetch posts
posts = fetch_hashtag_posts("travel", cookies, max_pages=5, tab="top")
for post in posts:
    storage.upsert_post(post)
    print(f"{post['code']}: {post['likes']} likes — {post['caption'][:60]}")

# Fetch comments
comments = fetch_comments("CxR2a4Nv3", cookies)
for c in comments:
    print(f"@{c['username']}: {c['text'][:80]}")

# Fetch user profile
profile = fetch_user_profile("natgeo", cookies)
print(f"@natgeo: {profile['followers']:,} followers")

storage.close()
```

---

## Rate limiting & safety

igminer is built to be gentle:

- **Randomized delays** between requests (1.5–3s for posts, 10–25s between hashtags in daemon)
- **Automatic backoff** on 429 (rate limit) responses — waits 30–60s
- **Session detection** — if cookies expire, attempts auto-refresh from Chrome
- **Graceful shutdown** — SIGTERM/SIGINT saves progress before stopping

Tips to avoid issues:
- Don't run more than 2 parallel instances
- Keep page counts reasonable (20 pages = ~480 posts per hashtag)
- The daemon mode handles all rate limiting automatically

---

## Cookie management

### Auto-extract from Chrome (macOS/Linux)

```bash
igminer auth
# Requires: pip install igminer[chrome]
```

### Manual export

If auto-extract doesn't work, export cookies manually:

1. Open Instagram in Chrome
2. Open DevTools → Application → Cookies
3. Copy these cookies into `ig_cookies.json`:

```json
{
  "sessionid": "your_session_id",
  "csrftoken": "your_csrf_token",
  "ds_user_id": "your_user_id",
  "mid": "...",
  "ig_did": "..."
}
```

Only `sessionid` and `csrftoken` are required. Sessions last ~90 days.

---

## Use cases

- **Academic research** — Collect Instagram data for NLP, sentiment analysis, information retrieval
- **Market research** — Analyze hashtag trends, engagement patterns, competitor content
- **Dataset creation** — Build image-caption datasets for ML/AI training
- **Social listening** — Monitor brand mentions and user sentiment
- **Content analysis** — Study visual trends across hashtags and locations

---

## Disclaimer

This tool is for **educational and research purposes only**. It accesses publicly available data through Instagram's web interface using authenticated sessions.

- Respect Instagram's Terms of Service
- Don't scrape private accounts
- Don't use collected data for harassment or spam
- Comply with applicable data protection laws (GDPR, CCPA, etc.)
- Rate limit your requests to avoid service disruption

The authors are not responsible for misuse of this tool.

---

## Contributing

PRs welcome! Areas we'd love help with:

- [ ] Windows cookie extraction testing
- [ ] Firefox cookie support
- [ ] Export to CSV/Parquet
- [ ] Reel/video metadata scraping
- [ ] Location-based scraping
- [ ] Async support (aiohttp)

---

## License

MIT
