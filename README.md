# Kinbase Design

A local visual workbench for reusable design languages. M0 includes a hand-authored coastal
language, **Harbor**, with an SVG wordmark, a landscape illustration, and Instrument Sans.
The shared `library/` directory demonstrates a library living inside another Git project.

Requires Python 3.12 with `jinja2`, `rfc8785`, `fonttools`, and `pillow`. No database or build
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

## What M0 implements

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

Kinbase standards and direction are **unknown** in M0. The adapter has no active connection.
M1–M4 are not implemented: rendered contrast/reflow/target checks, capture/ingest and quantization,
guided generation and choice history, export/apply adapters, site inventory acceptance,
feedback/proposals, and Kinbase standards integration. Declared behavior scope/kind is validated;
rendered behavior exceptions belong to the later rendered checker and cannot bypass broken
references or semantic contracts. No deployment, remote publishing, or telemetry is included.

## Local verification without sockets

`kinbase_design.workbench.create_app(library, workspace)` returns a WSGI application. Call it
with a WSGI environment and `start_response` to exercise routes in-process. The renderer's
`preview_files(library, id)` returns the same filename-to-bytes map used by `build_preview`.
This lane performed throwaway CLI/WSGI checks; the independent Factory Tester owns the test
suite. Browser appearance, actual font decoding, contrast and asset legibility require the
Validator's browser environment and are not claimed verified here.
