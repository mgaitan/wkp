from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from wkp import wiki

app = typer.Typer(help="Wikipedia helper CLI (download, translate, preview, publish).")


def _ensure_env() -> None:
    load_dotenv()


@app.command()
def download(url: str, out: Optional[Path] = None) -> None:
    """Download wikitext from a Wikipedia URL."""
    lang, title = wiki.parse_wiki_url(url)
    page = wiki.fetch_wikitext(lang, title)
    target = out or wiki.default_article_path(lang, page.title)
    wiki.save_wikitext(target, page.wikitext)
    typer.echo(f"Saved: {target}")


@app.command()
def preview(
    path: Path,
    lang: str = "es",
    out: Optional[Path] = None,
    open: bool = typer.Option(False, "--open", help="Open HTML preview after render."),
) -> None:
    """Render wikitext to HTML via Wikimedia REST API."""
    wikitext = wiki.load_wikitext(path)
    html = wiki.preview_wikitext(lang, wikitext, title=wiki.title_from_path(path))
    target = out or (Path("preview") / f"{path.stem}.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    typer.echo(f"Preview saved: {target}")
    if open:
        typer.launch(str(target))


@app.command()
def translate(
    url: str,
    lang: str = typer.Option("es", "--lang", help="Target language."),
    source_lang: Optional[str] = typer.Option(
        None, "--source-lang", help="Override source language."
    ),
    out: Optional[Path] = None,
    engine: str = typer.Option(
        "libretranslate", "--engine", help="Translation engine."
    ),
) -> None:
    """Create an initial translation from a source Wikipedia URL."""
    _ensure_env()
    src_lang, title = wiki.parse_wiki_url(url)
    if source_lang:
        src_lang = source_lang

    page = wiki.fetch_wikitext(src_lang, title)

    if engine == "none":
        translated = page.wikitext
    elif engine == "libretranslate":
        translator = wiki.make_translator(src_lang, lang)
        translated = wiki.translate_wikitext(page.wikitext, translator)
    else:
        raise typer.BadParameter(f"Unsupported engine: {engine}")

    target = out or wiki.default_article_path(lang, page.title)
    wiki.save_wikitext(target, translated)
    typer.echo(f"Translated draft saved: {target}")


@app.command()
def publish(
    path: Path,
    lang: str = typer.Option("es", "--lang", help="Target wiki language."),
    title: Optional[str] = typer.Option(None, "--title", help="Override page title."),
    summary: str = typer.Option("Update via wkp", "--summary"),
    minor: bool = typer.Option(False, "--minor"),
) -> None:
    """Publish a local wikitext file to Wikipedia."""
    _ensure_env()
    username, password = wiki.load_credentials()
    if not username or not password:
        raise typer.BadParameter("Missing WKP_USERNAME/WKP_PASSWORD in environment")

    resolved_title = title or wiki.title_from_path(path)
    wikitext = wiki.load_wikitext(path)

    wiki.publish_page(
        lang=lang,
        title=resolved_title,
        wikitext=wikitext,
        username=username,
        password=password,
        summary=summary,
        minor=minor,
    )
    typer.echo(f"Published: {resolved_title} ({lang})")


if __name__ == "__main__":
    app()
