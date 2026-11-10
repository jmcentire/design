"""Amendment 09 clarification: navigation paint comes from its band, not a button.

The authored source provides both colour oracles. Real HTTP capture, offline
draft/save and ordinary sample rendering must preserve them independently.
"""
import pytest

from tests.content_browser_support import composite, rgba
from tests.support import PAGES
from tests.test_composition_ingest import configure_capture, css, derive
from tests.test_composition_role_transfer import assert_color
from tests.test_composition_shipped import composition_report, assert_composition_passes

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(600)]
WIDTHS = (375, 1280)


def assert_transparent(element):
    values = css(element, ["background-color", "background-image"])
    assert rgba(values["background-color"])[1] == 0, values
    assert values["background-image"] == "none", values


def effective_background(layers):
    """Composite ancestor-to-element solid fills over the browser's white canvas."""
    assert layers and all(float(layer["opacity"]) == 1 for layer in layers), layers
    opaque = [i for i, layer in enumerate(layers) if rgba(layer["background"])[1] == 1]
    contributing = layers[opaque[-1]:] if opaque else layers
    assert all(layer["image"] == "none" for layer in contributing), layers
    background = [255, 255, 255]
    for layer in contributing:
        color, alpha = rgba(layer["background"])
        background = composite(color, background, alpha)
    return "rgb(" + ", ".join(str(round(channel)) for channel in background) + ")"


def assert_effective_white(element, tolerance):
    layers = element.evaluate("""e=>{
      const layers=[];
      for(let p=e;p;p=p.parentElement) {
        const s=getComputedStyle(p);
        layers.unshift({background:s.backgroundColor,image:s.backgroundImage,opacity:s.opacity});
      }
      return layers;
    }""")
    assert_color(effective_background(layers), "#ffffff", tolerance)


@pytest.mark.parametrize("variant,link_color", [("dark", "#ffffff"), ("light", "#173e8f")],
                         ids=["painted-wrapper", "transparent-links-with-filled-button"])
def test_saved_navigation_uses_band_surface_and_own_link_colours(
        library, fixture_site, ingest_config, tmp_path, page, variant, link_color):
    configure_capture(library, ingest_config)
    source = fixture_site.root / "navigation-band" / "index.html"
    text = source.read_text()
    assert text.count('<body class="dark">') == 1
    source.write_text(text.replace('<body class="dark">', f'<body class="{variant}">'))
    url = fixture_site.url + "/navigation-band/index.html"
    page.goto(url)
    for width in WIDTHS:
        page.set_viewport_size({"width": width, "height": 1000})
        header, band, nav = (page.locator(selector) for selector in ("header", ".navbar", "nav"))
        if variant == "dark":
            assert_transparent(header)
            assert_color(css(band, ["background-color"])["background-color"], "#212529", 0)
        else:
            assert_color(css(header, ["background-color"])["background-color"], "#ffffff", 0)
            assert_transparent(band)
            assert_effective_white(nav, 0)
        assert_transparent(nav)
        links = nav.locator("a[href]")
        assert links.count() == 2
        for link in links.all():
            assert link.is_visible()
            assert_transparent(link)
            assert_color(css(link, ["color"])["color"], link_color, 0)
        button = header.locator("button")
        assert button.is_visible()
        assert_color(css(button, ["background-color"])["background-color"], "#8b2030", 0)

    _, document, _, requests = derive(library, fixture_site, url, "navigation-source")
    library.cli("save-draft", document["id"], cwd=library.project, timeout=90)
    assert library.read(document["id"]) == document
    preview = library.build(tmp_path / "saved-preview", document["id"])
    tolerance = ingest_config["color_delta_e"]
    seen = set()
    for width in WIDTHS:
        page.set_viewport_size({"width": width, "height": 1000})
        for name in PAGES:
            page.goto((preview / name).as_uri())
            page.evaluate("document.fonts.ready")
            for nav in page.locator('[data-kd-construct="nav"]').all():
                if not nav.is_visible():
                    continue
                if variant == "dark":
                    assert_color(css(nav, ["background-color"])["background-color"], "#212529", tolerance)
                else:
                    assert_effective_white(nav, tolerance)
                links = nav.locator('[data-kd-slot="nav.links"] a[href], a[data-kd-slot="nav.links"][href]')
                assert links.count(), (name, width, "Navigation links missing from saved sample")
                for link in links.all():
                    assert link.is_visible(), (name, width)
                    assert_transparent(link)
                    assert_color(css(link, ["color"])["color"], link_color, tolerance)
                if name != "states.html":
                    seen.add(width)
    assert seen == set(WIDTHS), ("No saved navigation checked at a requested width", seen)
    report = composition_report(library, document["id"], tmp_path / "saved-check", widths=WIDTHS)
    assert_composition_passes(report)
    assert len(fixture_site.requests) == requests, "Saved-language operations revisited the source"
