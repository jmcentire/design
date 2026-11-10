"""M2 B5 / amendments 12–13: domain-neutral reconstruction content and appearance.

Oracle: our own source pages, repeated groups and authored accent colors.
Falsifiers: generic vocabulary copy substituted for captured content, one page
reused for all pairs, groups flattened/reordered, lost hierarchy or grey accents.
"""

import re
from urllib.parse import quote

import pytest

from tests.m2_support import capture, color_distance, confined, draft, png, read_json
from tests.m1_support import contrast_ratio
from tests.test_m1_design import solid_background
from tests.test_m2_capture import tree_hashes

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]

PAGES = {
    "coast.html": {
        "heading": "Seagrass coastal notebook",
        "section": "Places beside the tide pools",
        "intro": "Three salt-air hideaways chosen for slow mornings.",
        "cards": [("Zinnia Pier cottage", "North jetty, four guests", "$289 per night"),
                  ("Amber Dune studio", "West dunes, two guests", "$173 per night"),
                  ("Kestrel Cove house", "Sheltered cove, six guests", "$331 per night")],
    },
    "estuary.html": {
        "heading": "Estuary weekend ledger",
        "section": "Rooms along the reed beds",
        "intro": "Three reed-side retreats for watching the changing water.",
        "cards": [("Willow Ferry loft", "Old ferry, three guests", "$247 per night"),
                  ("Bracken Marsh hut", "Reed marsh, two guests", "$195 per night"),
                  ("Otter Reach lodge", "River bend, five guests", "$364 per night")],
    },
    "editorial.html": {
        "heading": "Fieldwork dispatches", "section": "Stories from the field",
        "intro": "Essays for noticing the places around us.",
        "cards": [("Sketching the tidal orchard", "Mira Chen, field notes", "New essay"),
                  ("Letters from the moss garden", "Ivo Reed, correspondence", "Editor’s pick"),
                  ("An atlas of quiet footpaths", "Sol Park, walking notes", "Read slowly")],
    },
    "events.html": {
        "heading": "Community observatory", "section": "Gatherings under open skies",
        "intro": "Shared afternoons for making, listening and learning.",
        "cards": [("Lantern-making workshop", "Saturday, studio north", "Materials included"),
                  ("River sound walk", "Sunday, riverside gate", "Outdoor gathering"),
                  ("Seeds and stories circle", "Wednesday, garden room", "Bring a notebook")],
    },
    "team.html": {
        "heading": "People behind the notebook", "section": "Meet the field team",
        "intro": "A small team bringing different ways of noticing.",
        "cards": [("Yara Bell", "Illustration and field research", "Makes space for questions"),
                  ("Eli Santos", "Program coordination", "Connects people and ideas"),
                  ("Noor Patel", "Community facilitation", "Listens before drawing")],
    },
    "blog.html": {
        "heading": "A notebook beside the estuary", "section": "Observations along the path",
        "intro": "The morning tide left small stories on the shore.",
        "cards": [("Tracks in the wet sand", "Field journal, early morning", "Look closely"),
                  ("Reeds bending into the wind", "Field journal, midday", "Pause and listen"),
                  ("Shadows across the boardwalk", "Field journal, late afternoon", "Watch the light")],
    },
    "guide.html": {
        "heading": "A slow day around Saltmarsh Bay", "section": "Three places to explore on foot",
        "intro": "Follow the water from the quiet inlet to the open headland.",
        "cards": [("The inlet boardwalk", "Sheltered water, level path", "Start gently"),
                  ("The reed-bed lookout", "Marsh edge, shaded trail", "Bring binoculars"),
                  ("The headland loop", "Open coast, uneven ground", "Allow extra daylight")],
    },
    "words-neutral.html": {
        "heading": "Orchard notebook", "section": "Stories around",
        "intro": "Gentle notes from quiet spaces.",
        "cards": [("Juniper field notes", "Blue atlas", "Read soon"),
                  ("Willows ridge tales", "Gold atlas", "Open note"),
                  ("Meadows brook notes", "Rose atlas", "More here")],
    },
    "words-commerce.html": {
        "heading": "Booking discount", "section": "Booking nights",
        "intro": "Nights stars beds rooms guests.",
        "cards": [("Booking stars rooms", "Beds stars", "$240 /day"),
                  ("Booking stars rates", "Beds rates", "$180 /day"),
                  ("Booking rooms stars", "Beds rooms", "4.90 star")],
    },
}


def normalized(text):
    return " ".join(text.split())


def visible_fragments(locator):
    """Observe visible text nodes rather than regexing HTML or using OCR as proof."""
    return locator.evaluate("""root => {
      const result = [], walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        const text = node.textContent.trim().replace(/\\s+/g, ' ');
        if (!text) continue;
        const style = getComputedStyle(node.parentElement);
        if (style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity) === 0) continue;
        let transparent = false;
        for (let e=node.parentElement; e; e=e.parentElement) {
          if (Number(getComputedStyle(e).opacity) === 0) { transparent=true; break; }
        }
        if (transparent) continue;
        const range = document.createRange(); range.selectNodeContents(node);
        if ([...range.getClientRects()].some(r => r.width > 0 && r.height > 0 && r.right > 0 && r.bottom > 0))
          result.push({text, color: style.color});
      }
      return result;
    }""")


def assert_accent(locator, expected, tolerance):
    fragments = visible_fragments(locator)
    assert fragments, "Accent assertion reached no painted text"
    surface = solid_background(locator)
    for fragment in fragments:
        channels = [float(value) for value in re.findall(r"[\d.]+", fragment["color"])]
        assert fragment["color"].startswith("rgb") and len(channels) in (3, 4), fragment
        alpha = channels[3] if len(channels) == 4 else 1
        composed = [round(channels[i] * alpha + surface[i] * (1 - alpha)) for i in range(3)]
        observed = "#" + "".join(f"{channel:02x}" for channel in composed)
        assert color_distance(expected, observed) <= tolerance, (fragment["text"], expected, observed)


def decoded_samples(image):
    """Sample decoded source media, independent of output encoding or CSS scaling.

    The selected normalized points lie inside broad colored regions of our SVG;
    the same color tolerance used for the captured design applies here. This
    rejects a default placeholder even if it is visible and has a copied alt.
    """
    surface = solid_background(image)
    return image.evaluate("""(e, background) => {
      if (!e.complete || !e.naturalWidth || !e.naturalHeight) throw Error('Image did not decode');
      const canvas = document.createElement('canvas'); canvas.width = 120; canvas.height = 60;
      const ctx = canvas.getContext('2d'); ctx.fillStyle = `rgb(${background.join(',')})`;
      ctx.fillRect(0, 0, 120, 60); ctx.drawImage(e, 0, 0, 120, 60);
      return [[6,6],[6,54],[60,24],[60,45],[108,12]].map(([x,y]) =>
        [...ctx.getImageData(x,y,1,1).data].slice(0,3));
    }""", surface)


def assert_media_visible(group, original, tolerance):
    media = group.locator('[data-kd-slot][data-kd-role="media"]')
    assert media.count() == 1
    assert media.evaluate("""e => {
      for (let node=e; node; node=node.parentElement)
        if (Number(getComputedStyle(node).opacity) === 0) return false;
      return true;
    }""")
    images = group.locator("img")
    if images.count():
        assert images.count() == 1
        image = images.first
        assert image.is_visible()
        observed = decoded_samples(image)
        for expected_rgb, actual_rgb in zip(original, observed):
            expected = "#" + "".join(f"{v:02x}" for v in expected_rgb)
            actual = "#" + "".join(f"{v:02x}" for v in actual_rgb)
            assert color_distance(expected, actual) <= tolerance, ("Reconstruction substituted media", expected, actual)
    else:
        # Inline SVG/background-image are also valid media renderings. Geometry
        # still must show actual media, not an empty wrapper; decoded pixel
        # sampling above applies to this fixture's ordinary img rendering path.
        assert media.evaluate("""e => [e, ...e.querySelectorAll('svg')].some(node => {
          const r=node.getBoundingClientRect(), s=getComputedStyle(node);
          return r.width>0 && r.height>0 && s.visibility!=='hidden' &&
            (node.tagName.toLowerCase()==='svg' || s.backgroundImage!=='none');
        })""")


def repeated_groups(page, items, vocabulary):
    """Locate groups by their captured contents, without naming a domain construct."""
    constructs = page.locator("[data-kd-construct]")
    matches = constructs.evaluate_all("""(els, items) => {
      const norm = text => text.trim().replace(/\\s+/g, ' ').toLowerCase();
      return items.map(item => {
        const candidates = els.map((e,i) => ({e,i})).filter(({e}) => {
          const text=norm(e.innerText);
          // A semantic wrapper may use display:contents. Its children, rather
          // than a particular wrapper box, must actually render.
          const visible=[e,...e.querySelectorAll('*')].some(node => {
            const r=node.getBoundingClientRect();
            return r.width>0 && r.height>0 && getComputedStyle(node).visibility!=='hidden';
          });
          return visible
            && item.every(value => text.includes(norm(value)))
            && !items.some(other => other!==item && text.includes(norm(other[0])));
        });
        // A page-shell/section wrapper is not evidence of a repeated instance.
        return candidates.filter(({e}) => !candidates.some(other => other.e!==e && e.contains(other.e)))
          .map(({e,i}) => ({index:i, construct:e.dataset.kdConstruct}));
      });
    }""", items)
    assert all(len(match) == 1 for match in matches), ("Each source group needs exactly one reconstructed instance", matches)
    identities = [match[0]["construct"] for match in matches]
    assert len(set(identities)) == 1 and identities[0] in vocabulary["constructs"]
    indexes = [match[0]["index"] for match in matches]
    assert indexes == sorted(indexes) and len(set(indexes)) == len(items), "Repeated source order changed"
    return [constructs.nth(index) for index in indexes]


def assert_title_prominence(title, meta):
    def cues(locator):
        style = locator.evaluate("e => { const s=getComputedStyle(e); return [parseFloat(s.fontSize), Number(s.fontWeight), s.color]; }")
        channels = [float(v) for v in re.findall(r"[\d.]+", style[2])]
        surface = solid_background(locator)
        alpha = channels[3] if len(channels) == 4 else 1
        foreground = [round(channels[i]*alpha+surface[i]*(1-alpha)) for i in range(3)]
        to_hex = lambda rgb: "#" + "".join(f"{v:02x}" for v in rgb)
        return style[:2] + [contrast_ratio(to_hex(foreground), to_hex(surface))]
    a, b = cues(title), cues(meta)
    # Size, weight and contrast are independent observable prominence cues.
    # Do not require a specific role name, point size or font from the mapper.
    assert any(title_value > meta_value + 0.05 for title_value, meta_value in zip(a, b)), ("Title lost prominence over meta", a, b)


def heading_outline(page):
    # Native headings and equivalent ARIA headings are both valid. Preserve the
    # hierarchy relation, not a particular template's absolute heading levels.
    return page.get_by_role("heading").evaluate_all("""els => els.map(e => ({
      text: e.textContent.trim().replace(/\\s+/g, ' '),
      level: Number(e.getAttribute('aria-level') || (/^H[1-6]$/.test(e.tagName) ? e.tagName.slice(1) : 2))
    }))""")


def assert_heading_hierarchy(page, source):
    observed = heading_outline(page)
    assert [h["text"] for h in observed] == [h["text"] for h in source], (
        "Captured headings must remain headings in source order", source, observed)
    assert all(1 <= h["level"] for h in observed), observed
    def relation(a, b):
        return (a > b) - (a < b)
    for i, before in enumerate(source):
        for j, after in enumerate(source):
            assert relation(before["level"], after["level"]) == relation(observed[i]["level"], observed[j]["level"]), (
                "Heading hierarchy changed", source, observed)


def reconstruct(library, fixture_site, ingest_config, page, filenames, identity):
    sources = {}
    for filename in filenames:
        expected = PAGES[filename]
        url = fixture_site.url + "/cards/" + filename
        page.goto(url)
        assert normalized(page.locator("h1").inner_text()) == expected["heading"]
        assert page.locator(".item h3").all_text_contents() == [card[0] for card in expected["cards"]]
        for accent in page.locator(".highlight").all():
            assert_accent(accent, "#0b6e4f", 0.01)
        sources[url] = {**expected, "fragments": visible_fragments(page.locator("body")),
                        "headings": heading_outline(page),
                        "media": [decoded_samples(image) for image in page.locator(".item img").all()]}
        sources[url]["text"] = normalized(" ".join(fragment["text"] for fragment in sources[url]["fragments"]))
    artifact, artifact_root, captured = capture(library, list(sources))
    assert not captured["problems"], captured
    for entry in captured["pages"]:
        assert {*ingest_config["widths"], 768} <= {int(width) for width in entry["widths"]}
    immutable = tree_hashes(artifact_root)
    fixture_site.available = False
    source_request_count = len(fixture_site.requests)
    root, _, _ = draft(library, [artifact], identity)
    library.cli("fidelity", identity, cwd=library.project, timeout=90)
    report_root = root / "fidelity"
    report = read_json(report_root / "report.json")
    expected_pairs = {(entry["name"], int(width)) for entry in captured["pages"] for width in entry["widths"]}
    assert {(pair["page"], pair["width"]) for pair in report["pairs"]} == expected_pairs
    assert len(report["pairs"]) == len(expected_pairs)
    by_page = {entry["name"]: sources[entry["url"]] for entry in captured["pages"]}
    return report_root, report, by_page, artifact_root, immutable, source_request_count


def inspect_reconstruction(page, server, identity, report_root, pair, expected, vocabulary, tolerance):
    html = confined(report_root, pair["html"])
    png(report_root / pair["reconstruction"])
    page.set_viewport_size({"width": pair["width"], "height": 900})
    response = page.goto(server + f"/ingest/drafts/{identity}/fidelity/" + quote(pair["html"], safe="/"))
    assert response and response.ok and response.body() == html.read_bytes()
    assert page.evaluate("innerWidth") == pair["width"]
    assert_heading_hierarchy(page, expected["headings"])
    for text in (expected["heading"], expected["section"], expected["intro"]):
        assert page.get_by_text(text, exact=True).first.is_visible(), (pair["page"], pair["width"], text)
    fragments = visible_fragments(page.locator("body"))
    assert fragments
    text = normalized(" ".join(fragment["text"] for fragment in fragments))
    assert all(normalized(fragment["text"]) in expected["text"] for fragment in fragments), (
        "Reconstruction introduced copy absent from its source", pair["page"],
        [fragment["text"] for fragment in fragments if normalized(fragment["text"]) not in expected["text"]])
    assert all(normalized(fragment["text"]) in text for fragment in expected["fragments"]), (
        "Reconstruction dropped captured copy", pair["page"],
        [fragment["text"] for fragment in expected["fragments"] if normalized(fragment["text"]) not in text])
    groups = repeated_groups(page, expected["cards"], vocabulary)
    signatures = []
    for index, (title_text, meta_text, highlight_text) in enumerate(expected["cards"]):
        group = groups[index]
        title, meta, accent = (group.get_by_text(value, exact=True).first for value in (title_text, meta_text, highlight_text))
        assert title.is_visible() and meta.is_visible() and accent.is_visible()
        assert_title_prominence(title, meta)
        assert_media_visible(group, expected["media"][index], tolerance)
        assert_accent(accent, "#0b6e4f", tolerance)
        signatures.append({"construct": group.get_attribute("data-kd-construct"), "slots": group.locator("[data-kd-slot]").evaluate_all(
            "els => els.map(e => [e.dataset.kdSlot,e.dataset.kdRole,e.dataset.kdEmphasis])")})
    assert_accent(page.get_by_text(expected["section"], exact=True).first, "#a14524", tolerance)
    return signatures


@pytest.mark.parametrize("filenames", [("coast.html", "estuary.html"), ("editorial.html", "events.html", "team.html"),
                                        ("blog.html", "guide.html")],
                         ids=["original-content", "non-commerce", "blog-and-travel-guide"])
def test_fidelity_preserves_generic_groups_content_hierarchy_media_and_accents(
        library, server, fixture_site, ingest_config, page, vocabulary, filenames):
    identity = "generic-reconstruction"
    report_root, report, sources, artifact_root, immutable, count = reconstruct(
        library, fixture_site, ingest_config, page, filenames, identity)
    for pair in report["pairs"]:
        inspect_reconstruction(page, server, identity, report_root, pair, sources[pair["page"]], vocabulary, ingest_config["color_delta_e"])
    assert len(fixture_site.requests) == count, "Fidelity HTML fetched the unavailable live source"
    assert tree_hashes(artifact_root) == immutable


def test_same_structure_and_presentation_map_identically_when_domain_words_change(
        library, server, fixture_site, ingest_config, page, vocabulary):
    geometries, mappings = [], []
    for filename in ("words-neutral.html", "words-commerce.html"):
        fixture_site.available = True
        geometry = {}
        for width in (320, 768, 960):
            page.set_viewport_size({"width": width, "height": 900})
            page.goto(fixture_site.url + "/cards/" + filename)
            geometry[width] = page.locator(".item,.item > *").evaluate_all("""els => els.map(e => {
              const r=e.getBoundingClientRect(), s=getComputedStyle(e);
              return [e.tagName,r.x,r.y,r.width,r.height,s.fontFamily,s.fontSize,s.fontWeight,s.color];
            })""")
        geometries.append(geometry)
        # The input metric precondition is checked before comparing mappings;
        # matching character counts alone do not prove matching rendered geometry.
        if len(geometries) == 2:
            assert geometries[0] == geometries[1], "Text substitution changed presentation; the mapping relation would be confounded"
        identity = filename.removesuffix(".html")
        report_root, report, sources, artifact_root, immutable, count = reconstruct(
            library, fixture_site, ingest_config, page, [filename], identity)
        observed = {}
        for pair in report["pairs"]:
            observed[pair["width"]] = inspect_reconstruction(
                page, server, identity, report_root, pair, sources[pair["page"]], vocabulary, ingest_config["color_delta_e"])
        mappings.append(observed)
        assert len(fixture_site.requests) == count
        assert tree_hashes(artifact_root) == immutable
    assert mappings[0] == mappings[1], "Domain words changed construct/slot/role mapping despite identical structure and presentation"


def test_reconstructed_prose_keeps_local_rhythm_surfaces_and_structured_content(
        library, fixture_site, ingest_config, page):
    # This compact reading group deliberately uses 12px paragraph gaps, 4px
    # list gaps and a 24px line height. Section spacing remains unconstrained.
    source = fixture_site.root / "centred-prose" / "index.html"
    text = source.read_text().replace("<p>This introduction", "<div class=\"intro-copy\"><p>This introduction").replace(
        "place in the record.</p>", "place in the record.</p></div>").replace("</style>", """
      #reading p { margin:12px 0; } #reading li { margin:4px 0; }
      table { border-collapse:collapse; display:block; max-width:100%; overflow-x:auto; }
      th, td { padding:8px; border:1px solid; }
    </style>""").replace("</article>", """
      <div id="reading"><p>First ordinary reading paragraph.</p>
      <p>Second ordinary reading paragraph.</p>
      <ul><li>Observe the weather.</li><li>Record the change.</li></ul>
      <table><caption>Field measurements</caption><thead><tr><th>Month</th><th>Rain</th><th>Record</th></tr></thead>
      <tbody><tr><th>April</th><td>12</td><td>OBS202604GARDENSTATIONNORTHDAILYRAINFALL0001</td></tr><tr><th>May</th><td>18</td><td>OBS202605GARDENSTATIONNORTHDAILYRAINFALL0002</td></tr></tbody></table>
      <dl><dt>Observer</dt><dd>Garden team</dd><dt>Interval</dt><dd>One day</dd></dl></div>
    </article>""")
    source.write_text(text)
    ingest_config["widths"] = [375, 1280]
    (library.project / "kinbase-design.toml").write_text(
        "[ingest]\n" + "\n".join(f"{k} = {v}" for k, v in ingest_config.items()))
    page.set_viewport_size({"width": 375, "height": 900})
    page.goto(fixture_site.url + "/centred-prose/index.html")
    assert page.get_by_role("table").evaluate("e => e.scrollWidth > e.clientWidth")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator("#reading p").evaluate_all(
        "els=>els.map(e=>[getComputedStyle(e).lineHeight,getComputedStyle(e).marginBottom])") == [["24px", "12px"]] * 2
    assert page.get_by_role("table").get_by_role("row").count() == 3
    artifact, _, _ = capture(library, [fixture_site.url + "/centred-prose/index.html"])
    fixture_site.available = False
    root, _, _ = draft(library, [artifact], "reading-rhythm")
    report = library.json("fidelity", "reading-rhythm", cwd=library.project, timeout=90)
    observations = []
    for pair in report["pairs"]:
        if pair["width"] not in (375, 1280):
            continue
        page.set_viewport_size({"width": pair["width"], "height": 900})
        page.goto(confined(root / "fidelity", pair["html"]).as_uri())
        first = page.get_by_text("First ordinary reading paragraph.", exact=True)
        second = page.get_by_text("Second ordinary reading paragraph.", exact=True)
        a, b = first.bounding_box(), second.bounding_box()
        items = page.get_by_role("listitem").filter(has_text="Observe the weather.").or_(
            page.get_by_role("listitem").filter(has_text="Record the change."))
        boxes = [item.bounding_box() for item in items.all()]
        intro = page.get_by_text("This introduction offers a short route into the notebook and explains why each observation has a place in the record.", exact=True)
        observations.append({"width": pair["width"], "paragraph_gap": b["y"] - a["y"] - a["height"],
            "list_gap": boxes[1]["y"] - boxes[0]["y"] - boxes[0]["height"] if len(boxes) == 2 else None,
            "intro_surface": solid_background(intro),
            "page_contained": page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
            "table_scroll": page.get_by_role("table").evaluate_all("""els => els.map(e => {
              let owner=e;
              for(let n=e;n && n!==document.body;n=n.parentElement)
                if(n.scrollWidth>n.clientWidth && ['auto','scroll'].includes(getComputedStyle(n).overflowX)) {
                  owner=n; break;
                }
              owner.scrollLeft=owner.scrollWidth;
              return [owner.scrollWidth,owner.clientWidth,owner.scrollLeft];
            })"""),
            "rows": page.get_by_role("table").get_by_role("row").evaluate_all(
                "rows=>rows.map(r=>[...r.querySelectorAll('th,td')].map(c=>c.textContent.trim()))"),
            "definitions": page.locator("dl dt,dl dd").all_text_contents()})
    assert {o["width"] for o in observations} == {375, 1280}
    for o in observations:
        assert 0 <= o["paragraph_gap"] <= 24, observations
        assert o["list_gap"] is not None and 0 <= o["list_gap"] <= o["paragraph_gap"], observations
        # Retain the authored #e3edf5 surface through transparent prose; do not
        # introduce an inner white panel. Reuse capture's color tolerance.
        color = "#" + "".join(f"{v:02x}" for v in o["intro_surface"])
        assert color_distance(color, "#e3edf5") <= ingest_config["color_delta_e"], observations
        assert o["page_contained"], observations
        assert len(o["table_scroll"]) == 1, observations
        extent, available, reached = o["table_scroll"][0]
        if o["width"] == 375:
            assert extent > available, observations  # Fixture deliberately requires local scrolling.
        assert extent <= available or reached > 0, observations
        assert o["rows"] == [["Month", "Rain", "Record"],
            ["April", "12", "OBS202604GARDENSTATIONNORTHDAILYRAINFALL0001"],
            ["May", "18", "OBS202605GARDENSTATIONNORTHDAILYRAINFALL0002"]], observations
        assert o["definitions"] == ["Observer", "Garden team", "Interval", "One day"], observations
