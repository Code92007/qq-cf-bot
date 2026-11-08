"""Sanitized Markdown that leaves LaTeX intact for browser rendering."""
from __future__ import annotations

import html
import re
from urllib.parse import urljoin


def render_markdown(source, *, source_url="", allow_images=False, allow_html=True, line_breaks=False):
    import markdown
    from .webapp import _HTMLSanitizer

    class Sanitizer(_HTMLSanitizer):
        allowed_tags = (_HTMLSanitizer.allowed_tags - {"img"}) | {"h1", "h2", "h3", "h4", "h5", "h6", "hr", "del"}
        void_tags = {"br", "hr"}
        if allow_images:
            allowed_tags = allowed_tags | {"img"}
            void_tags = void_tags | {"img"}

        def handle_starttag(self, tag, attrs):
            if source_url:
                attrs = [(name, urljoin(source_url, value) if value and
                          ((tag == "img" and name == "src") or (tag == "a" and name == "href"))
                          else value) for name, value in attrs]
            super().handle_starttag(tag, attrs)

    # Protect formulas from Markdown's escaping and emphasis rules; code stays literal.
    formulas = []

    def stash(match):
        if match[1]:
            return match[0]
        formulas.append(match[0])
        return f"RICHTEXTMATH{len(formulas) - 1}TOKEN"

    protected = re.sub(r"(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)|(?<!\\)(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$|\\\[[\s\S]*?\\\]|\\\(.+?\\\))", stash, source)
    extensions = ["extra", "sane_lists"] + (["nl2br"] if line_breaks else [])
    renderer = markdown.Markdown(extensions=extensions, output_format="html5")
    # Markdown versions differ on punctuation next to closing emphasis. Cached
    # statements commonly contain labels such as **时间限制：**2 秒.
    renderer.inlinePatterns.register(markdown.inlinepatterns.SimpleTagInlineProcessor(
        r"(\*\*)([^*\n]+[：:])\*\*(?=\S)", "strong"), "adjacent_label", 175)
    if not allow_html:
        # Editorial inequalities such as x<a must never be mistaken for an HTML tag.
        renderer.preprocessors.deregister("html_block")
        renderer.inlinePatterns.deregister("html")
    rendered = renderer.convert(protected)
    for index, formula in enumerate(formulas):
        rendered = rendered.replace(f"RICHTEXTMATH{index}TOKEN", html.escape(formula))
    sanitizer = Sanitizer()
    sanitizer.feed(rendered)
    sanitizer.close()
    return sanitizer.result
