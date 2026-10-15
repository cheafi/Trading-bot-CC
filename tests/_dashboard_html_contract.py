"""Read Alpine bindings independently of layout and JS formatting."""

from html.parser import HTMLParser
from pathlib import Path


class _Bindings(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.elements: list[dict[str, str | None]] = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append(dict(attrs))


def bindings(path: Path, attribute: str) -> list[str]:
    """Return decoded expressions, including HTML-escaped && and quotes."""
    return [
        value
        for element in _Bindings(path.read_text(encoding="utf-8")).elements
        if (value := element.get(attribute)) is not None
    ]
