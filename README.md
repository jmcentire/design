# Kinbase Design

A local visual workbench for reusable design languages. M1 includes two hand-authored languages: coastal **Harbor** and warm editorial **Lantern**, with an SVG wordmark, a landscape illustration, and Instrument Sans.
The shared `library/` directory demonstrates a library living inside another Git project.

Requires Python 3.12 with `jinja2`, `rfc8785`, `fonttools`, `pillow`, and `playwright`, plus an installed Chromium browser. No database or build
service is needed. Use your prepared environment; the Factory runtime is the Python interpreter
under the run's `runtime/venv/bin/` directory.

## Open the workbench

```sh
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
  asset/font gaps. Every finding has a library-relative file and JSON pointer.
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
Languages can express clipping with `overflow`, `text-overflow`, and `white-space`.
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

Kinbase standards and direction are **unknown**. M2–M4 remain unimplemented: capture/ingest and
quantization, guided generation and choice history, export/apply adapters, site inventory
acceptance, feedback/proposals, and Kinbase standards integration. No deployment, remote
publishing, or telemetry is included.

## Local verification without sockets

`kinbase_design.workbench.create_app(library, workspace)` returns a WSGI application. Call it
with a WSGI environment and `start_response` to exercise routes in-process. The renderer's
`preview_files(library, id)` returns the same filename-to-bytes map used by `build_preview`.
This lane performed throwaway CLI/WSGI checks; the independent Factory Tester owns the test
suite. The M0 browser repairs were confirmed by the Validator. The M1 checker and Lantern
require a fresh Validator Chromium run; rendered acceptance is not claimed from the local
Python-only checks.
