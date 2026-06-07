import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from crawler import WebCrawler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

crawler = WebCrawler()


# ── Commands ────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🕷️ *Web Crawler Bot*\n\n"
        "I can crawl websites and extract information for you.\n\n"
        "*Commands:*\n"
        "/crawl `<url>` – Crawl a single page\n"
        "/links `<url>` – Extract all links from a page\n"
        "/text `<url>` – Extract plain text content\n"
        "/meta `<url>` – Extract meta tags (title, description, OG)\n"
        "/images `<url>` – List all images on a page\n"
        "/help – Show this message",
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def crawl_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /crawl <url>\nExample: /crawl https://example.com")
        return

    url = context.args[0]
    msg = await update.message.reply_text(f"🔍 Crawling `{url}`…", parse_mode="Markdown")

    result = await crawler.crawl(url)

    if result["error"]:
        await msg.edit_text(f"❌ Error: {result['error']}")
        return

    text = (
        f"✅ *Crawl complete*\n\n"
        f"🔗 URL: {result['url']}\n"
        f"📄 Title: {result['title'] or 'N/A'}\n"
        f"⏱️ Status: {result['status_code']}\n"
        f"🔗 Links found: {result['link_count']}\n"
        f"🖼️ Images found: {result['image_count']}\n"
        f"📝 Word count: {result['word_count']}\n\n"
        f"*Description:*\n{result['description'] or 'N/A'}"
    )

    keyboard = [
        [
            InlineKeyboardButton("📎 Get Links", callback_data=f"links|{url}"),
            InlineKeyboardButton("📄 Get Text", callback_data=f"text|{url}"),
        ],
        [
            InlineKeyboardButton("🏷️ Meta Tags", callback_data=f"meta|{url}"),
            InlineKeyboardButton("🖼️ Images", callback_data=f"images|{url}"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await msg.edit_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def links_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /links <url>")
        return
    url = context.args[0]
    msg = await update.message.reply_text(f"🔗 Extracting links from `{url}`…", parse_mode="Markdown")
    await _send_links(msg, url)


async def text_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /text <url>")
        return
    url = context.args[0]
    msg = await update.message.reply_text(f"📄 Extracting text from `{url}`…", parse_mode="Markdown")
    await _send_text(msg, url)


async def meta_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /meta <url>")
        return
    url = context.args[0]
    msg = await update.message.reply_text(f"🏷️ Fetching meta tags from `{url}`…", parse_mode="Markdown")
    await _send_meta(msg, url)


async def images_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /images <url>")
        return
    url = context.args[0]
    msg = await update.message.reply_text(f"🖼️ Fetching images from `{url}`…", parse_mode="Markdown")
    await _send_images(msg, url)


# ── Callback buttons ─────────────────────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action, url = query.data.split("|", 1)
    await query.edit_message_text(f"⏳ Working on `{url}`…", parse_mode="Markdown")

    if action == "links":
        await _send_links(query.message, url)
    elif action == "text":
        await _send_text(query.message, url)
    elif action == "meta":
        await _send_meta(query.message, url)
    elif action == "images":
        await _send_images(query.message, url)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _send_links(msg, url: str) -> None:
    result = await crawler.get_links(url)
    if result["error"]:
        await msg.edit_text(f"❌ {result['error']}")
        return

    links = result["links"][:30]  # cap at 30
    lines = [f"🔗 *Links on* `{url}`\n_(showing {len(links)} of {result['total']})_\n"]
    for i, link in enumerate(links, 1):
        lines.append(f"{i}. {link}")
    await msg.edit_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)


async def _send_text(msg, url: str) -> None:
    result = await crawler.get_text(url)
    if result["error"]:
        await msg.edit_text(f"❌ {result['error']}")
        return

    content = result["text"][:3500]  # Telegram message limit
    await msg.edit_text(
        f"📄 *Text content of* `{url}`\n\n{content}…",
        parse_mode="Markdown",
    )


async def _send_meta(msg, url: str) -> None:
    result = await crawler.get_meta(url)
    if result["error"]:
        await msg.edit_text(f"❌ {result['error']}")
        return

    m = result["meta"]
    text = (
        f"🏷️ *Meta Tags for* `{url}`\n\n"
        f"*Title:* {m.get('title') or 'N/A'}\n"
        f"*Description:* {m.get('description') or 'N/A'}\n"
        f"*Keywords:* {m.get('keywords') or 'N/A'}\n"
        f"*OG Title:* {m.get('og_title') or 'N/A'}\n"
        f"*OG Description:* {m.get('og_description') or 'N/A'}\n"
        f"*OG Image:* {m.get('og_image') or 'N/A'}\n"
        f"*Twitter Card:* {m.get('twitter_card') or 'N/A'}\n"
        f"*Canonical:* {m.get('canonical') or 'N/A'}\n"
        f"*Lang:* {m.get('lang') or 'N/A'}"
    )
    await msg.edit_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def _send_images(msg, url: str) -> None:
    result = await crawler.get_images(url)
    if result["error"]:
        await msg.edit_text(f"❌ {result['error']}")
        return

    images = result["images"][:20]
    lines = [f"🖼️ *Images on* `{url}`\n_(showing {len(images)} of {result['total']})_\n"]
    for i, img in enumerate(images, 1):
        alt = f" — _{img['alt']}_" if img.get("alt") else ""
        lines.append(f"{i}. {img['src']}{alt}")
    await msg.edit_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("crawl", crawl_command))
    app.add_handler(CommandHandler("links", links_command))
    app.add_handler(CommandHandler("text", text_command))
    app.add_handler(CommandHandler("meta", meta_command))
    app.add_handler(CommandHandler("images", images_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot is running…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
