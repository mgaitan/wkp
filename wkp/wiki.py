from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qs, unquote, urlparse

import mwclient
import mwparserfromhell
import requests

API_TIMEOUT = 30
DEFAULT_USER_AGENT = "wkp/0.1 (https://example.invalid; contact: local)"
DEFAULT_TRANSLATE_URL = "https://libretranslate.de/translate"


class WikiError(RuntimeError):
    pass


@dataclass(frozen=True)
class WikiPage:
    lang: str
    title: str
    wikitext: str


def parse_wiki_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if not parsed.netloc:
        raise WikiError(f"Invalid URL: {url}")

    host_parts = parsed.netloc.split(".")
    if len(host_parts) < 3 or host_parts[-2:] != ["wikipedia", "org"]:
        raise WikiError(f"Unsupported host: {parsed.netloc}")

    lang = host_parts[0]
    title = None

    if parsed.path.startswith("/wiki/"):
        title = unquote(parsed.path[len("/wiki/") :])
    else:
        query = parse_qs(parsed.query)
        title_values = query.get("title")
        if title_values:
            title = title_values[0]

    if not title:
        raise WikiError(f"Could not parse title from URL: {url}")

    return lang, title


def api_endpoint(lang: str) -> str:
    return f"https://{lang}.wikipedia.org/w/api.php"


def rest_endpoint(lang: str) -> str:
    return f"https://{lang}.wikipedia.org/api/rest_v1"


def _user_agent() -> str:
    return os.getenv("WKP_USER_AGENT", DEFAULT_USER_AGENT)


def _headers() -> dict[str, str]:
    return {"User-Agent": _user_agent()}


def fetch_wikitext(lang: str, title: str) -> WikiPage:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": 2,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "titles": title,
        "redirects": 1,
    }
    response = requests.get(
        api_endpoint(lang),
        params=params,
        headers=_headers(),
        timeout=API_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()

    pages = data.get("query", {}).get("pages", [])
    if not pages:
        raise WikiError("No pages returned from API")

    page = pages[0]
    if page.get("missing") is True:
        raise WikiError(f"Page not found: {title}")

    revisions = page.get("revisions")
    if not revisions:
        raise WikiError(f"No revisions found for: {title}")

    content = revisions[0].get("slots", {}).get("main", {}).get("content")
    if content is None:
        raise WikiError("Missing wikitext content in API response")

    return WikiPage(lang=lang, title=page["title"], wikitext=content)


def safe_filename(title: str) -> str:
    safe = title.replace(" ", "_")
    safe = re.sub(r"[\\/:*?\"<>|]", "_", safe)
    return safe


def default_article_path(lang: str, title: str) -> Path:
    return Path("articles") / lang / f"{safe_filename(title)}.wiki"


def save_wikitext(path: Path, wikitext: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(wikitext, encoding="utf-8")


def load_wikitext(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def title_from_path(path: Path) -> str:
    return path.stem.replace("_", " ")


def preview_wikitext(lang: str, wikitext: str, title: Optional[str] = None) -> str:
    params = {
        "action": "parse",
        "format": "json",
        "contentmodel": "wikitext",
        "prop": "text",
        "disablelimitreport": 1,
        "text": wikitext,
    }
    if title:
        params["title"] = title
    response = requests.post(
        api_endpoint(lang), data=params, headers=_headers(), timeout=API_TIMEOUT
    )
    response.raise_for_status()
    data = response.json()
    parsed = data.get("parse", {}).get("text", {}).get("*")
    if parsed is None:
        raise WikiError("Preview response missing parsed HTML")
    return parsed


def login_site(lang: str, username: str, password: str) -> mwclient.Site:
    site = mwclient.Site(("https", f"{lang}.wikipedia.org"), path="/w/")
    site.login(username, password)
    return site


def publish_page(
    lang: str,
    title: str,
    wikitext: str,
    username: str,
    password: str,
    summary: str,
    minor: bool,
) -> None:
    site = login_site(lang, username, password)
    page = site.pages[title]
    page.edit(wikitext, summary=summary, minor=minor)


def make_translator(
    source_lang: str,
    target_lang: str,
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Callable[[str], str]:
    cache: dict[str, str] = {}
    session = requests.Session()
    translate_url = endpoint or os.getenv("WKP_TRANSLATE_URL") or DEFAULT_TRANSLATE_URL
    api_key = api_key or os.getenv("WKP_TRANSLATE_KEY")

    def translate_segment(segment: str) -> str:
        if not segment.strip():
            return segment

        cached = cache.get(segment)
        if cached is not None:
            return cached

        leading = re.match(r"^\s+", segment)
        trailing = re.search(r"\s+$", segment)
        core = segment.strip()

        payload = {
            "q": core,
            "source": source_lang,
            "target": target_lang,
            "format": "text",
        }
        if api_key:
            payload["api_key"] = api_key

        response = session.post(translate_url, json=payload, timeout=API_TIMEOUT)
        response.raise_for_status()
        translated = response.json().get("translatedText")
        if translated is None:
            raise WikiError("Translation API response missing translatedText")

        result = f"{leading.group(0) if leading else ''}{translated}{trailing.group(0) if trailing else ''}"
        cache[segment] = result
        return result

    return translate_segment


def translate_wikitext(wikitext: str, translator: Callable[[str], str]) -> str:
    code = mwparserfromhell.parse(wikitext)

    for heading in code.filter_headings():
        heading.title = translator(str(heading.title))

    for link in code.filter_wikilinks():
        if link.text:
            link.text = translator(str(link.text))

    for link in code.filter_external_links():
        if link.title:
            link.title = translator(str(link.title))

    for text_node in code.filter_text():
        raw = str(text_node)
        if not raw.strip():
            continue
        text_node.value = translator(raw)

    return str(code)


def load_credentials() -> tuple[Optional[str], Optional[str]]:
    username = os.getenv("WKP_USERNAME")
    password = os.getenv("WKP_PASSWORD")
    return username, password
