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


def reveal_preview_right_edge(frame):
    """Move real scroll positions only where scrolling is available to the user.

    Never scroll overflow:hidden/clip ancestors: doing so can conceal the product
    defect, since hidden content can be programmatically scrollable. No styles or
    layout are changed. Hit testing checks the final visible edge, not scrollWidth.
    """
    return frame.evaluate("""async frame => {
      const root = document.scrollingElement;
      const rootStyle = getComputedStyle(document.documentElement);
      const bodyStyle = getComputedStyle(document.body);
      const scrollable = value => ['auto', 'scroll', 'overlay'].includes(value);
      const contentBox = node => {
        const r = node.getBoundingClientRect();
        const sx = node.offsetWidth ? r.width / node.offsetWidth : 1;
        const sy = node.offsetHeight ? r.height / node.offsetHeight : 1;
        return {left: r.left + node.clientLeft * sx, top: r.top + node.clientTop * sy,
          right: r.left + (node.clientLeft + node.clientWidth) * sx,
          bottom: r.top + (node.clientTop + node.clientHeight) * sy, sx, sy};
      };
      const viewport = node => {
        if (node === root) return {left: 0, top: 0,
          right: document.documentElement.clientWidth,
          bottom: document.documentElement.clientHeight, sx: 1, sy: 1};
        return contentBox(node);
      };
      for (let node = frame.parentElement; node; node = node.parentElement) {
        const style = getComputedStyle(node), v = viewport(node);
        const rootX = rootStyle.overflowX === 'visible' ? bodyStyle.overflowX : rootStyle.overflowX;
        const rootY = rootStyle.overflowY === 'visible' ? bodyStyle.overflowY : rootStyle.overflowY;
        const canX = node === root ? !['hidden', 'clip'].includes(rootX) : scrollable(style.overflowX);
        const canY = node === root ? !['hidden', 'clip'].includes(rootY) : scrollable(style.overflowY);
        const r = contentBox(frame);
        const right = r.right;
        const y = r.top + Math.min(20, (r.bottom - r.top) / 2);
        const dx = right > v.right ? right - v.right : right < v.left ? right - v.left - 1 : 0;
        const dy = y >= v.bottom ? y - v.bottom + 1 : y < v.top ? y - v.top : 0;
        node.scrollTo({left: node.scrollLeft + (canX && v.sx > 0 ? dx / v.sx : 0),
          top: node.scrollTop + (canY && v.sy > 0 ? dy / v.sy : 0), behavior: 'instant'});
      }
      // Await the browser's next rendering opportunity, not an elapsed-time delay.
      await new Promise(requestAnimationFrame);
      const r = contentBox(frame);
      const x = r.right - Math.min(0.5, (r.right - r.left) / 2);
      let top = Math.max(0, r.top);
      let bottom = Math.min(document.documentElement.clientHeight, r.bottom);
      for (let node = frame.parentElement; node && node !== root; node = node.parentElement) {
        if (getComputedStyle(node).overflowY !== 'visible') {
          const v = viewport(node);
          top = Math.max(top, v.top);
          bottom = Math.min(bottom, v.bottom);
        }
      }
      const y = (top + bottom) / 2;
      return {clientWidth: frame.clientWidth, edgeX: x, edgeY: y,
        visibleHeight: bottom - top, windowWidth: document.documentElement.clientWidth,
        edgeHitsFrame: bottom > top && document.elementFromPoint(x, y) === frame};
    }""")


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
