from __future__ import annotations

from typing import Any

import requests


def extract_url(url: str, timeout: int = 20) -> dict[str, Any]:
    try:
        import trafilatura
    except Exception:
        trafilatura = None

    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": "ensemble-buy-side-research/0.1"})
        response.raise_for_status()
    except Exception as exc:
        return {"url": url, "text": "", "error": str(exc)}

    html = response.text
    text = ""
    metadata: dict[str, Any] = {}
    if trafilatura is not None:
        try:
            text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
            meta = trafilatura.extract_metadata(html)
            if meta:
                metadata = {
                    "title": meta.title,
                    "date": meta.date,
                    "author": meta.author,
                    "sitename": meta.sitename,
                }
        except Exception:
            text = ""
    if not text:
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(" ", strip=True)
        except Exception:
            text = html[:5000]
    return {"url": url, "text": text, "metadata": metadata}
