"""Independent rendered visibility criteria from the Validator's beach-session review.

The numerical cutoffs below are tester-chosen operational criteria, not WCAG
thresholds. They reject localized/noisy changes while allowing type/shape choices
that naturally change less paint than a new page background.
"""

import colorsys
from io import BytesIO
import re

from PIL import Image, ImageChops, ImageFilter, ImageOps

from tests.m3_render_support import ALLOWED, assert_whimsy, numeric_values, rgba, pixels

PAIR_CHANGED_SHARE = 0.01
MOOD_CHANGED_SHARE = 0.03


def screenshot_image(data):
    with Image.open(BytesIO(data)) as picture:
        return picture.convert("RGB")


def changed_share(first, second, normalize=False):
    """Ignore sub-16/255 channel changes after a half-pixel anti-noise blur.

    Full-page pairs use only their common extent, at identical width: changing
    screenshot height or appending white space cannot alone earn a difference.
    Mood specimens get a common canvas, preserving each item's aspect ratio.
    """
    if normalize:
        normalized = []
        for picture in (first, second):
            canvas = Image.new("RGB", (320, 180), "white")
            fitted = ImageOps.contain(picture, canvas.size, Image.Resampling.LANCZOS)
            canvas.paste(fitted, ((320 - fitted.width) // 2, (180 - fitted.height) // 2))
            normalized.append(canvas)
        first, second = normalized
    else:
        assert first.width == second.width, "A/B screenshots must use the same CSS viewport and device scale"
        extent = (0, 0, first.width, min(first.height, second.height))
        first, second = first.crop(extent), second.crop(extent)
    diff = ImageChops.difference(first.filter(ImageFilter.GaussianBlur(0.5)),
                                second.filter(ImageFilter.GaussianBlur(0.5)))
    red, green, blue = diff.split()
    maximum = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return sum(maximum.histogram()[16:]) / (maximum.width * maximum.height)


def prominent(row, viewport_area, dimension):
    area = row["box"]["width"] * row["box"]["height"]
    heading = (row["tag"] in {"H1", "H2", "H3"} or row["role"] in {"title", "subtitle"}) and pixels(row["css"]["font-size"]) >= 24
    action = row["role"] == "action" and row["emphasis"] == "primary" and row["box"]["width"] >= 24 and row["box"]["height"] >= 24
    # Large means >=10% of one viewport. Typography needs a text specimen;
    # inheriting a font on a large otherwise empty wrapper is insufficient.
    paint = rgba(row["css"]["background-color"])[3] > 0 or row["css"]["background-image"] != "none"
    surface = area >= viewport_area * 0.1 and (paint or dimension == "density")
    return (heading and bool(row["text"])) or action or (surface and dimension not in {"type-pairing", "type-scale", "formality"})


def assert_prominent_dimension_effects(first, second, dimensions, viewport_area, first_image, second_image):
    for dimension in dimensions:
        # For whimsy, the effect belongs to attention paint; for formality, title
        # tracking supplies prominence even when only small labels change case.
        candidates = [(a, b) for a, b in zip(first, second)
                      if prominent(a, viewport_area, dimension) or prominent(b, viewport_area, dimension)]
        visible_effect = False
        for a, b in candidates:
            changed = {prop for prop in ALLOWED[dimension] if a["css"][prop] != b["css"][prop]}
            text_or_action = a["role"] in {"title", "subtitle"} or a["tag"] in {"H1", "H2", "H3"} or (
                a["role"] == "action" and a["emphasis"] == "primary")
            if not text_or_action and dimension in {"hue-family", "saturation", "value-contrast", "whimsy"}:
                # An inherited foreground on a large wrapper isn't a colored
                # surface. Require the container's own background/boundary paint.
                changed &= {"background-color", "background-image", "border-color"}
                if "border-color" in changed and (a["css"]["border-style"] == "none" or max(numeric_values(a["css"]["border-width"])) == 0):
                    changed.remove("border-color")
            if not changed:
                continue
            before, after = crop_box(first_image, a), crop_box(second_image, b)
            # Computed-only changes (e.g. white rounded corners on white) do
            # not demonstrate a prominent visual effect. Also require paint.
            if before is not None and after is not None and changed_share(before, after, normalize=True) >= 0.005:
                visible_effect = True
                break
        assert visible_effect, (
            "Dimension only changed small/non-prominent content", dimension)


def beach_pixel_share(picture):
    """Use 90–255 degrees, >=20/255 channel spread: nearly white isn't blue paint."""
    # Downsampling bounds cost; areas, not isolated antialiased text pixels, are
    # the oracle here. The broad hue interval matches the existing seed test.
    reduced = picture.copy()
    reduced.thumbnail((256, 256))
    count = 0
    for r, g, b in reduced.convert("RGB").getdata():
        hue, _, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        count += 90 <= hue * 360 <= 255 and saturation >= 0.2 and max(r, g, b) - min(r, g, b) >= 20
    return count / (reduced.width * reduced.height)


def crop_box(picture, row):
    box = row["box"]
    left, top = max(0, round(box["x"])), max(0, round(box["y"]))
    right = min(picture.width, round(box["x"] + box["width"]))
    bottom = min(picture.height, round(box["y"] + box["height"]))
    return picture.crop((left, top, right, bottom)) if right > left and bottom > top else None


def assert_beach_paint(rows, picture, viewport_area):
    actions = [row for row in rows if row["role"] == "action" and row["emphasis"] == "primary"
               and row["box"]["width"] >= 24 and row["box"]["height"] >= 24]
    assert actions, "The beach language needs a prominent primary action"
    assert any((crop := crop_box(picture, row)) is not None and beach_pixel_share(crop) >= 0.01 for row in actions), (
        "No primary action actually paints a blue/green/turquoise color")
    surfaces = [row for row in rows if row["role"] != "media"
                and row["box"]["width"] * row["box"]["height"] >= viewport_area * 0.1
                and (rgba(row["css"]["background-color"])[3] > 0 or row["css"]["background-image"] != "none")]
    assert any((crop := crop_box(picture, row)) is not None and beach_pixel_share(crop) >= 0.5 for row in surfaces), (
        "No large surface is predominantly blue/green/turquoise; small accents do not satisfy the brief")
    labels = [row for row in rows if row["role"] == "label" and row["text"]]
    assert labels and all(row["css"]["text-transform"] != "uppercase" for row in labels), "Casual beach seeds rendered formal uppercase labels"
    assert_whimsy(rows, 1)  # The requested whimsical seed needs the >=60-degree relation.


def assert_moodboard_variety(page):
    pins = page.get_by_role("button", name=re.compile(r"\bpin\b", re.I))
    pictures = []
    for pin in pins.all():
        if not pin.is_visible():
            continue
        # Associate a specimen with its own pin action through DOM containment,
        # without guessing a private class, route, mood item id or label phrase.
        handle = pin.evaluate_handle("""button => {
          const visible = e => { const r=e.getBoundingClientRect(),s=getComputedStyle(e);
            return r.width>=16 && r.height>=16 && s.visibility!=='hidden' && s.display!=='none'; };
          for (let e=button.parentElement; e && e!==document.body; e=e.parentElement) {
            const pins=[...e.querySelectorAll('button,input[type=submit]')].filter(b=>/\\bpin\\b/i.test(b.getAttribute('aria-label') || b.textContent || b.value));
            if(pins.length>1) return null;
            const samples=[...e.querySelectorAll('img,iframe,svg,[data-kd-construct]')].filter(visible);
            if(samples.length) return samples.sort((a,b)=>{
              const x=a.getBoundingClientRect(),y=b.getBoundingClientRect(); return y.width*y.height-x.width*x.height;
            })[0];
            const css=[...e.querySelectorAll('div,span,p,figure')].filter(n=>visible(n) && !n.closest('button') && !n.querySelector('button,input,select'));
            if(css.some(n=>getComputedStyle(n).backgroundColor!=='rgba(0, 0, 0, 0)' || parseFloat(getComputedStyle(n).fontSize)>=20))
              return e;
          }
          return null;
        }""")
        try:
            sample = handle.as_element()
            assert sample is not None, "Pin item has no associated visible specimen"
            pictures.append(screenshot_image(sample.screenshot(timeout=5000, animations="disabled", caret="hide")))
        finally:
            handle.dispose()
    assert len(pictures) >= 3, "Mood board must offer multiple visual directions"
    # Three mutually distinguishable examples allow intentional related items,
    # but repeated near-identical thumbnails cannot satisfy the board's variety.
    distances = {(i, j): changed_share(a, b, normalize=True)
                 for i, a in enumerate(pictures) for j, b in enumerate(pictures) if i < j}
    assert any(min(distances[i, j], distances[i, k], distances[j, k]) >= MOOD_CHANGED_SHARE
               for i in range(len(pictures)) for j in range(i+1, len(pictures)) for k in range(j+1, len(pictures))), (
        "Mood board lacks three visibly distinct specimens", distances)


def assert_neutral_default_copy(page):
    # These are user-visible strings, not HTML paths, vocabulary slot ids or CSS.
    # The vocabulary may retain listing-card ids while its default sample copy
    # remains reusable for articles, teams and other domains.
    copy = [page.locator("body").inner_text()]
    copy += page.locator("[aria-label],[placeholder],img[alt]").evaluate_all("""els => els.filter(e => {
      const r=e.getBoundingClientRect(); return r.width>0 && r.height>0 && getComputedStyle(e).visibility!=='hidden';
    }).flatMap(e => ['aria-label','placeholder','alt'].map(a => e.getAttribute(a) || ''))""")
    depicted = page.locator("[data-kd-construct][data-kd-state]").evaluate_all(
        "els => els.map(e => [e.dataset.kdConstruct, e.dataset.kdState])")
    captions = [re.compile(r"^" + re.escape(construct) + r"(?:\s*(?:[·:—–/\-]\s*)?" + re.escape(state) + r")?$", re.I)
                for construct, state in depicted]
    # Only complete identifier captions for states actually depicted are exempt.
    # Keep scanning all other sample prose, including copy on those same cards.
    copy = ["\n".join(line for line in text.splitlines()
                      if not any(caption.fullmatch(line.strip()) for caption in captions)) for text in copy]
    domain = re.compile(r"\b(?:listings?|bookings?|ratings?|destinations?)\b|\bbook\s+(?:now|this|your)\b|"
                        r"\breserve\s+(?:this|your)\b|\bper\s+night\b|\b\d+\s+(?:beds?|bedrooms?|guests?)\b", re.I)
    offenders = [text for text in copy if domain.search(text)]
    assert not offenders, ("Domain-specific default sample copy", offenders)
