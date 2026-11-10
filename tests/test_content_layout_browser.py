"""Amendment 02 D: grammar must reach real CSS layout/paint, not only resolve.

An authored consumer uses the existing public listing-card/slot hooks. Only the
real exported styles supply presentation. This tests the export/render boundary;
the separate content-page cases cover vocabulary-owned page markup. Oracles are
CSS grid arithmetic, authored image pixels and direct 768/1280 token thresholds.
"""
import io

from PIL import Image, ImageDraw
import pytest

from tests.content_browser_support import loaded_images
from tests.m1_support import token
from tests.test_resolution import resolved
from tests.test_validation import VALID_VARIANT, set_variant

pytestmark = pytest.mark.browser


def configure(language):
    for name, value in (("canvas", 600), ("image", 120), ("gutter", 16), ("zero", 0)):
        token(language, "space", name, "dimension", f"{value}px")
    root = language["components"]["listing-card"]
    root["properties"] = {"display": "grid", "width": "{space.canvas}", "max-width": "{space.canvas}",
        "grid-template-columns": "1fr", "column-gap": "{space.gutter}", "row-gap": "{space.small}",
        "padding": "{space.zero}", "border-width": "{space.zero}", "margin-inline": "auto", "align-items": "start"}
    for name in ("media", "title", "location", "rating", "price", "action"):
        root["slots"][name] = {"properties": {"margin-block": "{space.zero}", "padding": "{space.zero}",
            "border-width": "{space.zero}", "grid-column": "auto", "grid-row": "auto"}}
    root["slots"]["media"]["properties"]["width"] = "{space.image}"
    return root


def consumer(library, language, out, title="A title", part=False):
    library.write(language)
    library.validate()
    library.cli("export", language["id"], "--adapter", "generic", "--out", out)
    picture = Image.new("RGB", (120, 40), "#ff0000")
    draw = ImageDraw.Draw(picture)
    draw.rectangle((40, 0, 79, 39), fill="#00ff00")
    draw.rectangle((80, 0, 119, 39), fill="#0000ff")
    picture.save(out / "stripes.png")
    slots = ('<img id="media" data-kd-slot="listing-card.media" src="stripes.png" alt="Three synthetic stripes">'
             f'<h2 id="title" data-kd-slot="listing-card.title">{title}</h2>'
             '<p id="location" data-kd-slot="listing-card.location">A location</p>'
             '<p id="rating" data-kd-slot="listing-card.rating">A rating</p>'
             '<p id="price" data-kd-slot="listing-card.price">A value</p>'
             '<a id="action" data-kd-slot="listing-card.action" href="#title">Read</a>')
    if part:
        slots = '<div data-kd-part="stack">' + slots + '</div>'
    path = out / "probe.html"
    path.write_text('<!doctype html><html><head><meta charset="utf-8">'
                   '<link rel="stylesheet" href="tokens.css"><link rel="stylesheet" href="roles.css">'
                   '</head><body><article id="grid" data-kd-construct="listing-card">' + slots + '</article></body></html>')
    return path


def box(page, identity):
    result = page.locator("#" + identity).bounding_box()
    assert result and result["width"] > 0 and result["height"] > 0
    return result


def near(actual, expected):
    # One CSS pixel bounds grid subpixel rounding, not a timing/retry window.
    assert abs(actual - expected) <= 1, (actual, expected)


def test_grid_tracks_and_gaps_apply_exactly_at_breakpoints(library, language, tmp_path, page):
    configure(language)
    language["overrides"] = [
        {"scope": "listing-card@md", "properties": {"grid-template-columns": "repeat(2, 1fr)"}, "reason": "Two columns from 768px"},
        {"scope": "listing-card@lg", "properties": {"grid-template-columns": "repeat(3, 1fr)"}, "reason": "Three columns from 1280px"}]
    path = consumer(library, language, tmp_path / "export")
    for width, columns, bp in ((767, 1, None), (768, 2, "md"), (769, 2, "md"), (1279, 2, "md"), (1280, 3, "lg")):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(path.as_uri())
        loaded_images(page)
        grid, image, title = (box(page, n) for n in ("grid", "media", "title"))
        near(grid["width"], 600)
        track = (600 - (columns-1)*16)/columns
        near(title["width"], track)
        if columns == 1:
            near(title["x"], image["x"])
            near(title["y"] - image["y"] - image["height"], 8)
        else:
            near(title["x"] - grid["x"], track + 16)
            near(title["y"], image["y"])
            # First item on row two starts after the tallest first-row item + 8.
            row2 = box(page, "location" if columns == 2 else "rating")
            near(row2["y"] - max(box(page, n)["y"] + box(page, n)["height"] for n in
                 (("media", "title") if columns == 2 else ("media", "title", "location"))), 8)
        result = resolved(library, "listing-card", breakpoint=bp)
        assert result["column-gap"]["value"] == "16px" and result["row-gap"]["value"] == "8px"
        assert result["grid-template-columns"]["value"].replace(" ", "") == ("1fr" if columns == 1 else f"repeat({columns},1fr)")


def test_grid_spans_change_occupied_rows_and_columns(library, language, tmp_path, page):
    root = configure(language)
    root["properties"]["grid-template-columns"] = "repeat(3, 1fr)"
    root["slots"]["media"]["properties"].update({"width": "{space.image}", "grid-column": "span 2", "grid-row": "span 2"})
    path = consumer(library, language, tmp_path / "export")
    page.goto(path.as_uri())
    loaded_images(page)
    grid, image, title, location, rating = (box(page, n) for n in ("grid", "media", "title", "location", "rating"))
    track = (600-32)/3
    near(title["x"] - grid["x"], 2*(track+16))
    near(title["y"], image["y"])
    near(location["x"], title["x"])
    assert location["y"] > title["y"]
    near(rating["x"], grid["x"])
    assert rating["y"] >= image["y"] + image["height"] + 7


def test_alignment_aspect_image_crop_shadow_and_margin_have_rendered_effect(library, language, tmp_path, page):
    root = configure(language)
    root["properties"].update({"grid-template-columns": "repeat(2, 1fr)", "row-gap": "{space.gutter}"})
    shadow = token(language, "shadow", "probe", "shadow", {"color": "#000000", "offsetX": "0px", "offsetY": "8px", "blur": "0px", "spread": "0px"})
    root["slots"]["media"]["properties"].update({"aspect-ratio": "2 / 1", "object-fit": "cover",
        "object-position": "left", "align-self": "end", "justify-self": "center", "box-shadow": shadow,
        "background-color": "{color.paper}"})
    language["overrides"] = [
        {"scope": "listing-card.media@md", "properties": {"object-position": "right"}, "reason": "Right crop from md"},
        {"scope": "listing-card.media@lg", "properties": {"object-fit": "contain"}, "reason": "Contain at lg"}]
    path = consumer(library, language, tmp_path / "export", title="Long title " * 22)
    for width, expected_pixel in ((767, (255, 0, 0)), (768, (0, 255, 0)), (1280, None)):
        page.set_viewport_size({"width": width, "height": 1100})
        page.goto(path.as_uri())
        loaded_images(page)
        grid, media, title = (box(page, n) for n in ("grid", "media", "title"))
        near(grid["x"] + grid["width"]/2, width/2)
        near(media["width"], 120)
        near(media["height"], 60)
        near(media["x"] - grid["x"], ((600-16)/2 - 120)/2)
        near(media["y"] + media["height"], title["y"] + title["height"])
        pixels = Image.open(io.BytesIO(page.locator("#media").screenshot())).convert("RGB")
        if expected_pixel:
            assert pixels.getpixel((10, 30)) == expected_pixel
        else:
            assert pixels.getpixel((60, 2)) == (255, 255, 255), "contain must preserve a letterbox"
        paint = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        assert paint.getpixel((round(media["x"] + 10), round(media["y"] + media["height"] + 4))) == (0, 0, 0), "Missing actual shadow paint"
    result = resolved(library, "listing-card.media")
    for prop in ("align-self", "justify-self", "aspect-ratio", "object-fit", "object-position", "box-shadow"):
        assert result[prop]["source"] == "component:listing-card.media"
        assert result[prop]["value"]


def test_part_breakpoint_overrides_change_actual_layout(library, language, tmp_path, page):
    root = configure(language)
    set_variant(language, VALID_VARIANT)
    root["properties"]["display"] = "block"
    root["parts"] = {"stack": {"display": "grid", "grid-template-columns": "1fr", "column-gap": "{space.gutter}"}}
    language["overrides"] = [{"scope": "listing-card~stack@md", "properties": {"grid-template-columns": "repeat(2, 1fr)"}, "reason": "Part columns at md"}]
    path = consumer(library, language, tmp_path / "export", part=True)
    for width in (767, 768):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(path.as_uri())
        loaded_images(page)
        image, title = box(page, "media"), box(page, "title")
        if width == 767:
            near(image["x"], title["x"])
            assert title["y"] >= image["y"] + image["height"]
        else:
            near(title["x"] - image["x"], (600-16)/2+16)
            near(image["y"], title["y"])
