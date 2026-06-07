# 🕷️ Telegram Web Crawler Bot

A Telegram bot that crawls websites and extracts links, text, images, and meta tags.

## Features

| Command | Description |
|---|---|
| `/crawl <url>` | Full page summary (title, links, images, word count) |
| `/links <url>` | Extract all hyperlinks |
| `/text <url>` | Extract readable plain text |
| `/meta <url>` | Title, description, OG tags, Twitter card, canonical |
| `/images <url>` | List all images with alt text |

Results also have inline buttons so you can drill down after `/crawl`.

## Setup

### 1. Get a Bot Token

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the token you receive (looks like `123456:ABC-DEF…`)

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set your token

**Option A – environment variable (recommended)**
```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
python bot.py
```

**Option B – edit bot.py directly**
Open `bot.py` and replace `"YOUR_BOT_TOKEN_HERE"` with your actual token.

### 4. Run

```bash
python bot.py
```

The bot uses long-polling, so no webhook or public server is needed.

## Project Structure

```
telegram-crawler-bot/
├── bot.py          # Telegram handlers and entry point
├── crawler.py      # Async HTTP fetcher + BeautifulSoup parser
├── requirements.txt
└── README.md
```

## Notes

- The bot respects `robots.txt` by behaving as a browser (it does **not** parse `robots.txt` — add that if needed).
- Links are capped at 30 and images at 20 per message to stay within Telegram's message size limit.
- Text is truncated at 3 500 characters for the same reason.
- Uses `httpx` for async HTTP and `BeautifulSoup` with the `lxml` parser for fast HTML parsing.
