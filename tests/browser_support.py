"""Chromium assertions at the rendered boundary, using only public annotation hooks."""

from playwright.sync_api import expect


def assert_color(locator, expected):
    assert locator.count() > 0, "No rendered target reached"
    for i in range(locator.count()):
        expect(locator.nth(i)).to_have_css("color", expected)


def frame_at(page, path):
    frames = page.locator("iframe")
    matches = [frames.nth(i) for i in range(frames.count())
               if frames.nth(i).evaluate("e => new URL(e.src).pathname") == path]
    assert len(matches) == 1, (path, len(matches))
    return matches[0]


def form_at(page, path):
    forms = page.locator("form")
    matches = [forms.nth(i) for i in range(forms.count())
               if forms.nth(i).evaluate("e => new URL(e.action).pathname") == path]
    assert len(matches) == 1, (path, len(matches))
    return matches[0]


def link_at(page, path):
    links = page.locator("a[href]")
    matches = [links.nth(i) for i in range(links.count())
               if links.nth(i).evaluate("e => new URL(e.href).pathname") == path]
    assert matches, path
    return matches[0]


def semantic_view(page):
    """Relational semantic observation: no baseline captured from an implementation."""
    return {
        "accessibility": page.locator("body").aria_snapshot(),
        "text": " ".join(page.locator("body").inner_text().split()),
        "slots": page.locator("[data-kd-slot]").evaluate_all("""els => els.map(e => ({
            slot: e.dataset.kdSlot, role: e.dataset.kdRole, emphasis: e.dataset.kdEmphasis,
            element: e.tagName, text: e.textContent.trim().replace(/\\s+/g, ' ')
        }))"""),
        "headings": page.locator("h1,h2,h3,h4,h5,h6").evaluate_all(
            "els => els.map(e => [e.tagName,e.textContent.trim()])"),
        "focus_order": page.locator("a[href],button,input,select,textarea,[tabindex]").evaluate_all("""els =>
            els.map(e => [e.tagName,e.getAttribute('href'),e.getAttribute('type'),
                e.getAttribute('tabindex'),e.getAttribute('aria-label'),e.textContent.trim()])"""),
    }


def focus_style(locator):
    return locator.evaluate("""e => {
      const s = getComputedStyle(e);
      return {outline: s.outlineStyle, width: s.outlineWidth, color: s.outlineColor,
        shadow: s.boxShadow, background: s.backgroundColor, border: s.borderColor,
        decoration: s.textDecorationLine, text: s.color};
    }""")


def assert_visible_focus(before, after):
    """Visible CSS focus evidence; no claim about WCAG contrast (deferred to M1)."""
    outline = (after["outline"] not in {"none", "hidden"} and float(after["width"].removesuffix("px")) > 0
               and after["color"] not in {"transparent", "rgba(0, 0, 0, 0)"})
    shadow = after["shadow"] != "none" and after["shadow"] != before["shadow"]
    treatment = any(after[k] != before[k] for k in ("background", "border", "text", "decoration"))
    assert outline or shadow or treatment, ("No visible keyboard focus treatment", before, after)
