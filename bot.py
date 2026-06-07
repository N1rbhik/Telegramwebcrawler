import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from crawler import WebCrawler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
crawler = WebCrawler()

# ── /start & /help ────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🕷️ *Web Crawler Bot*\n\n"
        "Commands:\n"
        "/crawl `<url>` – Single-page summary\n"
        "/deepcrawl `<url>` – Recursively follow ALL links & summarize\n"
        "/deepcrawl `<url>` `<pages>` `<depth>` – Custom limits "
        "_(e.g. /deepcrawl https://example.com 30 2)_\n"
        "/links `<url>` – List links on a page\n"
        "/text `<url>` – Extract page text\n"
        "/meta `<url>` – Meta tags\n"
        "/images `<url>` – List images\n"
        "/help – Show this message",
        parse_mode="Markdown",
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)

# ── /crawl (single page) ──────────────────────────────────────────────────────

async def crawl_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /crawl <url>")
        return
    url = context.args[0]
    msg = await update.message.reply_text(f"🔍 Crawling `{url}`…", parse_mode="Markdown")
    result = await crawler.crawl(url)
    if result["error"]:
        await msg.edit_text(f"❌ {result['error']}")
        return
    text = (
        f"✅ *Page crawled*\n\n"
        f"📄 *Title:* {result['title'] or 'N/A'}\n"
        f"🔗 *URL:* {result['url']}\n"
        f"⚡ *Status:* {result['status_code']}\n"
        f"🔗 *Links:* {result['link_count']}\n"
        f"🖼️ *Images:* {result['image_count']}\n"
        f"📝 *Words:* {result['word_count']}\n\n"
        f"_{result['description'] or 'No description'}_"
    )
    keyboard = [[
        InlineKeyboardButton("📎 Links", callback_data=f"links|{url}"),
        InlineKeyboardButton("📄 Text",  callback_data=f"text|{url}"),
        InlineKeyboardButton("🏷️ Meta",  callback_data=f"meta|{url}"),
        InlineKeyboardButton("🖼️ Imgs",  callback_data=f"images|{url}"),
    ]]
    await msg.edit_text(text, parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(keyboard))

# ── /deepcrawl (recursive BFS) ────────────────────────────────────────────────

async def deepcrawl_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Usage: /deepcrawl <url> [max_pages] [max_depth]\n"
            "Example: /deepcrawl https://example.com 40 3"
        )
        return

    url = context.args[0]
    try:
        max_pages = int(context.args[1]) if len(context.args) > 1 else 50
        max_depth = int(context.args[2]) if len(context.args) > 2 else 3
    except ValueError:
        await update.message.reply_text("max_pages and max_depth must be numbers.")
        return

    max_pages = max(5, min(max_pages, 200))   # clamp 5–200
    max_depth = max(1, min(max_depth, 6))     # clamp 1–6

    msg = await update.message.reply_text(
        f"🕸️ *Deep crawl started*\n\n"
        f"🌱 Seed: `{url}`\n"
        f"📄 Max pages: {max_pages}  |  📐 Max depth: {max_depth}\n\n"
        f"⏳ Crawling… this may take a minute.",
        parse_mode="Markdown",
    )

    last_update = {"text": ""}
    update_lock = asyncio.Lock()

    async def progress(visited: int, queued: int, current_url: str) -> None:
        bar_filled = int((visited / max_pages) * 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        short_url = current_url[:50] + "…" if len(current_url) > 50 else current_url
        new_text = (
            f"🕸️ *Deep crawl in progress…*\n\n"
            f"🌱 `{url}`\n\n"
            f"`[{bar}]` {visited}/{max_pages} pages\n"
            f"📬 Queued: {queued}\n"
            f"🔍 Now: `{short_url}`"
        )
        async with update_lock:
            if new_text != last_update["text"]:
                last_update["text"] = new_text
                try:
                    await msg.edit_text(new_text, parse_mode="Markdown")
                except Exception:
                    pass   # ignore rate-limit flicker

    result = await crawler.deep_crawl(
        url,
        max_pages=max_pages,
        max_depth=max_depth,
        concurrency=8,
        same_domain_only=True,
        progress_cb=progress,
    )

    if result["error"]:
        await msg.edit_text(f"❌ {result['error']}")
        return

    # ── Format summary ────────────────────────────────────────────────────
    top = result["top_pages"]
    top_lines = []
    for i, p in enumerate(top[:8], 1):
        title = (p["title"] or p["url"])[:55]
        top_lines.append(f"{i}. *{title}*\n   _{p['words']:,} words, {p['image_count']} imgs, depth {p['depth']}_")

    ext = result["external_domains"]
    ext_text = ", ".join(ext[:10]) if ext else "none"

    errors_text = ""
    if result["errors"]:
        errors_text = f"\n⚠️ *Errors ({len(result['errors'])}):* {result['errors'][0][:60]}…"

    summary = (
        f"✅ *Deep Crawl Complete!*\n\n"
        f"🌱 `{url}`\n\n"
        f"📊 *Stats*\n"
        f"• Pages visited: *{result['pages_visited']}*\n"
        f"• Max depth reached: *{result['max_depth_reached']}*\n"
        f"• Total words: *{result['total_words']:,}*\n"
        f"• Total images: *{result['total_images']:,}*\n"
        f"• Unique links found: *{result['total_unique_links']:,}*\n"
        f"• External domains linked: *{len(result['external_domains'])}*\n"
        f"{errors_text}\n\n"
        f"🌐 *External domains:*\n_{ext_text}_\n\n"
        f"📄 *Top pages by content:*\n" + "\n\n".join(top_lines)
    )

    # Telegram message limit is 4096 chars
    if len(summary) > 4000:
        summary = summary[:3990] + "\n…_(truncated)_"

    await msg.edit_text(summary, parse_mode="Markdown", disable_web_page_preview=True)

# ── Single-page drill-down commands ──────────────────────────────────────────

async def links_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /links <url>")
        return
    msg = await update.message.reply_text("🔗 Fetching links…")
    await _send_links(msg, context.args[0])

async def text_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /text <url>")
        return
    msg = await update.message.reply_text("📄 Fetching text…")
    await _send_text(msg, context.args[0])

async def meta_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /meta <url>")
        return
    msg = await update.message.reply_text("🏷️ Fetching meta…")
    await _send_meta(msg, context.args[0])

async def images_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /images <url>")
        return
    msg = await update.message.reply_text("🖼️ Fetching images…")
    await _send_images(msg, context.args[0])

# ── Inline button callbacks ───────────────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action, url = query.data.split("|", 1)
    await query.edit_message_text(f"⏳ Working…")
    dispatch = {"links": _send_links, "text": _send_text,
                "meta": _send_meta, "images": _send_images}
    if action in dispatch:
        await dispatch[action](query.message, url)

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _send_links(msg, url: str) -> None:
    r = await crawler.get_links(url)
    if r["error"]:
        await msg.edit_text(f"❌ {r['error']}")
        return
    links = r["links"][:30]
    lines = [f"🔗 *Links* _(showing {len(links)} of {r['total']})_\n"]
    for i, l in enumerate(links, 1):
        lines.append(f"{i}. {l}")
    await msg.edit_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)

async def _send_text(msg, url: str) -> None:
    r = await crawler.get_text(url)
    if r["error"]:
        await msg.edit_text(f"❌ {r['error']}")
        return
    await msg.edit_text(f"📄 *Text*\n\n{r['text'][:3500]}…", parse_mode="Markdown")

async def _send_meta(msg, url: str) -> None:
    r = await crawler.get_meta(url)
    if r["error"]:
        await msg.edit_text(f"❌ {r['error']}")
        return
    m = r["meta"]
    await msg.edit_text(
        f"🏷️ *Meta Tags*\n\n"
        f"*Title:* {m.get('title') or 'N/A'}\n"
        f"*Desc:* {m.get('description') or 'N/A'}\n"
        f"*Keywords:* {m.get('keywords') or 'N/A'}\n"
        f"*OG Title:* {m.get('og_title') or 'N/A'}\n"
        f"*OG Desc:* {m.get('og_description') or 'N/A'}\n"
        f"*OG Image:* {m.get('og_image') or 'N/A'}\n"
        f"*Twitter:* {m.get('twitter_card') or 'N/A'}\n"
        f"*Canonical:* {m.get('canonical') or 'N/A'}\n"
        f"*Lang:* {m.get('lang') or 'N/A'}",
        parse_mode="Markdown", disable_web_page_preview=True,
    )

async def _send_images(msg, url: str) -> None:
    r = await crawler.get_images(url)
    if r["error"]:
        await msg.edit_text(f"❌ {r['error']}")
        return
    images = r["images"][:20]
    lines = [f"🖼️ *Images* _(showing {len(images)} of {r['total']})_\n"]
    for i, img in enumerate(images, 1):
        alt = f" — _{img['alt']}_" if img.get("alt") else ""
        lines.append(f"{i}. {img['src']}{alt}")
    await msg.edit_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)

# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("help",      help_command))
    app.add_handler(CommandHandler("crawl",     crawl_command))
    app.add_handler(CommandHandler("deepcrawl", deepcrawl_command))
    app.add_handler(CommandHandler("links",     links_command))
    app.add_handler(CommandHandler("text",      text_command))
    app.add_handler(CommandHandler("meta",      meta_command))
    app.add_handler(CommandHandler("images",    images_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    logger.info("Bot is running…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
