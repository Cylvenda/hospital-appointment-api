import bleach

ALLOWED_TAGS = [
    "p", "b", "i", "u", "strong", "em", "ul", "ol", "li",
    "a", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "pre", "code", "hr", "span", "div",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "span": ["class"],
    "div": ["class"],
}

ALLOWED_STYLES = []


def sanitize_html(content: str) -> str:
    if not content:
        return content
    return bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        styles=ALLOWED_STYLES,
        strip=True,
    )
