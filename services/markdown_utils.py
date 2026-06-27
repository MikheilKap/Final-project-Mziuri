import markdown
import bleach

ALLOWED_TAGS = [
    "p", "strong", "em", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "a", "br", "hr", "code", "pre", "blockquote",
]
ALLOWED_ATTRIBUTES = {"a": ["href", "target", "rel"]}


def format_ai_response(text: str) -> str:
    html = markdown.markdown(text, extensions=["extra", "nl2br", "sane_lists"])
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)
