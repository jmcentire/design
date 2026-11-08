# Kinbase Design

A local visual workbench for reusable design languages. Includes ingest and guided generate journeys and two hand-authored languages: coastal **Harbor** and warm editorial **Lantern**, with an SVG wordmark, a landscape illustration, and Instrument Sans.
The shared `library/` directory demonstrates a library living inside another Git project.

Requires Python 3.12 with `jinja2`, `rfc8785`, `fonttools`, `pillow`, and `playwright`, plus an installed Chromium browser. No database or build
service is needed. Use your prepared environment; the Factory runtime is the Python interpreter
under the run's `runtime/venv/bin/` directory.

## Open the workbench

The repository/checkout is named `design`. The product remains Kinbase Design and the Python
package remains `kinbase_design`. From the parent of your checkout:

```sh
cd design
python -m kinbase_design serve
```

Open `http://127.0.0.1:8765/`. The server binds only to `127.0.0.1` (port is configurable).
Browse the library, open Harbor, choose a page and a 320/768/1280 CSS-pixel viewport, or compare
two languages. Turn annotations on and hover a slot to inspect its vocabulary role/emphasis and
asset binding. Page links, width selection, annotations, comparison, upload/promotion, and
static navigation work without JavaScript.

The assets panel lists variants, their hashes, and missing bindings/font variants. Uploading and
promoting a file retains an immutable private original and copies the approved bytes into the
language package. IDs use kebab-case; font promotion also needs a weight. Upload limit: 20 MiB.

## Library and private workspace

Every command accepts `--library PATH` and `--workspace PATH`, either before or after its
subcommand. Precedence for each: flag, environment (`KINBASE_DESIGN_LIBRARY` or
`KINBASE_DESIGN_WORKSPACE`), `kinbase-design.toml` in the current directory, then defaults.
Paths in the TOML file are relative to that file:

```toml
library = "design/library"
workspace = "../private-design-originals"
```

Defaults: `./library` and `~/.local/share/kinbase-design`. The private workspace must be outside
the library. Originals are never copied into the shared library. Shared assets are stored as
`languages/<id>/assets/sha256/<digest>`; immutable language versions live in `versions/`.
The Instrument Sans copyright and OFL notice are in [library/FONT-LICENSE.txt](library/FONT-LICENSE.txt).

## CLI

```sh
python -m kinbase_design vocabulary
python -m kinbase_design validate harbor
python -m kinbase_design resolve harbor listing-card.price
python -m kinbase_design resolve harbor listing-card.price --state hover --breakpoint md
python -m kinbase_design build-preview harbor --out /tmp/harbor-preview
python -m kinbase_design mint harbor
python -m kinbase_design check lantern --widths 320,768,1280
python -m kinbase_design check lantern --out /tmp/lantern-checks
python -m kinbase_design import-artifact --file ./wordmark.svg
python -m kinbase_design promote harbor --artifact artifact-HASH --asset-id wordmark --kind logo --variant primary
python -m kinbase_design promote harbor --artifact artifact-HASH --asset-id body-font --kind font --variant regular --weight 400 --style normal --family "Instrument Sans"
```

JSON results go to stdout; bounded operation logs go to stderr. `validate`, `resolve`,
`build-preview`, and `mint` return 1 for a rejected language; usage errors return 2.
Breakpoint arguments are declared token IDs such as `md`, never numeric viewport widths or
`breakpoint.md`. Omitting the flag resolves the base context below all declared breakpoints.

The preview produces `index.html`, `search.html`, `listing.html`, `form.html`, `states.html`,
`language.css`, and local `assets/`. The workbench serves those same bytes under
`/preview/<id>/`. Language identity lives in CSS. Default-variant HTML is identical across
languages with the same vocabulary/sample set and the same asset id, variant, and format bound
to each media slot (contract amendment 02). Annotation hooks retain vocabulary defaults;
effective component role/emphasis treatment is computed by the resolver.

## What is implemented

- Versioned vocabulary and context/sample set, including long words/titles, missing images,
  zero/one/many collections, and every declared state.
- DTCG token evaluation, typed references, R1–R5 composition validation, variant-template
  contracts, role/surface pairing, spacing/breakpoints, override scope/reason checks, and
  asset/font gaps. Every finding has a source-relative file and JSON pointer.
- Resolution with per-property provenance and the specified override precedence; removing an
  override restores inherited treatment.
- Immutable source import, content-addressed asset promotion, font/media bindings, and
  RFC 8785/SHA-256 version minting. CLI and workbench share the operations.
- Static semantic previews and the server-rendered library, viewer, compare and asset workflows.
- A source-inspection schema spike in [docs/design/M0-SPIKE.md](docs/design/M0-SPIKE.md), including
  vocabulary revisions and explicit fidelity gaps.

M1 adds the `checks` bounded context. `check` builds a fresh preview and audits all five pages
in Chromium, with JavaScript disabled for rendering/navigation/state coverage and enabled for
interaction checks. It measures contrast, role conformance, clipping, reflow, targets, asset
loading, keyboard order and visible focus. Alpha-composition and geometry math are plain Python;
axe-core 4.10.3 is bundled with its MPL-2.0 notice for supplemental rendered contrast analysis.
Languages can express clipping with `overflow`, `text-overflow`, and `white-space`, and paint
borders with `border-style`. Control box treatments apply to native inputs inside the slot; text
treatments stay on the slot and inherit. Parts unused by the selected variant produce advisory coverage.
`background-image` accepts a gradient token alias (DTCG color stops rendered at 180 degrees)
or `asset:<image-id>:<variant>`. Background images are packaged and decoded by the checks;
text over imagery or gradients remains an unresolved contrast review.
Browser operations and the whole worker process have configured time limits. Chromium startup
failure is an environment error (exit 2), never an accepted report. OCR is not used.

Reports and `<page>@<width>.png` screenshots go to `--out`, or by default to
`library/generated/<id>/checks/<hash>/`. A custom output is mirrored under `generated/` so the
workbench can show its latest report and link its screenshots. The viewer groups findings by
type, shows measurements and exceptions, and offers a server-rendered “Run Chromium checks”
form. Results from an earlier language hash are marked stale.

The shared acceptance rule rejects uncovered missing/violation findings. Declared truncation
only covers clipping when the full text is visible on its named destination page. Horizontal
scroll and target-size exceptions are reported explicitly; unused behaviors are advisory
coverage findings. Unresolved `needs-review` findings remain visible and are counted in
`needs_review`; they do not by themselves reject a report. Image/gradient legibility is sent to
review when the checker cannot measure it reliably.

Lantern packages Instrument Sans, an authored wordmark and an evening illustration. Its
`listing-card` variant wraps editorial content, stacks below 768px and puts media beside it at
768px and above. Card titles clamp to two lines; full sample titles remain visible on the listing
page. The gallery deliberately scrolls horizontally. Media reserves a 3:2 box before images load,
using `object-fit: contain` to preserve each image’s proportions.

Kinbase standards and direction are **unknown**. M4 remains unimplemented:
export/apply adapters, site inventory acceptance, feedback/proposals, and Kinbase standards integration. No deployment, remote
publishing, or telemetry is included.

## Ingest a source (M2)

Open **Ingest** in the workbench (`/ingest`). Enter unauthenticated HTTP(S) URLs, including localhost or LAN development servers, or upload images, mocks,
wireframes, DTCG JSON, assets, a brief, or a Figma export ZIP. Review captures at each width,
derive a new draft, inspect the palette/type/spacing measurements, render the fidelity review,
answer visual questions, and save to the library. These forms work without JavaScript.
Figma export directories are also accepted by the CLI.

```sh
python -m kinbase_design capture --url https://example.com --widths 320,768,1280
python -m kinbase_design import-artifact --file ./variables.json --kind dtcg
python -m kinbase_design import-artifact --file ./figma-export --kind figma-export
python -m kinbase_design draft --from artifact-HASH --language my-language
python -m kinbase_design fidelity my-language
python -m kinbase_design questions my-language
python -m kinbase_design answer my-language question-1 candidate-2
python -m kinbase_design save-draft my-language
```

Capture uses fresh Chromium and unauthenticated request contexts. It accepts internet, loopback
and private-network HTTP(S) URLs, refuses embedded credentials and other URL schemes, strips
cookies/auth headers and Set-Cookie responses, and blocks non-read requests and WebSockets.
Capture scrolls through the page to activate lazy media, waits within configured time/step bounds,
and restores the starting position before sampling. Unloaded images remain explicit capture problems.
Discovered media-query widths are added within configured bounds. It stores DOM originals, sampled computed styles, screenshots, font faces
and candidate asset originals. Visible image/background references take priority over unrelated
network images; capture retains up to 512 assets within the byte budget. AVIF and GIF originals
can be displayed privately in fidelity review without changing the approved package formats.
Later operations read those immutable artifacts and never visit
the live site. A missing Chromium installation or launch failure returns exit 2 clearly.

Capture artifacts expose `capture.json`, with screenshots, DOM and style samples under `pages/`
and image originals under `assets/`. Capture stdout lists only successfully captured page names;
unloaded pages appear in problems. Draft stdout is also saved as `drafts/<id>/summary.json`,
including `measured` facts and a numeric question count; `questions <id>` returns the candidates.
Fidelity writes `drafts/<id>/fidelity/report.json` with image pairs and aggregate measured facts.
Each pair's `html` points to the reconstructed page rendered for that screenshot. The workbench
links to it at `/ingest/drafts/<id>/fidelity/<file>`, serving its adjacent stylesheet and assets.

Optional settings in the current directory's `kinbase-design.toml` apply to CLI and workbench:

```toml
[ingest]
color_delta_e = 2.0
type_size_px = 1.0
type_ratio = 0.05
spacing_px = 1.0
radius_px = 1.0
widths = [320, 768, 1280]
capture_timeout_s = 30
max_pages = 10
```

Drafts live in `workspace/drafts/<id>/`, with working JSON, provenance, captured compositions,
questions and fidelity artifacts. Provenance files are direct JSON-pointer maps: a record covers
its value and descendants, and the nearest ancestor record wins. Token values and other design
leaves require coverage; descriptive metadata, token metadata and reason text do not. Palette clustering uses CIEDE2000; type and spacing tolerances
live in `config.py`. Source DTCG values remain unchanged. Semantic mapping is deterministic and
reported as **heuristic**. Missing and ambiguous treatments get rendered alternatives; choosing
an alternative records its provenance. Repeated source groups map to the generic `card`
construct using sibling structure, media, headings and typographic hierarchy. Text is data:
currency, ratings and domain words do not select constructs or slots. Small text becomes
metadata or an eyebrow by position; short accent text becomes a highlight. Specialised
constructs such as `listing-card` remain available for explicit mappings and authored languages.

Choosing again supersedes the value and its chosen provenance. Candidate preview paths are relative to
the draft directory. The value-provenance panel marks erased originals as “source removed”.
Unsupported layout details, unmapped
content, capture limits and fidelity divergences remain explicit coverage findings.

The fidelity renderer uses the same vocabulary constructs, validated variants and CSS resolver
as ordinary previews, with captured text and reference assets kept private. It pairs capture and
reconstruction screenshots at the captured widths and reports measured colour distances, font
matches, type ratios and spacing. This is an approximation constrained by the vocabulary and
closed property set; the comparison exposes its gaps. Draft previews and fidelity rendering
use the existing validator, and promoted draft assets use the existing promotion operation.
Long-form pages retain heading-led sections, ordered prose and media, and inline link/accent
fragments. These use structure and presentation signals, including for blogs and travel guides.
Repeated-group containers retain measured columns and row/column gaps at each captured width.
Captured compositions recover content and repeated groups from the saved DOM, leave unobserved
slots empty, and retain measured context as references to draft tokens. These contexts pass
through the same validator and resolver. Responsive source-image substitutions are reported;
saved inline SVGs pass the ordinary asset safety checks before private rendering.
Captured originals are offered for promotion, never automatically approved. Saving copies the
working language and approved assets into the library; shared provenance keeps opaque source
ids and safe selectors/JSON pointers, with private URLs and filesystem locations removed.

An optional user command can be configured with `KINBASE_DESIGN_LLM_COMMAND`. It reads a JSON
mapping request on stdin and returns an array of `{selector, construct, slot, role, emphasis?}`.
Every selector must come from the capture and every semantic id from the vocabulary. Invalid
output is discarded with a coverage finding. No command is run when unconfigured; no API keys
are read and no model network client is built in. All browser and adapter operations are bounded.

Generated ingest JSON (draft evidence, worker jobs and fidelity reports) has a shared
100 MiB read/write limit in `config.py`. Original sampled design evidence is retained.
This is separate from the 20 MiB upload limit and the 4 MiB working-language and
adapter input/output limits. An oversized adapter prompt keeps heuristic mapping
and reports the reason; it does not discard captured evidence.

## Generate a language (M3)

Open `/generate`. Enter a brief and optionally upload a logo, font, DTCG palette or image.
The visual interview renders specimens, the mood board supports pin/remove, and A/B rounds
compare the same sample screen. Choose A, B or neither with an optional comment. Earlier choices
can be revised without deleting history. Stop at any time to derive, review the multi-page site
and findings, and save through the same draft path as ingest. Every step works without JavaScript.
Supplied assets remain constraints even when their mood-board tile is removed.

```sh
python -m kinbase_design generate start --brief "A casual site for young families; relaxing but engaging beach vacation; blues, greens and turquoise; whimsical flair"
python -m kinbase_design generate interview SESSION --answers '{"shape":16,"density":10,"type-pairing":"rounded"}'
python -m kinbase_design generate moodboard SESSION
python -m kinbase_design generate moodboard SESSION --pin shape-2
python -m kinbase_design generate pair SESSION
python -m kinbase_design generate choose SESSION PAIR A --comment "The calmer direction"
python -m kinbase_design generate settled SESSION
python -m kinbase_design generate choose SESSION PAIR B --supersedes CHOICE
python -m kinbase_design generate derive SESSION --language beach-family
python -m kinbase_design save-draft beach-family
```

Add `--artifact ID` repeatedly to `generate start` for existing imports. Brief parsing is local
keyword heuristics; generate does not invoke a model or fetch fonts. Supplied palette literals
stay exact source tokens; imported aliases are rebased into a source namespace. Supplied font,
logo and image bytes go through the existing content-hash promotion operation unchanged.
Generated illustrations are clearly sample assets. Default context copy is domain-neutral;
the long-word, long-title, missing-image and collection-size stress cases remain available.

Sessions live in the private workspace under `sessions/<id>/`. `choices.jsonl` is append-only;
settled dimensions are calculated from effective choices. `neither` reoffers those dimensions
at greater distances until their domain is exhausted, then moves on. Categorical exploration
ends with an explicitly marked widest comparison before moving on; pair JSON exposes its
`variation` and the dimensions left `exhausted` but unsettled. Interview and pinned
mood-board directions provide priors; A/B choices take precedence. Candidate directories hold
`working.json`, `sample.html`, `swatch.html`, the normal sample pages, CSS and packaged assets.
The common sample includes attention-emphasis status text, labels, typography, cards and form
controls so each dimension has a visible specimen. Colour fills hero and accent surfaces and
primary actions; type scale, spacing and shape affect prominent parts of the same screen. Both
directions retain identical sample HTML. Interview selections initially preserve the brief’s seeds.
Mood-board and interview tiles use focused palette strips, type specimens, shape/rhythm and
accent/texture compositions (`palette.html`, `type.html`, `shape.html`, `formality.html`,
`texture.html`), built by the same preview renderer from each candidate’s language.
The workbench serves these at `/generate/<session>/candidates/<hash>/<file>`.
Candidates include the manifest’s `assets/sha256/` package files as well as preview URLs, so
the directory can be copied to `languages/<working.json id>/` in another library. The round
cap counts answered pairs; replacing an unanswered pair after a revision consumes no round.

```toml
[generate]
round_cap = 8
candidates_per_question = 3 # 2–4 rendered interview alternatives
repair_iterations = 5
```

Derivation uses colour harmony, a modular title/subtitle/body scale, spacing multiples and
hierarchy. It reuses R1–R5 validation and the Chromium `check` operation. Repairs are bounded
and change only unsupplied values; remaining findings stay visible. If Chromium cannot start,
the CLI exits 2 and retains the draft for review. The workbench displays checks as unavailable,
never passed. A static preview alone does not establish rendered acceptance.

Generate's five type pairings use system families: geometric-sans uses Arial; humanist-sans
uses system-ui; rounded requests Trebuchet MS then ui-rounded; serif uses Georgia; slab requests
Rockwell then Courier New. Serif and sans normally render distinct faces. Rounded and slab
depend on installed system faces and may fall back; five distinct downloaded faces are not
claimed. Harbor and Lantern use the packaged, licensed Instrument Sans. A supplied font is
bound to body text as its original bytes, while title pairing remains selectable.

## Local verification without sockets

`kinbase_design.workbench.create_app(library, workspace)` returns a WSGI application. Call it
with a WSGI environment and `start_response` to exercise routes in-process. The renderer's
`preview_files(library, id)` returns the same filename-to-bytes map used by `build_preview`.
This lane performed throwaway CLI/WSGI checks; the independent Factory Tester owns the test
suite. The M0 browser repairs were confirmed by the Validator. M1 grouping and behavior handling were confirmed by the Validator. M2 capture and fidelity
require a Validator Chromium run; rendered fidelity is not claimed from local Python-only checks.
M3 session planning, candidate validity, provenance, CLI and no-JavaScript WSGI flow are exercised
offline; its actual rendered checks and beach-brief appearance require the Validator's browser.
