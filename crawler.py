"""
crawler.py – Async recursive/BFS web crawler using httpx + BeautifulSoup.

Deep-crawl stays on the same domain by default and is bounded by:
  max_pages  – total pages visited               (default 50)
  max_depth  – how many hops from the seed URL   (default 3)
  concurrency – parallel HTTP requests at once   (default 8)
"""

import asyncio
import re
from collections import deque
from typing import Any, Callable, Awaitable
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TelegramCrawlerBot/1.0)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 12.0

# File extensions we skip (binaries, downloads, etc.)
SKIP_EXTENSIONS = {
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
    ".mp4", ".mp3", ".mov", ".avi", ".mkv",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
    ".exe", ".dmg", ".deb", ".apk",
}


def _same_domain(base: str, url: str) -> bool:
    b = urlparse(base)
    u = urlparse(url)
    # Match exact host or any subdomain of the seed host
    return u.netloc == b.netloc or u.netloc.endswith("." + b.netloc)


def _clean_url(url: str) -> str:
    """Strip fragment so #section links don't count as new pages."""
    p = urlparse(url)
    return p._replace(fragment="").geturl()


def _skip_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in SKIP_EXTENSIONS)


def _extract_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full = _clean_url(urljoin(base_url, href))
        if full.startswith("http") and not _skip_url(full):
            links.append(full)
    return links


def _page_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    return re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n")).strip()


class WebCrawler:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            headers=HEADERS,
            timeout=TIMEOUT,
            follow_redirects=True,
        )

    # ── Low-level fetch ───────────────────────────────────────────────────

    async def _fetch(self, url: str) -> dict[str, Any]:
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            return {
                "soup": soup,
                "status_code": resp.status_code,
                "url": str(resp.url),
                "error": None,
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}"}
        except httpx.RequestError as e:
            return {"error": f"Request error: {type(e).__name__}"}
        except Exception as e:
            return {"error": str(e)[:80]}

    # ── Single-page helpers (unchanged from v1) ───────────────────────────

    async def crawl(self, url: str) -> dict[str, Any]:
        r = await self._fetch(url)
        if r.get("error"):
            return {"error": r["error"]}
        soup: BeautifulSoup = r["soup"]
        base_url = r["url"]
        title = soup.title.string.strip() if soup.title else None
        desc_tag = soup.find("meta", attrs={"name": "description"}) or \
                   soup.find("meta", attrs={"property": "og:description"})
        links = set(_extract_links(soup, base_url))
        images = soup.find_all("img", src=True)
        words = len(re.findall(r"\w+", soup.get_text()))
        return {
            "error": None, "url": base_url,
            "status_code": r["status_code"], "title": title,
            "description": desc_tag.get("content", "").strip() if desc_tag else None,
            "link_count": len(links), "image_count": len(images), "word_count": words,
        }

    async def get_links(self, url: str) -> dict[str, Any]:
        r = await self._fetch(url)
        if r.get("error"):
            return {"error": r["error"], "links": [], "total": 0}
        links = sorted(set(_extract_links(r["soup"], r["url"])))
        return {"error": None, "links": links, "total": len(links)}

    async def get_text(self, url: str) -> dict[str, Any]:
        r = await self._fetch(url)
        if r.get("error"):
            return {"error": r["error"], "text": ""}
        return {"error": None, "text": _page_text(r["soup"])}

    async def get_meta(self, url: str) -> dict[str, Any]:
        r = await self._fetch(url)
        if r.get("error"):
            return {"error": r["error"], "meta": {}}
        soup = r["soup"]
        def _m(name=None, prop=None):
            t = soup.find("meta", attrs={"name": name}) if name \
                else soup.find("meta", attrs={"property": prop})
            return t.get("content", "").strip() if t else None
        canonical = soup.find("link", rel="canonical")
        html_tag = soup.find("html")
        return {"error": None, "meta": {
            "title": soup.title.string.strip() if soup.title else None,
            "description": _m(name="description"),
            "keywords": _m(name="keywords"),
            "og_title": _m(prop="og:title"),
            "og_description": _m(prop="og:description"),
            "og_image": _m(prop="og:image"),
            "twitter_card": _m(name="twitter:card"),
            "canonical": canonical.get("href") if canonical else None,
            "lang": html_tag.get("lang") if html_tag else None,
        }}

    async def get_images(self, url: str) -> dict[str, Any]:
        r = await self._fetch(url)
        if r.get("error"):
            return {"error": r["error"], "images": [], "total": 0}
        soup, base_url = r["soup"], r["url"]
        images = [{"src": urljoin(base_url, img["src"]), "alt": img.get("alt", "").strip()}
                  for img in soup.find_all("img", src=True)]
        return {"error": None, "images": images, "total": len(images)}

    # ── NEW: Recursive BFS deep-crawl ─────────────────────────────────────

    async def deep_crawl(
        self,
        seed_url: str,
        *,
        max_pages: int = 50,
        max_depth: int = 3,
        concurrency: int = 8,
        same_domain_only: bool = True,
        progress_cb: Callable[[int, int, str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """
        BFS crawl starting at seed_url.

        progress_cb(visited, queued, current_url) is called after each page
        so the bot can update the Telegram message in real time.

        Returns a rich summary dict.
        """
        visited: dict[str, dict] = {}   # url -> page_data
        queue: deque[tuple[str, int]] = deque()  # (url, depth)
        seen: set[str] = set()
        errors: list[str] = []

        seed_clean = _clean_url(seed_url)
        queue.append((seed_clean, 0))
        seen.add(seed_clean)

        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_one(url: str, depth: int) -> None:
            async with semaphore:
                r = await self._fetch(url)
                if r.get("error"):
                    errors.append(f"{url}: {r['error']}")
                    return

                soup: BeautifulSoup = r["soup"]
                base_url = r["url"]
                title = soup.title.string.strip() if soup.title else url
                text = _page_text(soup)
                words = len(re.findall(r"\w+", text))
                links_found = _extract_links(soup, base_url)
                images = soup.find_all("img", src=True)

                visited[url] = {
                    "url": base_url,
                    "title": title,
                    "words": words,
                    "image_count": len(images),
                    "outlinks": links_found,
                    "depth": depth,
                    "snippet": text[:300].replace("\n", " "),
                }

                # Enqueue new links
                if depth < max_depth:
                    for link in links_found:
                        if link not in seen and len(seen) < max_pages * 3:
                            if not same_domain_only or _same_domain(seed_clean, link):
                                seen.add(link)
                                queue.append((link, depth + 1))

        # BFS wave by wave so we can send progress updates
        while queue and len(visited) < max_pages:
            # Take a batch of up to concurrency URLs from the front of the queue
            batch = []
            while queue and len(batch) < concurrency and len(visited) + len(batch) < max_pages:
                batch.append(queue.popleft())

            if not batch:
                break

            # Fire progress callback before the batch
            if progress_cb:
                current = batch[0][0]
                await progress_cb(len(visited), len(queue) + len(batch), current)

            await asyncio.gather(*(fetch_one(u, d) for u, d in batch))

        # ── Build summary ─────────────────────────────────────────────────
        all_pages = list(visited.values())
        total_words = sum(p["words"] for p in all_pages)
        total_images = sum(p["image_count"] for p in all_pages)
        all_outlinks: set[str] = set()
        for p in all_pages:
            all_outlinks.update(p["outlinks"])

        # Top pages by word count (most content)
        top_pages = sorted(all_pages, key=lambda p: p["words"], reverse=True)[:10]

        # Unique external domains linked to
        seed_host = urlparse(seed_clean).netloc
        external_domains: set[str] = set()
        for link in all_outlinks:
            host = urlparse(link).netloc
            if host and host != seed_host:
                external_domains.add(host)

        return {
            "error": None,
            "seed": seed_url,
            "pages_visited": len(visited),
            "pages_queued": len(seen),
            "total_words": total_words,
            "total_images": total_images,
            "total_unique_links": len(all_outlinks),
            "external_domains": sorted(external_domains)[:20],
            "errors": errors[:10],
            "top_pages": top_pages,
            "max_depth_reached": max(p["depth"] for p in all_pages) if all_pages else 0,
        }
