"""Rendered observations, independent of product checks and implementation CSS."""
import re


def loaded_images(page):
    images = page.locator("img")
    assert images.count(), "No images reached the rendered page"
    for index in range(images.count()):
        image = images.nth(index)
        image.scroll_into_view_if_needed()
        # decode() waits on an actual browser completion signal, including lazy
        # images after scrolling. Native promises work in no-JavaScript contexts.
        image.evaluate("e => e.decode()")
        assert image.evaluate("e => e.complete && e.naturalWidth > 0 && e.naturalHeight > 0")
        assert image.bounding_box()["width"] > 0 and image.bounding_box()["height"] > 0
    page.evaluate("window.scrollTo(0, 0)")
    page.evaluate("document.fonts.ready")


def assert_visible_text_and_controls(page):
    failures = page.evaluate(r"""() => {
      const failures = [];
      function clipped(rect, element) {
        let left=rect.left, right=rect.right, top=rect.top, bottom=rect.bottom;
        for(let n=element; n; n=n.parentElement) {
          const s=getComputedStyle(n), r=n.getBoundingClientRect();
          if(s.display==='none' || s.visibility!=='visible' || Number(s.opacity)===0) return true;
          if(['hidden','clip','scroll','auto'].includes(s.overflowX)) {left=Math.max(left,r.left);right=Math.min(right,r.right);}
          if(['hidden','clip','scroll','auto'].includes(s.overflowY)) {top=Math.max(top,r.top);bottom=Math.min(bottom,r.bottom);}
        }
        return right<=left || bottom<=top;
      }
      const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
      while(walker.nextNode()) {
        const node=walker.currentNode, parent=node.parentElement;
        if(!node.textContent.trim() || parent.closest('style,script')) continue;
        const range=document.createRange(); range.selectNodeContents(node);
        const rects=[...range.getClientRects()];
        if(!rects.some(r=>r.width>0 && r.height>0 && !clipped(r,parent))) failures.push(node.textContent);
      }
      for(const e of document.querySelectorAll('a[href],button,input,select,textarea')) {
        if(![...e.getClientRects()].some(r=>r.width>0 && r.height>0 && !clipped(r,e))) failures.push(e.outerHTML);
      }
      return failures;
    }""")
    assert not failures, ("Content or controls have no visible unclipped box", failures)


def visible_copy(content):
    """Text explicitly belonging in the body; page metadata/alt/hrefs are not prose."""
    def inline(value):
        if isinstance(value, str):
            return [value]
        return [run if isinstance(run, str) else run["text"] for run in value]
    values = [n["text"] for n in content["site"].get("nav", [])]
    for block in content["blocks"]:
        values.extend(block[k] for k in ("title", "eyebrow") if k in block)
        for key in ("body", "intro"):
            if key in block:
                values.extend(inline(block[key]))
        values.extend(a["text"] for a in block.get("actions", []))
        for entry in block.get("content", []):
            if "paragraph" in entry:
                values.extend(inline(entry["paragraph"]))
            if "list" in entry:
                for item in entry["list"]["items"]:
                    values.extend(inline(item))
            if "quote" in entry:
                values.extend(inline(entry["quote"]["text"]))
                values.append(entry["quote"]["cite"])
            if "media" in entry:
                values.extend(entry["media"][k] for k in ("caption", "credit") if k in entry["media"])
        for item in block.get("items", []):
            values.extend(item[k] for k in ("title", "eyebrow") if k in item)
            values.extend(inline(item.get("body", "")))
            values.extend(v for fact in item.get("facts", []) for v in fact.values())
            if "action" in item:
                values.append(item["action"]["text"])
    values.extend(inline(content["footer"]["text"]))
    values.extend(a["text"] for a in content["footer"].get("links", []))
    return [v for v in values if v.strip()]


def rgba(value):
    channels = [float(n) for n in re.findall(r"[\d.]+", value)]
    assert value.startswith(("rgb(", "rgba(")) and len(channels) in (3, 4), value
    return channels[:3], channels[3] if len(channels) == 4 else 1


def composite(foreground, background, alpha):
    return [a * alpha + b * (1-alpha) for a, b in zip(foreground, background)]


def luminance(rgb):
    normalized = [c/255 for c in rgb]
    linear = [c/12.92 if c <= 0.04045 else ((c+0.055)/1.055)**2.4 for c in normalized]
    return sum(c*w for c,w in zip(linear, (0.2126, 0.7152, 0.0722)))


def assert_text_contrast(page):
    samples = page.evaluate("""() => {
      const samples=[], walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
      while(walker.nextNode()) {
        const n=walker.currentNode, e=n.parentElement;
        if(!n.textContent.trim() || e.closest('style,script')) continue;
        const range=document.createRange();range.selectNodeContents(n);
        if(![...range.getClientRects()].some(r=>r.width && r.height)) continue;
        const layers=[];
        for(let p=e;p;p=p.parentElement) {
          const s=getComputedStyle(p);
          layers.unshift({background:s.backgroundColor,image:s.backgroundImage,opacity:s.opacity});
        }
        const s=getComputedStyle(e);
        samples.push({text:n.textContent,color:s.color,size:parseFloat(s.fontSize),weight:parseFloat(s.fontWeight),layers});
      }
      return samples;
    }""")
    assert samples
    for sample in samples:
        # This cannot prove contrast over a gradient/image or group opacity.
        # Surface an evidence gap rather than substitute a fictitious solid bg.
        layers = sample["layers"]
        # A solid opaque descendant covers ancestor background imagery. Retain
        # group opacity from every ancestor because it still affects the group.
        opaque = [i for i, layer in enumerate(layers) if rgba(layer["background"])[1] == 1]
        contributing = layers[opaque[-1]:] if opaque else layers
        assert all(layer["image"] == "none" for layer in contributing) and all(float(layer["opacity"]) == 1 for layer in layers), (
            "Contrast evidence gap: image/gradient/group opacity requires rendered pixel assessment", sample)
        background = [255, 255, 255]  # Chromium default canvas behind transparent root.
        for layer in contributing:
            color, alpha = rgba(layer["background"])
            background = composite(color, background, alpha)
        foreground, alpha = rgba(sample["color"])
        foreground = composite(foreground, background, alpha)
        low, high = sorted((luminance(foreground), luminance(background)))
        ratio = (high + .05)/(low + .05)
        threshold = 3 if sample["size"] >= 24 or (sample["size"] >= 56/3 and sample["weight"] >= 700) else 4.5
        assert ratio >= threshold, (sample["text"], ratio, threshold, foreground, background)
