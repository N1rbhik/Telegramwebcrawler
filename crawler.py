"""
crawler.py – Async web crawler using httpx + BeautifulSoup.
"""

import asyncio
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TelegramCrawlerBot/1.0; "
        "+https://github.com/your-repo)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 15.0


class WebCrawler:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            headers=HEADERS,
            timeout=TIMEOUT,
            follow_redirects=True,
        )

    # ── Low-level fetch ───────────────────────────────────────────────────────

    async def _fetch(self, url: str) -> dict[str, Any]:
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            return {"soup": soup, "status_code": resp.status_code, "url": str(resp.url), "error": None}
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}"}
        except httpx.RequestError as e:
            return {"error": f"Request failed: {e}"}
        except Exception as e:
            return {"error": str(e)}

    # ── Public API ────────────────────────────────────────────────────────────

    async def crawl(self, url: str) -> dict[str, Any]:
        """Return a summary of the page."""
        r = await self._fetch(url)
        if r.get("error"):
            return {"error": r["error"]}

        soup: BeautifulSoup = r["soup"]
        base_url = r["url"]

        title = soup.title.string.strip() if soup.title else None
        description = (
            soup.find("meta", attrs={"name": "description"}) or
            soup.find("meta", attrs={"property": "og:description"})
        )
        desc_content = description.get("content", "").strip() if description else None

        links = {
            urljoin(base_url, a["href"])
            for a in soup.find_all("a", href=True)
            if not a["href"].startswith(("#", "javascript:"))
        }
        images = soup.find_all("img", src=True)
        words = len(re.findall(r"\w+", soup.get_text()))

        return {
            "error": None,
            "url": base_url,
            "status_code": r["status_code"],
            "title": title,
            "description": desc_content,
            "link_count": len(links),
            "image_count": len(images),
            "word_count": words,
        }

    async def get_links(self, url: str) -> dict[str, Any]:
        r = await self._fetch(url)
        if r.get("error"):
            return {"error": r["error"], "links": [], "total": 0}

        soup: BeautifulSoup = r["soup"]
        base_url = r["url"]
        links = sorted({
            urljoin(base_url, a["href"])
            for a in soup.find_all("a", href=True)
            if not a["href"].startswith(("#", "javascript:", "mailto:"))
        })
        return {"error": None, "links": links, "total": len(links)}

    async def get_text(self, url: str) -> dict[str, Any]:
        r = await self._fetch(url)
        if r.get("error"):
            return {"error": r["error"], "text": ""}

        soup: BeautifulSoup = r["soup"]
        # Remove script and style noise
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()

        text = re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n")).strip()
        return {"error": None, "text": text}

    async def get_meta(self, url: str) -> dict[str, Any]:
        r = await self._fetch(url)
        if r.get("error"):
            return {"error": r["error"], "meta": {}}

        soup: BeautifulSoup = r["soup"]

        def _meta(name: str | None = None, prop: str | None = None) -> str | None:
            tag = (
                soup.find("meta", attrs={"name": name}) if name
                else soup.find("meta", attrs={"property": prop})
            )
            return tag.get("content", "").strip() if tag else None

        canonical = soup.find("link", rel="canonical")
        html_tag = soup.find("html")

        meta = {
            "title": soup.title.string.strip() if soup.title else None,
            "description": _meta(name="description"),
            "keywords": _meta(name="keywords"),
            "og_title": _meta(prop="og:title"),
            "og_description": _meta(prop="og:description"),
            "og_image": _meta(prop="og:image"),
            "twitter_card": _meta(name="twitter:card"),
            "canonical": canonical.get("href") if canonical else None,
            "lang": html_tag.get("lang") if html_tag else None,
        }
        return {"error": None, "meta": meta}

    async def get_images(self, url: str) -> dict[str, Any]:
        r = await self._fetch(url)
        if r.get("error"):
            return {"error": r["error"], "images": [], "total": 0}

        soup: BeautifulSoup = r["soup"]
        base_url = r["url"]
        images = [
            {
                "src": urljoin(base_url, img["src"]),
                "alt": img.get("alt", "").strip(),
            }
            for img in soup.find_all("img", src=True)
        ]
        return {"error": None, "images": images, "total": len(images)}
