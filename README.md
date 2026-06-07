# 🕷️ Telegram Web Crawler Bot

A Telegram bot that crawls websites and extracts links, text, images, and meta tags — including a **recursive deep crawler** that automatically follows every link it finds and summarizes the entire site.

## Commands

| Command | Description |
|---|---|
| `/crawl <url>` | Single-page summary (title, links, images, word count) |
| `/deepcrawl <url>` | Recursively follow all links and summarize the whole site |
| `/deepcrawl <url> <max_pages> <max_depth>` | Deep crawl with custom limits |
| `/links <url>` | Extract all hyperlinks from a page |
| `/text <url>` | Extract readable plain text |
| `/meta <url>` | Title, description, OG tags, Twitter card, canonical |
| `/images <url>` | List all images with alt text |

After `/crawl`, inline buttons let you drill down into links, text, meta, and images without retyping the URL.

### Deep Crawl examples

```
/deepcrawl https://example.com              # defaults: 50 pages, depth 3
/deepcrawl https://example.com 30 2        # 30 pages max, 2 hops deep
/deepcrawl https://myblog.com 100 4        # larger crawl, go deeper
```

The deep crawl shows a **live progress bar** in Telegram as it works, then delivers a full summary including:
- Pages visited and max depth reached
- Total words and images across the whole site
- All unique links discovered
- External domains the site links to
- Top 8 pages ranked by content (word count)

## Setup

### 1. Get a Bot Token

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the token you receive (looks like `123456789:ABCdef…`)

### 2. Clone / copy the files

```bash
cd ~/Telegramwebcrawler   # or wherever you put the project
```

Make sure you have these four files:
```
bot.py
crawler.py
requirements.txt
README.md
```

### 3. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Set your token

**Option A — environment variable (recommended)**
```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
```

To make it permanent so you don't have to re-type it each session:
```bash
echo 'export TELEGRAM_BOT_TOKEN="your_token_here"' >> ~/.bashrc
source ~/.bashrc
```

**Option B — edit bot.py directly**
Open `bot.py` and replace `"YOUR_BOT_TOKEN_HERE"` with your token.

### 6. Run

```bash
python bot.py
```

The bot uses long-polling — no webhook or public server needed.

## Keep it running after closing SSH

**Using screen (recommended)**
```bash
screen -S crawlerbot
source venv/bin/activate
export TELEGRAM_BOT_TOKEN="your_token_here"
python bot.py
# Press Ctrl+A then D to detach — keeps running in background
# To reconnect later: screen -r crawlerbot
```

**Using nohup**
```bash
TELEGRAM_BOT_TOKEN="your_token_here" nohup python bot.py > bot.log 2>&1 &
```

## Project Structure

```
Telegramwebcrawler/
├── bot.py            # Telegram command handlers and entry point
├── crawler.py        # Async BFS crawler + single-page helpers (httpx + BeautifulSoup)
├── requirements.txt  # Python dependencies
└── README.md
```

## How the deep crawler works

- **BFS (breadth-first search)** — visits pages level by level from the seed URL, so it covers the site evenly rather than going down one rabbit hole
- **8 concurrent requests** — fetches pages in parallel for speed
- **Same-domain only** — won't drift off to external sites (Google, Twitter, etc.)
- **Skips binaries** — ignores `.pdf`, `.jpg`, `.zip`, `.mp4`, and other non-HTML file types automatically
- **Bounded** — capped at `max_pages` (default 50) and `max_depth` (default 3 hops) so it never runs forever

## Notes

- Links are capped at 30 per message, images at 20, and text at 3,500 characters to stay within Telegram's 4,096-character message limit.
- The bot does **not** parse `robots.txt` — use it responsibly and only on sites you have permission to crawl.
- Uses `httpx` for async HTTP and `BeautifulSoup` with the `lxml` parser for fast HTML parsing.
