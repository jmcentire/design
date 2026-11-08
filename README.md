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

M4 export, inventory, Apply, feedback/proposals and the Kinbase adapter are implemented.
In this environment Kinbase standards and direction remain **unknown**: no initialized
design repository or design logical keys have been configured (G2). No deployment, remote
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
at greater distances until the offered pair reports `variation[dimension].widest: true`,
then leaves that dimension unsettled and moves on. Each pair reports its distance and limit;
a mixed pair retries only dimensions that can still widen. Different type pairings already
have the maximum categorical distance of 1, so their first comparison is marked widest.
Pair JSON also lists dimensions left `exhausted` but unsettled. Interview and pinned
mood-board directions provide priors; A/B choices take precedence. Candidate directories hold
`working.json`, `sample.html`, `swatch.html`, the normal sample pages, CSS and packaged assets.
The home hero’s eyebrow uses attention emphasis by default. The common A/B sample also
includes attention-emphasis status text, labels, typography, cards and form
controls so each dimension has a visible specimen. Colour fills hero and accent surfaces and
primary actions; type scale, spacing and shape affect prominent parts of the same screen. Both
directions retain identical sample HTML. Interview selections initially preserve the brief’s seeds.
Mood-board and interview tiles use focused palette strips, type specimens, shape/rhythm and
accent/texture compositions (`palette.html`, `type.html`, `shape.html`, `formality.html`,
`texture.html`), built by the same preview renderer from each candidate’s language. Decorative
texture occupies an empty accent-band part above the content; all text has a solid background.
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

Export a versioned language with `python -m kinbase_design export harbor --adapter generic
--out /tmp/harbor-export` (one shell line). Load `tokens.css` before `roles.css` for custom
properties, role classes (`.kd-role-title-neutral`), and the normal `data-kd-*` treatments.
`--adapter dtcg-tailwind` produces computed DTCG `tokens.json` and `theme.css` for Tailwind v4:
`@theme static` registers theme variables and `[data-theme='light']` declares light overrides,
following the pinned design-system generator. The `dtcg-tailwind@2` adapter replaces recognized
groups with one Tailwind namespace: `color.brand` → `--color-brand`, `breakpoint.lg` →
`--breakpoint-lg`, `font.body` → `--font-body`, `space.base` → `--spacing-base`,
`type.title` → `--text-title`, and `radius.card` → `--radius-card`. Custom groups retain their
path; colliding short names gain a reserved `_path` suffix with the full path so no token is lost.
Generic properties use `--kd-` plus the token path (`--kd-color-brand`). Token segments escape hyphens as `_h` and underscores as `_u` to distinguish
`a-b.c` from `a.b-c` without collisions. Both adapters include all bound asset bytes and native-control, breakpoint,
state and behavior treatments from the preview renderer. Export mints the language version;
CSS comments and DTCG metadata identify that version and adapter version. Identical version and
adapter inputs produce identical files. `theme.css` works directly in a browser: custom properties
live under `:root, [data-theme='light']`, and role/hook rules remain outside `@theme` (which
browsers skip). No Tailwind compiler is required or provided offline. **Verification gap:**
Tailwind's own consumption of the `@theme` block has not been verified; verify it in the target
design-system repository during Apply.

`python -m kinbase_design inventory-check harbor --inventory /path/to/site/kinbase-design.inventory.json`
compares a site's inventory with resolved treatments. Role defaults count; non-default states
must differ from default in at least one resolved property. Only bound, packaged assets count.
A page's `assets` array accepts bare kinds (`"logo"`) or explicit variants (`"logo:on-dark"`).
A bare kind needs any bound asset of that kind; a variant request needs that variant packaged
on a bound asset of the same kind. No variant is required merely because of its name.
An asset exception uses `page-id/asset/kind[:variant]` and a nonempty reason, for example
`{"scope":"index/asset/logo:on-dark","rule":"missing","reason":"Light surface only"}`.
The bare scope `index/asset/logo` covers every logo request on that page; the variant scope
covers only `logo:on-dark`. The `inventory-asset` rule is also accepted. Earlier `page-id/kind`
exception scopes remain supported for existing inventories.
Findings use `inventory-construct`, `inventory-slot`, `inventory-state`, and `inventory-asset`;
an exception names that rule (or `missing` for missing findings), its reported scope, and a nonempty reason. An exception on a
construct also covers its slots/states for that rule. Covered findings remain in the report.
The same report also includes the language's validation findings, including coverage advisories;
acceptance covers both sets. Every finding has `source: "inventory"` or `source: "language"`.
Inventory files are relative to the site repository root; language files are relative to the
library root. Resolve each pointer in its source's file. Apply preserves these labels in its
report, task and findings display. Drafting inventories
from a BFF contract is deferred until the target BFF is decided (D3).
If the inventory file is absent, Apply and inventory-check stop with a message identifying the
file to create and the requirements it should list. Site findings remain unknown until it exists.


Open `/apply` to choose a language and a local Git repository. **Create hand-off** builds and
shows the bundle, findings, export and requested screenshots without JavaScript, through the same
operation as the CLI. **Review inventory findings first** retains the step-by-step review/export
path. Equivalent command:

```sh
python -m kinbase_design apply harbor --site /path/to/site --adapter generic --target-dir theme --page-url http://localhost:3000/
```

The command prints its private `handoffs/<id>/` bundle path. It contains exported files,
`findings.json`, a Factory `TASK.md`, and before/after images for each requested page URL at the
capture widths. After images are explicitly labelled **injected previews**, not the site's real
build. Screenshots reuse the anonymous capture worker: HTTP(S), including local servers, no
cookies or credentials, bounded requests and process cleanup. Chromium failure is an error,
never a passing screenshot report. Omit `--page-url` for an offline bundle without screenshots.

With `--branch`, Apply creates `kinbase-design/<language>-<hash8>` in the target repository,
commits the export under the target directory, and leaves the site's checkout and unrelated work
alone. It uses an isolated temporary worktree and never pushes, merges, opens remote PRs, or
deploys. An existing branch with that name is reported rather than overwritten. Uncovered
inventory findings stay in the hand-off for the implementer; a hand-off is not deployment approval.

## Kinbase adapter (M4)

The library and viewer display the adapter's direction/standards state. All journeys remain
usable when the binary or initialized repository is unavailable; badges include the reason.
Kinbase is not initialized for this design repository, and no design logical keys have been
established. Nothing is auto-initialized, ratified or promoted. Optional configuration:

```toml
[kinbase]
binary = "/path/to/kinbase"
repo = "/path/to/kinbase-initialized-repository"
decision = "Choose design standards for this project"
# Replace these placeholders with keys registered by the Kinbase owner.
standard_keys = { "design-scope" = "<your-standard-logical-key>" }
direction_keys = { "site-scope" = "<your-direction-logical-key>" }
```

The adapter reads `kinbase explain <key> --repo <repo> --decision <decision> --json` and retains
state, current statement/standing/scope/fact ID, trust, and owned Unknowns. Availability requires
a configured executable and a successful read-only `kinbase fsck --repo <repo> --json`; failure
reports the failing step. No repository-marker or version probe substitutes for fsck. Kinbase
itself remains responsible for trust and authority. Calls use argument arrays, bounded time/output, and no credential lookup.
A conflict or untrusted projection supplies no fixed values. Scope matching is exact against
the configured scope; no organization-wide authority is inferred.

**Proposed convention, awaiting confirmation with the Kinbase owner (G2):** a current,
authoritative, in-scope standard may contain JSON such as:

```json
{"kinbase-design":{"values":{"/style/color/brand/$value":"#0b6e65"}}}
```

These RFC 6901 pointer assignments enter generate as fixed inputs. Statements may also carry
closed generate dimensions, for example
`{"kinbase-design":{"dimensions":{"hue-family":200}}}`; `dimensions` and `values` are independently
optional. Fixed dimensions are settled from the start, displayed as **Fixed by Kinbase**, and
excluded from interview options and A/B rounds. Interview answers and choices cannot replace them.

Each affected value receives `{"kind":"source","artifact":"kinbase:<fact_id>","location":"..."}`
provenance in both workspace and library. The location is `/kinbase-design/dimensions/hue-family`
for that dimension, or `/kinbase-design/values/~1style~1color~1brand~1$value` for the example
pointer (RFC 6901 escaping). Dimension ownership covers the tokens and direct properties that
that dimension determines; dependent fixed inputs are retained when a value has multiple owners. Generated brand
colour normally aliases primary; the example fixes that brand value on prominent actions and
headings. A standard may assign a complete token object when introducing new tokens. Language
validation still applies: a standard cannot make an invalid value pass. Conflicting fixed
sources are reported instead of altering supplied values. Every other authoritative statement
is shown verbatim as **not machine-applicable — apply manually**. Lower-standing facts appear
as suggestions. Generate reads every configured standard key when starting a session. Derive reads them again
and replaces the session snapshot with the current results; new fixed dimensions also invalidate
incompatible pending pairs. Choices and repair cannot rewrite fixed values.

The viewer records comments/flags in private `feedback.jsonl` (author, versioned target, text,
time). When available it submits through `kin kinbase submit --repo ... --type concept|question`
with agent provenance; when unavailable it reports **not sent (Kinbase unavailable)**. The UI
shows the actual receipt/error. Propose as direction mints the language and submits a decision
naming its version and configured scope; **received** never implies **current**. Owned Unknowns
from explain can be explicitly routed with `kinbase questions ask <id>`. No feedback action
changes fixed inputs, validation outcomes or current direction on its own. There are no pushes,
merges, deployments or automatic authority promotions.
