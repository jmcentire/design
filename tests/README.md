# Independent M0 and M1 acceptance tests

Authority: `docs/design/SPEC.md` B1–B3, B9, B15–B16; the run's M0 public
contract; vocabulary contract amendment 01 (Q-0001-289a1e06d3c3) and
breakpoint/HTML identity amendment 02 (Q-0005-4b7b08a45c9e).
Tests are normative. Expected presentation values are hand-authored in
`fixtures/language.json`. Vocabulary ids, slot defaults and declared states come
from the public `vocabulary` command, using amendment 01's shape. No candidate
language, implementation or Coder test supplies expected values.

Run from the candidate repository with Python 3.12 and the supplied packages:

```sh
python -m pytest tests -m 'not browser'
python -m pytest tests -m browser
```

The browser selection requires installed Chromium and permission to launch it
and bind loopback sockets. The Tester sandbox cannot do those things; the
Validator runs this selection. Nothing is installed or fetched by these tests.
Tests create fresh temporary libraries under an unrelated project directory,
copying only the candidate's public `library/vocabulary/` data. Product and
vocabulary absence is an error, never a passing skip.

The table records the initial authoring evidence; subsequent Validator results
are retained below.

| Invariant | Oracle / boundary | Falsifier | Evidence status |
| --- | --- | --- | --- |
| B2: R1–R4 and other composition errors identify invalid input | Direct rules; real CLI and JSON findings | Accept invalid refs/types, conceal failure behind accepted=true, report wrong field | Gap: no candidate |
| B1: variants preserve the semantic contract | Direct R5; valid wrapper followed by one-defect variant | Drop/duplicate/reorder slots, add semantics or content | Gap: no candidate |
| B1: default HTML identity / variant meaning | Amendment 02; byte comparison and relational Chromium accessibility/text/slot/focus-order observations | Embed language identity in HTML; ignore variant or alter meaning | Gap: no candidate/browser run |
| B3: fallback and resolution | Authored token values; CLI sequence and Chromium computed style | Stale override after deletion, wrong source, one-hop aliases, wrong specificity | Gap: no candidate/browser run |
| Breakpoint boundaries | Amendment 02 and authored 768/1280px tokens; CLI contexts and browser widths below/at/above | Apply breakpoint early or late, prefer smaller breakpoint | Gap: no candidate/browser run |
| Immutable reproducible versions | Independent rfc8785 + SHA-256, persisted versions | Hash whitespace/name or omit facts/assets, overwrite old version | Gap: no candidate |
| B16: approved assets and private originals | Authored bytes and hashes; import/promote commands, real files, WSGI upload | Move/re-encode source, leak path, omit font weight/style gap | Gap: no candidate |
| B9: static pages and states | Vocabulary amendment 01; real no-JS Chromium, decoded images and custom font glyph evidence | Missing links/states, labels without state styles, font fallback, invisible focus | Gap: browser execution unavailable |
| B15: browse/compare/upload | WSGI output and actual files, real no-JS HTTP/browser controls | Omit language/frame/page, wrong width, redirect without promotion | Gap: no candidate/browser run |
| Configurable Git-subfolder library | Flag/env/TOML and precedence; validation and actual imported artifact | Read/write wrong project or private workspace | Gap: no candidate |

Files: `test_validation.py` covers composition errors, `test_resolution.py` covers
values/sources/precedence/removal, `test_versions_assets.py` covers minting and
assets, `test_preview_workbench.py` covers static output and WSGI/configuration,
`test_vocabulary.py` checks the pinned public vocabulary independently of its
consumers, and `test_browser.py` covers rendered and no-JS behavior. Browser tests start
the real CLI server and await its readiness line, or open static output by file
URL when serving is not the claim. The font fixture is a tiny real TTF generated
from authored geometric glyphs; it does not depend on a system font or network.

The first checkpoint command was `python -m pytest tests/test_validation.py -m
'not browser' -q --tb=short`: 33 setup errors, all at the explicit missing
`library/vocabulary` prerequisite. Syntax compilation succeeded. These errors
prove neither product correctness nor sensitivity to a behavioral defect.
There are no doubles, masks, retries, real-time sleeps, or mutation claims.

At the second checkpoint, the complete suite collected 82 tests. Running
`python -m pytest tests -m 'not browser' -q --tb=short` produced 74 setup errors
at the same missing vocabulary prerequisite, with 8 browser tests deselected.
Compilation and diff whitespace checks passed. The 8 browser tests collected
but were not executed, because the lane sandbox cannot launch Chromium or bind
sockets. All listed product invariants therefore remain **gap**. No test has
yet demonstrated a semantic red/green result against a candidate; the Validator
must run the exact integrated candidate/test commits. No candidate implementation
or other lane's tests were inspected. Full non-browser diagnostic output is in
`/tmp/kinbase-tester-m0-nonbrowser.log` on the Tester machine.

M1 rendered contrast, clipping, target sizes and logo legibility are outside
this M0 suite. The focus check demonstrates a visible CSS treatment, not its
contrast ratio. Variant semantics compare real browser accessibility output
between two independently specified inputs; there is no golden snapshot.

Final checkpoint: 93 cases collected; 84 non-browser cases attempted and all
errored at the missing candidate vocabulary prerequisite; 9 browser cases
deselected, not executed. New cases cover the public vocabulary, missing identity,
malformed JSON (retained corpus), deterministic truncation fuzz (seed 20261107),
and real pointer hover/active styles. Syntax and whitespace checks passed. The
fixture TTF was separately generated and decoded successfully: 4,680 bytes,
family `Fixture Sans`, 95 mapped characters. That diagnostic establishes only
fixture validity, not the application's font loading behavior.

The suite does not automatically judge the visual quality of the workbench's
thumbnail/swatch, its provenance-summary presentation, or annotation-toggle
usability. Those remain review gaps alongside the unexecuted product tests.
At the initial M0 handoff there were no outstanding contract questions; amendments
01 and 02 were reflected in the tests. The Tester remains available for source-free
Validator findings and later milestones.

Amendment 03 revision: all findings over parseable JSON now have their RFC 6901
pointer and observed value checked. R3 cases require the declaration itself or
its nearest existing ancestor, including omitted emphasis/role declarations.
`asset-font` cases check the requesting weight/style member for every
vocabulary-used role pair, component properties, slot properties and overrides.
Resolved property keys must belong to the closed CSS set; changing `surface`
must leave the resolved CSS unchanged. These are stronger expectations derived
from the ratified amendment, not edits to fit candidate output.

Revision checks: 104 cases collect; the non-browser run has 95 setup errors at
the absent candidate vocabulary prerequisite and 9 browser cases deselected.
Compilation, diff checks and the TTF decode diagnostic still pass. Full run
output is `/tmp/kinbase-tester-m0-amendment03.log`. Product evidence remains gap.
One contract question remains: malformed JSON has no JSON document into which an
RFC 6901 pointer can resolve. Its existing schema-failure assertions are retained,
but its pointer/observed convention awaits clarification rather than being guessed.

Validator browser review after amendment 03: the Validator reports 103 of 104
cases passed on the integrated candidate, and accepts the assertions as M0
evidence. The remaining failure is a product defect: a selected 768 CSS px
preview actually has a 766 px viewport. That exact-width assertion is retained
unchanged. The candidate commit was not supplied with this source-free result;
the Tester has not independently rerun that integrated tree.

Two additional regression checks follow the Validator's observed coverage gaps:

- A hand-authored SVG with only a `viewBox` is bound to listing-card media. It
  must decode, be visible, and have non-zero rendered width and height. Intrinsic
  `naturalWidth` is not used as a layout oracle for this shape.
- With window/preview widths 1280/1280, 320/320 and 320/1280, the preview retains
  its exact viewport width and its right edge must become visible. The test moves
  actual scroll positions only on user-scrollable ancestors, then hit-tests a
  point inside the iframe's right content edge. It never changes layout styles
  or scrolls overflow-hidden/clip containers to manufacture reachability.

These new regressions require a Validator browser run; no red/green result is
claimed for them yet. The previously reported exact-width failure remains
**falsified** until a subsequent integrated run demonstrates the repair.

Local checks after these additions: 108 cases collect, including 13 browser
cases. The 95 non-browser cases still stop at the absent candidate-vocabulary
prerequisite. Compilation, diff checks and the TTF diagnostic pass. Browser
execution remains delegated to the Validator because of sandbox restrictions.

Timeout repair after tester commit `1336c85`: the Validator reports that the
integrated run reached its 900-second timeout inside the right-edge helper.
The helper incorrectly awaited `requestAnimationFrame` in a JavaScript-disabled
context, where that callback never fired. No browser result from that run is
claimed. The helper now uses synchronous instant scrolling and synchronous
layout/hit-test reads, preserving the reachability and exact-width assertions.

Every browser-marked setup, call and teardown phase now has a 60-second host
deadline using POSIX `setitimer`, independent of page JavaScript and Playwright's
action timers. Expiry fails the current test phase; a repeating signal also
bounds cleanup entered while unwinding. Browser launch is limited to 15 seconds,
and page actions/navigation to 5 seconds. The deadline covers evaluate promises,
font/image waits and browser cleanup as well as normal actions. Unsupported
platform/thread configurations fail explicitly rather than silently losing the
deadline.

Local deadline diagnostics interrupted an unresolved asyncio Future inside a
real greenlet, and verified timer cancellation on completion. A separate pytest
subprocess (itself limited to 10 seconds) exercised actual setup/call/teardown
hooks with real SIGALRM signals: the three forced failures were reported and the
positive control passed. These are harness checks, not product evidence.

After this repair, all 108 cases still collect; compilation, whitespace and font
fixture diagnostics pass. The local non-browser attempt still has 95 missing-
vocabulary setup errors, with 13 browser cases deselected. The repaired browser
suite still requires an integrated Validator run.

M1 authoring uses the M1 public contract and amendment 04 (Q-0032-3ebdf42d7054).
The M0 closed-property assertion now includes the four newly ratified properties.
`test_m1_properties.py` validates those public inputs. `test_m1_contrast_assets.py`
uses an independent WCAG luminance calculation and authored colors at both sides
of the normal/large text thresholds, alpha composition, image/gradient review,
and correctly hashed corrupt asset bytes. `test_m1_behaviors.py` seeds actual
clipping, gallery overflow and crowded targets, checks declared exceptions,
verifies full title availability, and exercises missing/coverage acceptance.

The shipped Lantern package is an explicitly assigned test subject, copied at
test time into an isolated library. Its values are never used as an expected
design oracle. The design brief supplies those expected values, while its
required accepted baseline supports isolated acceptance/exception sequences.
No implementation or Coder tests are read. Each `check` subprocess has a 90-second
limit; M1 browser phases have a finite 240-second budget for multiple full preview
checks. M0 budgets remain unchanged. Rendered report fields, acceptance/counts,
and actual readable PNG screenshot artifacts are checked by `m1_support.py`.

First M1 checkpoint: 125 total cases collect. All 100 non-browser cases error at
the absent candidate vocabulary prerequisite; 25 browser cases are deselected.
Compilation and diff checks pass. These M1 checks have not been run against a
candidate and remain evidence gaps. Lantern design/role agreement and the M1
workbench report journey are still being authored.

M1 completion adds `test_m1_design.py` and `test_m1_workbench.py`. The former
compares authored slot values with both the resolver and real computed styles,
then tests Lantern against literal brief values at 320, 767, 768 and 1280px.
It checks stacked/beside media geometry, two-line title visibility and full text
on listing.html, relational variant semantics, real Instrument Sans glyph use,
and accepted `check` output. The public Lantern package must contain the stated
space-scale values and exact md/lg breakpoints; extra unrequested tokens are not
forbidden. Default-screen geometry assertions exclude the state gallery's empty
and loading depictions; gallery semantics and states retain their own checks.

The workbench test submits the real check form with JavaScript disabled, reads
the default hash-addressed report, follows actual screenshot links, checks
unresolved review, changes an authored color, submits again, and verifies the
latest panel/grid summary. It does not infer success from a redirect alone.
The existing keyboard test now covers all five pages, requires a visible focus
change and checks Tab reading order, retaining the accepted native-radio rule of
one Tab stop per group. Missing native controls cannot escape by setting tabindex
to -1. Existing no-JS navigation/state tests remain in place.

The M1 acceptance clarification is applied to the validation helper: a
needs-review finding is retained rather than misclassified as acceptance failure.
The new `check` tests separately require the exact unresolved count and show
that needs-review alone does not block an otherwise accepted Lantern fixture.
No failed finding is removed or relabeled to agree with candidate output.

| M1 invariant | Independent observation / falsifier | Current evidence |
| --- | --- | --- |
| Normal and large contrast, alpha composition | Authored colors + WCAG formula; exact reported ratio/threshold | Gap: browser run pending |
| Image/gradient uncertainty | Real background-image inputs must produce needs-review and unresolved counts | Gap: browser run pending |
| Clipping/scroll/target exceptions | Seed geometry, negative report, scoped exception still reported, full content retained | Gap: browser run pending |
| Missing/violation/coverage acceptance | Real command exit and report; coverage-only accepted, required missing rejected | Gap: browser run pending |
| Role agreement / asset loading | Distinct role/emphasis values; real corrupt bytes, real custom font glyphs | Gap: browser run pending |
| Check report and no-JS workbench | POST, persisted newest report, actual PNG link bytes, counts | Gap: browser run pending |
| Lantern brief | Literal values, viewport boundary geometry, semantic relation and accepted check | Gap: browser run pending |

At M1 completion, 140 total cases collect: 102 non-browser attempts stop at the
missing candidate vocabulary prerequisite, and 38 browser cases are deselected.
Syntax and diff checks pass. The TTF diagnostic still passes. Host deadline
diagnostics again fail setup/call/teardown stalls and pass both browser and
non-browser controls; the custom M1 budget is finite and tested. The independent
contrast calculation gives 4.48/4.54 for #777777/#767676 on white, 2.85/3.03 for
#999999/#949494 on white, and 3.95 for white on #808080. These calculations and
harness checks are not candidate evidence. Logs: `/tmp/kinbase-tester-m1-complete.log`
and `/tmp/kinbase-tester-m1-collection.log`.

No rendered role-conformance mismatch is artificially injected: the available
public language contract provides no legitimate alternate CSS path. The positive
agreement case checks every rendered fixture slot against independently authored
values and the resolver, as the M1 assignment permits. OCR is not used as an oracle.

M1 review repair: the Validator's integrated run at `bd6c3bd` reported 121 passed
and four failed. The clipping assertion exposed a product defect and is retained.
Three tester corrections follow the source-free review: screenshot evidence now
requires a valid, fully decodable PNG at least as wide as the CSS width, allowing
full-page overflow and device scaling; only alpha-composited contrast gets an
absolute 0.05 ratio tolerance (opaque comparisons stay exact); the crowded-target
fixture applies tiny treatment to every declared action slot and checks that its
overlapping undersized pair has no adequately sized same-destination links.
Legitimate remaining home-logo equivalents may retain their named exception.

After repair, all 140 cases still collect, compilation and diff checks pass, and
the local non-browser attempt still has 102 missing-vocabulary prerequisite errors
with 38 browser cases deselected. The Validator's 121 passes are prior integrated
evidence, not a rerun of this repair or the later `7692c96` additions. Repaired
browser execution remains pending. Local logs:
`/tmp/kinbase-tester-m1-repair-collection.log`, `/tmp/kinbase-tester-m1-repair.log`.

Amendment 05 adds `test_m1_review_queue.py`: independently seeded opaque contrast
violations and image/gradient reviews must each group to one finding across
rendered pages and widths. Expected occurrence coordinates come from visible
public preview slots, not from the report. A breakpoint changes the unresolved
surface and requires separate groups; a different target remains separate even
with the same surface. The workbench sequence now expects one grouped price
violation and still compares its latest summary with deduplicated report counts.
The shared report helper checks nonempty occurrence arrays, first-occurrence
fields, every occurrence's page/width and decodable screenshot, and counts review
rows rather than occurrences. Each distinct screenshot is decoded once.

The native-control exclusion uses a language with no authored boundary treatment
and compares visible checkbox/radio appearance with a plain native control in a
separate real Chromium document. It requires an actual native control, then
rejects non-text-contrast findings for those slots on the observed form page;
other state depictions are not assumed to retain the same appearance. Existing
keyboard, focus and target-size checks remain unchanged.

After amendment 05, 145 tests collect; compilation and whitespace checks pass.
The non-browser attempt still has 102 missing-vocabulary prerequisite errors,
with 43 browser cases deselected. New rendered assertions await integrated
execution. Logs: `/tmp/kinbase-tester-amendment05-collection.log` and
`/tmp/kinbase-tester-amendment05.log`.

Paint-evidence repair: the Validator ran tester `0002773` against integrated
candidate `21723bb` (endgame `cb919298`): 143 passed and two test-side failures.
The title line counter now requires the text rect's vertical midpoint inside
the title box, avoiding an empty ascent sliver counted as a third visible line.
This preserves the two-line limit and full-content checks.

Native checkbox/radio evidence now visits search.html and states.html and compares
decoded element screenshot pixels with the same native input type, state and
dimensions in a blank Chromium document. Subpixel placement is matched; computed
CSS equality is no longer the oracle. The test requires a pixel-identical example
and excludes mixed native/author-painted slot-page groups from its exclusion
assertion. A second input is styled through working.json with a low-contrast
background/border; it must paint differently and receive a non-text-contrast
violation, guarding against suppressing all control checks. Screenshot calls have
five-second timeouts and the existing host phase deadline remains in force.

All 145 cases still collect; syntax and whitespace checks pass. The local
non-browser run has 102 missing-vocabulary prerequisite errors, with 43 browser
cases deselected. The 143 integrated passes are prior evidence; these repairs
still await the Validator's browser rerun. Logs:
`/tmp/kinbase-tester-paint-repair-collection.log`, `/tmp/kinbase-tester-paint-repair.log`.

Native-backdrop correction: the reference document now uses the preview input's
effective ancestor background color. Chromium canvas composition combines ancestor
color layers, including alpha, over the default white canvas. The input's own
background is excluded so authored control paint remains detectable. The fixture
requires a solid backdrop rather than silently approximating image backgrounds.
This removes background-only differences at anti-aliased native-control edges.
The styled-control positive assertion remains unchanged.

After this correction, 145 tests collect and syntax/whitespace checks pass; the
non-browser attempt still has 102 missing-vocabulary setup errors and 43 browser
cases deselected. Browser verification remains pending. Logs:
`/tmp/kinbase-tester-backdrop-collection.log`, `/tmp/kinbase-tester-backdrop.log`.

Amendment 06 keeps the Lantern variant-switch assertion: dangling part treatments
are advisory coverage. The closed property set and positive validation input now
include border-style. The authored-control test sets a solid border, measures all
four native input edges and its background, independently computes their contrast
against the adjacent surface, requires it below 3:1, and checks the reported ratio.
This replaces a precondition based only on differing screenshots. Validator run
573f147f had 143 passes and the two reviewed failures before these amendments;
the amendment changes still require integrated execution.

M2 first checkpoint (public contract + amendment 07): test-owned HTML/CSS lives
under `fixtures/sites/`, with a deterministic test-authored TTF generated at runtime.
The editorial source supplies four known colors, sizes 16/20/25/31.25px (ratio 1.25),
8px spacing, 8/16px radii and an 800px breakpoint. It includes a rotated layout that
the closed language property set cannot directly express. A minimal partial source
and unchanged DTCG input are retained for the remaining question/import journey.

`test_m2_capture.py` exercises real HTTP/Chromium capture, immutable capture files,
configured widths plus media-query widths, independently calculated CIEDE2000
distances, extracted token values, font/radius/type/space facts, reconstruction
pairs, and coverage/question visibility. The source starts returning 503 after
capture; later draft/fidelity commands must make no further requests. Separate
cases retain instruction-looking text as data, compare it with equal-length
ordinary text, reject credential/cookie presentation, and expose network/browser
failures within finite deadlines. A server-provided cookie probes the explicit
M2 promise that capture never presents cookies. Missing Chromium is induced through
Playwright's real browser-installation configuration, not a patched browser.

All source requests are handled by a temporary test-owned HTTP server; no external
site, LLM or network service is used. Ambient LLM command configuration is removed
by the harness unless a test explicitly supplies it. Default M2 phases are bounded
at 420 seconds, CLI stages at 90 seconds (failure probes at 30), and source capture
configuration at 8 seconds. Existing M0/M1 deadlines are retained.

151 cases collect; compile/whitespace checks pass. The non-browser attempt still
has 102 absent-candidate-vocabulary setup errors, with 49 browser cases deselected.
Independent helper diagnostics checked CIEDE2000 against the standard 2.0425 Lab
example, identity/symmetry, and the generated font's family/95-character cmap.
These diagnostics are not product evidence. M2 browser execution and the remaining
import/provenance/questions/workbench tests are still pending. Logs:
`/tmp/kinbase-tester-m2-first-collection.log`, `/tmp/kinbase-tester-m2-first.log`.

Amendment 08 retains the existing 127.0.0.1 capture sources and adds localhost as
a positive target. Negative cases exercise file/data/javascript/chrome/ftp schemes
and embedded user/password credentials. Refusal requires a clear diagnostic or
reported capture problems with no captured pages; the credential-bearing URL must
never reach the test server. No internet/LAN service or real credential is used.
158 cases collect; compile and whitespace checks pass. Local non-browser execution
still stops at 102 missing-vocabulary prerequisite errors; 56 browser cases are
deselected. Logs: `/tmp/kinbase-tester-amendment08-collection.log` and
`/tmp/kinbase-tester-amendment08.log`. The provenance map/granularity clarification
is still pending; no provenance coverage semantics have been guessed.

M2 completion follows amendment 09: provenance is a direct pointer map, with the
nearest ancestor record covering a design leaf and the stated metadata excluded.
`test_m2_imports.py` checks all import-kind originals, unchanged DTCG values and
source attribution through save, and Figma variables/images/fonts after deletion
of the external export folder. Retained Figma originals are reimported through the
existing public file-import operation for promotion; no unpinned directory-member
selector is assumed. Shared provenance uses the hash independently calculated by
the M0 oracle. Library bytes/data are inspected for source URLs and private paths;
provenance pointer keys and permitted selector/JSON-pointer locations are treated
as data rather than mistaken for filesystem paths.

`test_m2_questions.py` captures a sparse source, verifies 2–4 distinct rendered
candidates, answers a different value, supersedes it, and checks effective `chosen`
provenance and the final saved value. Candidate paths may be absolute in the
workspace, workspace-relative or draft-relative (the contract does not pin a
relative base); no matching path outside the workspace is accepted. Image evidence
proves decodable, distinct candidate paint; HTML previews also expose the relevant
construct hook. Capture originals and source provenance remain local and unchanged.

`test_m2_workbench.py` drives visible no-JS forms and links through URL entry,
capture review, draft/listing, fidelity, a question and library save. Intermediate
routes are discovered from the page, not guessed. POSTs must redirect, and each
operation is corroborated by its persisted public artifact. A real refused TCP
connection supplements the HTTP failure and missing-Chromium cases. The text-as-
data relation compares resolved token values and role mappings without pinning
incidental token names; font-stack quoting and DTCG color-object representations
are normalized when comparing design facts, while imported token values stay exact.

At this checkpoint 169 cases collect. Syntax/whitespace checks and diagnostic
nearest-ancestor/metadata/missing-coverage examples pass. Local non-browser runs
have 108 absent-candidate-vocabulary setup errors, with 61 browser cases deselected.
No M2 candidate pass is claimed; all rendered execution remains an evidence gap
for the Validator. The previously reported M1 143 passes precede amendment 06 and
the new M2 work. Logs: `/tmp/kinbase-tester-m2-journey-collection.log` and
`/tmp/kinbase-tester-m2-journey.log`.

M2 real-site regressions add a static large-page template expanded into 5,000
neutral elements before four distinctive late colors. Browser preconditions
verify DOM position and below-screen geometry; both measured palette and actual
draft tokens must retain the authored colors within ΔE tolerance. A separate
fixture supplies negative margins, ordinary spacing, an 8px card radius and a
9999px pill. Its measured spacing and spacing tokens must be nonnegative, and
reported/used radii cannot exceed the source's largest radius plus tolerance;
geometric pill normalization is permitted.

The shared draft driver now validates an isolated copy through the public
`validate` command, including any packaged draft assets, before returning it.
This does not save or mutate the original draft. The sparse-source question case
also requires successful fidelity and its screenshot pairs before answering any
question; fidelity may add further questions without invalidating the initial
draft's reported question count.

171 cases collect; compilation and whitespace checks pass. Local non-browser
execution still has 108 missing-vocabulary setup errors, with 63 browser cases
deselected. The Validator reports its M2 run blocked on the product's loopback
capture fix; these additions have no integrated pass claim. Logs:
`/tmp/kinbase-tester-m2-large-collection.log`, `/tmp/kinbase-tester-m2-large.log`.

The Validator subsequently reports 168/171 passing on candidate `5c008af`
(endgame `f8e222fd`). The remaining spacing-base, clean-large-capture and visible
promotion-control failures are accepted product defects; their assertions stand.

`test_m2_concurrent_capture.py` exercises a real local page with 48 subresources:
36 images, six stylesheets and six font files. Each resource response has a
deliberate 200ms boundary delay. Completion must capture both configured widths,
request all resources with overlap, and finish within 30s against a 40s capture
bound. A second case holds resource responses while terminating only the public
CLI, then requires its observed descendants to exit within five seconds. Numeric
process ancestry and birth times identify this test's processes; macOS kqueue
exit events bound the wait. Forced process-group cleanup occurs after observation,
so cleanup cannot satisfy the cancellation assertion.

173 cases collect; compilation and whitespace checks pass. Non-browser execution
still reports 108 absent-vocabulary setup errors, with 65 browser cases deselected.
A local diagnostic confirms the exit watcher rejects a living child and detects
its exit. The sandbox denies `ps`, so process-tree inspection and the two new
browser cases await the Validator; no integrated pass is claimed for them. Logs:
`/tmp/kinbase-tester-fanout-collection.log`, `/tmp/kinbase-tester-fanout.log`.

M3 first increment (`test_m3_choices.py`, `test_m3_derive.py`) uses the public
amendment 10 value domains and settled-support schema. A/B decisions and a
superseding revision must append exactly one log record without changing earlier
bytes; settled values and later candidates must follow the effective decision.
Beach candidates use an independently defined broad green/turquoise/blue interval
of 90–255 degrees, rather than exact generated colors.

Two early-stop cases derive after zero or one comparison with a tester-authored
PNG logo, a real generated TTF and exact DTCG palette colors. Every pair of source
palette colors has contrast below 3:1; the delivered result must preserve those
values and sources while independently passing `validate` and rendered `check`
at 320/768/1280. Packaged bytes, bindings, actual loaded font use, visible logo,
all-value provenance, private originals and shared-data privacy are checked
through derive and save. This establishes readable output with fixed constraints;
it does not claim the internal repair loop necessarily executed.

177 cases collect, compile/whitespace checks pass, and the non-browser run retains
108 missing-vocabulary setup errors (69 browser cases deselected). No new M3
candidate pass is claimed. Logs: `/tmp/kinbase-tester-m3-collection.log` and
`/tmp/kinbase-tester-m3.log`. Remaining M3 coverage: rejected-pair widening/cap,
rendered pair isolation, interview/moodboard and the no-JS workbench journey.
The widening case needs a contract answer on revisiting rejected dimensions
before the cap; eight one-dimensional rounds could otherwise visit distinct
members of the nine-dimensional domain without exercising widening at all.

M3 amendment 10 item 5 adds an eight-round rejection sequence. Immediately
following `neither`, the same dimensions must return with larger domain distance;
exhausted numeric ranges retain their maximum and an exhausted pair gives way to
other unsettled dimensions. Categorical alternatives cannot reuse the last
rejected values while unused alternatives remain. Repeated rejection never
settles a value and the default cap stops new rounds without changing history.
A separate revision from `neither` to B verifies normal sequencing is restored.

`test_m3_workbench.py` runs the no-JS generate journey using visible forms/links:
upload, a visual interview answer, mood-board pin/remove, A/B plus comment,
revision, early derive, rendered review and library save. Public workspace files
corroborate each mutation; no generate CLI command drives the journey. Inline
CSS samples, loaded images and nonempty frames are supported as visual choices.
Draft validity and provenance are independently checked before saving.

180 cases collect; compilation and whitespace checks pass. The non-browser run
still has 108 missing-vocabulary setup errors, with 72 browser cases deselected.
These new cases await the Validator. Logs:
`/tmp/kinbase-tester-m3-journey-collection.log`, `/tmp/kinbase-tester-m3-journey.log`.
The remaining rendered-pair isolation test needs the public inspectable preview
surface and dimension-to-rendered-property contract, particularly for formality
and whimsy; labels/JSON values alone cannot establish what actually changed.

M3 amendment 11 resolves candidate inspection. `preview` now identifies the exact
workspace directory `sessions/<session>/candidates/<hash>/`, with working copy,
`sample.html`, stylesheet and assets. All pair drivers enforce this shape. The
workbench journey also validates every materialized language-backed swatch it
encounters, without treating a plain inline CSS palette strip as a full language.

`test_m3_rendered_pairs.py` walks the offered rounds through real Chromium with
JavaScript disabled, validates each candidate in isolation and reads the public
candidate route. It compares decoded screenshots, identical default-variant HTML
under B1's binding conditions, semantic/content observations and computed
properties. Width comparison uses CSS Typed OM's computed auto/percentage values,
not reflow-dependent used widths; unchanged em-based UA heading margins may scale
with type size. Unrelated typography, spacing, radii, opacity, transforms and
filters remain fixed. Relations cover primary hue/chroma, alpha-composed
text/surface lightness, consecutive role-size ratios, spacing/radius ordering,
label case/title tracking, and attention/primary hue distance. The beach base hue
is checked in actual rendered color as well as candidate values.

The public cap does not promise all nine dimensions within eight rounds; the test
records the dimensions actually observed in `rendered_dimensions`. Generic/common
system font stacks are checked for serif/sans compatibility. Unknown custom
family names are retained as `font_genres_needing_review`, rather than guessed from
their spelling; the typography comparison still requires different computed
families, and supplied-font loading/use has independent coverage. No OCR is used.

181 tests collect. Compilation and whitespace checks pass. Counterfactual helper
diagnostics accept a hue-only change, reject an unrelated font-size change and
measure a 60-degree attention offset. These diagnostics validate only the oracle,
not the product. The non-browser run still reports 108 missing-vocabulary setup
errors; 73 browser cases are deselected. Real M3 execution awaits the Validator.
Logs: `/tmp/kinbase-tester-m3-rendered-collection.log` and
`/tmp/kinbase-tester-m3-rendered.log`.

M2 amendment 12 / real-site fidelity regression adds the tester-authored `cards`
site: two pages, six distinct media/title/meta/price cards in non-alphabetical
order, green prices (`#0b6e4f`) and rust section headings (`#a14524`).
`test_m2_fidelity_content.py` first verifies the source preconditions, captures
both pages, makes the source unavailable, then inspects every reconstructed pair
through its reported `html` path and the public workbench fidelity route at
320/768/960 CSS px. It requires each page's own heading, introduction and section;
three construct instances in captured order with matching titles, meta,
accent text and visible media; and actual rendered accent text within configured
ΔE2000 tolerance. Every visible text fragment must occur in that page's source,
which rejects generic vocabulary/lorem copy without learning sample strings from
the product. Captures must remain unchanged and later rendering must not contact
the live source. No OCR or report palette assertion substitutes for DOM/paint.

182 cases collect; syntax and whitespace checks pass. A local fixture diagnostic
checks the six authored card tuples and local resource references; independent
color-distance diagnostics confirm grey fails both accent tolerances. These are
fixture/oracle checks, not product results. Non-browser execution retains 108
missing-candidate-vocabulary setup errors, with 74 browser cases deselected.
The new reconstruction check awaits the Validator's real-browser run. Logs:
`/tmp/kinbase-tester-fidelity-content-collection.log` and
`/tmp/kinbase-tester-fidelity-content.log`.

Amendment 13 supersedes the specialised fidelity mapping assertions. The fidelity
checks now locate each reconstructed group by its captured contents, require one
consistent vocabulary construct per source group in source order, and impose no
construct id, root tag, or price-slot requirement. All captured visible copy must
survive and no invented copy may appear. Titles retain a measurable prominence
cue over meta (size, weight or foreground/surface contrast). Media stays visible;
for decoded img elements, interior color samples are compared with the source
using the configured color tolerance, catching a substituted placeholder as well
as an empty box. Accent text is selected by captured content, not domain meaning.

The retained source examples are supplemented with editorial articles, events and
team members without currency/price/rating text. These use article, li and div
source groups and include prose as well as meta and short highlights. A separate
relation captures two pages with identical markup/presentation but substitutes
booking, beds, nights, discount, currency and rating-like text. Monospace word
metrics are matched, and browser geometry/style equality is a precondition. The
independent captures/drafts must produce identical construct/slot/role/emphasis
mappings, while preserving each input's own text. The generic `card` vocabulary's
explicitly pinned slots/defaults are checked separately through the public CLI;
its article root is not assumed by the generic fidelity invariant.

185 cases collect; compilation and whitespace checks pass. Local diagnostics
confirm all 21 authored item tuples, local resource references, non-commerce input
copy, the text-substitution pair's markup/word metrics, and the grey-accent
negative control. Real rendered geometry/mapping checks await the Validator.
Non-browser execution reports 109 missing-vocabulary setup errors; 76 browser
cases are deselected. Logs: `/tmp/kinbase-tester-generic-fidelity-collection.log`
and `/tmp/kinbase-tester-generic-fidelity.log`.

Amendment 13's blog/travel-guide addendum adds a full journal entry with nested
sections and a walking guide with an ordered route, narrative prose and practical
directions. Neither contains prices, ratings or booking actions. Both use the
same generic reconstruction assertions as the other sources: no domain-specific
mapping oracle or root/slot requirement. Capture, offline draft validation and
fidelity run for both pages at every captured width. Lost prose, flattened or
reordered groups, missing media and grey accents fail those shared checks.
The shared checks now also compare accessible heading text/order and the relative
heading levels against the source, allowing native or ARIA headings and absolute
level shifts while rejecting a hierarchy flattened into plain text.

186 cases collect; compilation and whitespace checks pass. Fixture diagnostics
confirm both pages' authored headings/content, local resource references and
absence of commerce signals. Non-browser execution remains blocked by the absent
candidate `library/vocabulary`: 109 setup errors, 77 browser cases deselected.
Real browser checks await the Validator. Logs:
`/tmp/kinbase-tester-guide-collection.log`, `/tmp/kinbase-tester-guide.log`.

M3 amendment 14 extends every observed materialized candidate check to require
the manifest's `assets/sha256/<hex>` files within that candidate directory, with
independently computed SHA-256 matching the declared name. Existing rendered-pair
and interview-swatch validation now copies the whole directory unchanged into a
separate library with a fresh workspace, rather than sharing session originals.
A focused supplied-logo/font case copies both A/B candidates, removes the external
originals and moves the session workspace out of reach, then runs public validate
and build-preview on each copy. The rebuilt pages must actually load/use the
supplied font and visibly render the logo. This catches candidates that work only
while their generating session exists, or include preview URLs but omit the
content-addressed package files. All process and browser waits remain bounded.

187 cases collect; compilation and whitespace checks pass. Non-browser execution
still has 109 setup errors from absent candidate `library/vocabulary`, with 78
browser cases deselected. The candidate portability and rendering assertions await
the Validator. Logs: `/tmp/kinbase-tester-portable-collection.log` and
`/tmp/kinbase-tester-portable.log`.

The Validator's lazy-media/grid regressions add `test_m2_lazy_grid.py` and a
generic visual-journal fixture under `sites/lazy/`. Six individually colored SVG
originals sit below a 5000px introduction, with native `loading="lazy"` and a
separate IntersectionObserver/placeholder version. A separate JS-enabled source
browser scrolls each image into view with bounded waits and independently verifies
its decoded pixels and card positions. Product capture starts in its own browser;
the test's scrolling/cache cannot prepare that session for it.

Capture must offer all six originals and its full-page screenshots must paint
their known colors at the independently observed source image centers. At every
captured width, including 390, 768 and 1280, the offline reconstruction must retain
one construct per source group, source order, decoded/visible media and its painted
colors. Card boxes must retain the source row membership (six single-card rows
below 768; two three-card rows above), allowing 2 CSS px of fractional alignment
rounding and rejecting overlapping columns/rows. Exact sizes or layout mechanisms
are not prescribed. The source is unavailable throughout drafting and fidelity.

189 cases collect; compilation and whitespace checks pass. Local fixture/oracle
diagnostics verify all media bindings, local references and authored content,
distinguish wide/narrow row arrangements, and reject the grey placeholder. These
are diagnostics, not product/browser evidence. Non-browser execution remains
blocked by missing `library/vocabulary` (109 setup errors; 80 browser cases
deselected). Validator browser execution remains required. Logs:
`/tmp/kinbase-tester-lazy-grid-collection.log`, `/tmp/kinbase-tester-lazy-grid.log`.

Validator run 9ff11255 (tester 611fd2d, candidate 06a394f) reported 184/189.
Two test-side repairs follow its ruling: the shared privacy scan now excludes
only package asset bytes under `assets/sha256/*`, since B6 requires originals
unchanged and an SVG's XML namespace is not a B8 metadata leak. Working copies,
provenance and other library text remain scanned. The no-JS generate locator now
spells its A/B slash as a regex Unicode escape to avoid Playwright's selector
delimiter error while matching the same accessible labels. Neither-widening and
whimsy assertions remain unchanged; the other three failures were product-side.

189 tests still collect; compilation and whitespace checks pass. Local diagnostics
accept an unchanged SVG asset while rejecting injected URL/workspace paths in
working.json, provenance and other library text, and verify the slash-free pattern
still matches A/B labels. Non-browser execution remains blocked by the absent
candidate vocabulary (109 setup errors, 80 browser cases deselected). Browser
rerun is pending the Validator. Logs: `/tmp/kinbase-tester-review-repair-collection.log`
and `/tmp/kinbase-tester-review-repair.log`.

Validator run 7b0057b3 (tester 97d97a8, candidate c02f854) reported 188/189.
The remaining test-side failure assumed particular words in the comment label.
The A/B helper now finds the selected choice control first, then a visible,
accessibly named textbox in that control's form. Any label wording is valid;
unrelated textboxes elsewhere on the page are excluded. Both the initial choice
and its revision must retain the exact submitted comment in the append-only log.
The original comment assertion is unconditional, and revision retention is now
asserted explicitly too.

189 cases collect; compilation and whitespace checks pass. Non-browser execution
still stops at the missing candidate vocabulary (109 setup errors, 80 browser
cases deselected). Browser rerun awaits the Validator. Logs:
`/tmp/kinbase-tester-comment-form-collection.log`, `/tmp/kinbase-tester-comment-form.log`.

The Validator's real beach-session review adds independent perceptual oracles in
`m3_perceptual_support.py` and `test_m3_perception.py`. These numerical cutoffs are
tester-chosen operational criteria requested by the review, not WCAG thresholds:

- Each offered A/B pair must change at least 1% of its common full-page pixel
  extent by >=16/255 in at least one RGB channel, after a 0.5px blur suppresses
  raster noise. Equal viewport widths are required; added blank height cannot
  count. This is materially stronger than unequal screenshot hashes while
  allowing typography/shape choices to change less paint than page recoloring.
- Every advertised dimension must change its own computed properties on a heading
  of at least 24px, a primary action of at least 24x24px, or a surface/layout region
  occupying >=10% of a viewport. That element's rendered crop must also change
  by >=0.5%; invisible radius/border changes cannot supply the prominent effect.
  Inherited text color on an otherwise unchanged large wrapper is insufficient.
- Both initial beach candidates and a language derived before any choices must
  paint hues 90–255 degrees on a primary action and predominantly on at least one
  large surface. Saturation >=0.2 and a channel spread >=20/255 exclude grey or
  imperceptibly tinted near-white. Labels must avoid uppercase, and the existing
  amendment-11 >=60-degree attention/primary relation verifies whimsical seeds.
  Supplied palettes and later user choices are not overridden by these checks.
- The no-JS mood board must have three mutually distinct pin-associated visual
  specimens, each pair differing by >=3% on an aspect-preserving normalized
  canvas. Image/frame/SVG specimens are compared directly, avoiding surrounding
  caption differences where possible; CSS specimens remain supported.
- Every default preview page and observed candidate sample is checked for the
  review's prohibited domain copy (listing/booking/rating/destination terms and
  common booking/occupancy phrases) in visible text and accessible labels. This
  bounded lexical oracle deliberately excludes vocabulary hooks, routes and
  captured/user-authored copy; it does not claim general semantic classification.

The existing computed-style isolation and dimension relationships remain in place.
191 cases collect; compilation and whitespace checks pass. Diagnostic images
confirm rejection of tiny/noisy changes, blank added height, grey, near-white and
off-brief hues, while recognizing a substantial blue region. Those diagnostics
are not product/browser results. Non-browser execution remains blocked by absent
candidate vocabulary (109 setup errors, 82 browser cases deselected). The real
rendered checks require the Validator. Logs:
`/tmp/kinbase-tester-perceptual-collection.log`, `/tmp/kinbase-tester-perceptual.log`.

Validator run 3858c5ae (tester b88094e, candidate 5d20f66) reported 186/191.
Amendment 10.6 replaces abstract-domain exhaustion with the pair's published
`variation.<dimension>.widest`. The driver verifies each reported distance against
the candidate values. After neither, the next pair must include every non-widest
dimension with greater distance and omit every widest dimension, including mixed
pairs; rejected dimensions remain unsettled. The usable range is product-published,
not inferred from the domain maximum. This supersedes the earlier widening oracle.

Three test-side repairs also follow the ruling. The neutral-copy scanner excludes
complete construct/state identifier captions for constructs actually depicted,
while still scanning the state specimens and all other prose. Density permits
`margin-block` and observes it as spacing; UA em-based margins caused by an
independent type-scale change retain their prior exception. Workbench revision
first finds inline forms carrying the previous choice id, regardless of field name,
and submits their visible B choice. Separate history/edit navigation is supported
when present, but is not required. Read-only `settled` output corroborates changed
values and the new supporting choice id; the append-only log must retain the first
comment and superseding revision. If a revision form offers a comment field its
submitted text must persist; a quick revision without a comment field is valid.
The initial choice still requires comment entry/retention. The home-page whimsy
failure remains product-side and its assertion is unchanged.

191 cases collect; compilation and whitespace checks pass. Non-browser execution
remains blocked by absent vocabulary (109 setup errors, 82 browser cases
deselected). Validator browser rerun is required. Logs:
`/tmp/kinbase-tester-variation-repair-collection.log`, `/tmp/kinbase-tester-variation-repair.log`.

Validator run b662ad1d (tester 178b3ed, candidate c9bb407) reported 190/191.
Amendment 11b permits skipped modular type steps. The type-scale oracle now checks
subtitle/body against the selected ratio with absolute tolerance 0.02, infers the
integer title/subtitle exponent from measured sizes, and checks ratio^k with
relative tolerance 0.02. The exponent must be >=1 and identical in both candidates;
fractional steps or changing the step count between A/B still fail. No role size
or particular exponent is pinned to the candidate's observed implementation.

191 tests collect; compilation and whitespace checks pass. Local arithmetic
diagnostics cover one-step and skipped-step scales, fractional-step rejection and
different inferred exponents. Non-browser execution remains blocked by absent
vocabulary (109 setup errors, 82 browser cases deselected). Browser rerun awaits
the Validator. Logs: `/tmp/kinbase-tester-type-scale-collection.log` and
`/tmp/kinbase-tester-type-scale.log`.

Validator run a3181487 (tester 31b531f, candidate 1cf5320) reported 190/191.
Amendment 11c allows formality-driven text-transform changes on both label and
caption roles, including hero eyebrows. Isolation now permits those two roles;
title, subtitle and body text-transform changes remain rejected. Existing label
threshold checks and all other dimension-isolation/perceptual checks remain intact.

191 tests collect; compilation and whitespace checks pass. Local isolation-oracle
diagnostics accept label/caption transforms and reject title/subtitle/body
transforms. Non-browser execution remains blocked by absent vocabulary (109 setup
errors, 82 browser cases deselected); browser rerun awaits the Validator. Logs:
`/tmp/kinbase-tester-formality-collection.log`, `/tmp/kinbase-tester-formality.log`.

M4's first checkpoint adds `test_m4_export.py`: real CLI exports for both adapters
must preserve identical bytes across output locations and unchanged language
versions (including display-name/serialization changes). Header identities use an
independently computed language hash; JSON follows amendment 15. All fixture
assets are bound through slots, a font family, or a background-image; every one
must be packaged unchanged and referenced by exported CSS. The Tailwind adapter
must expose its declared theme/light scope and leave no token-value aliases
uncomputed. A real-browser generic consumer uses only exported CSS, independently
authored role classes/hooks, known token values and resolver agreement at base/md.
Its font must load from the export. No adapter variable-name convention is guessed.

194 tests collect; compilation and whitespace checks pass. Non-browser execution
remains blocked by absent vocabulary (111 setup errors, 83 browser cases
deselected). Logs: `/tmp/kinbase-tester-m4-export-collection.log` and
`/tmp/kinbase-tester-m4-export.log`. M4 is not complete: Tailwind browser consumption
needs a public compilation/stylesheet contract before that oracle can be written;
inventory, Apply and the Kinbase seam coverage remain to be authored.

M4 amendment 16 adds `test_m4_inventory.py` and real temporary Git repository
helpers. Complete role defaults treat a construct and its requested slots even
without an explicit component declaration. Independently seeded unknown construct
and slot requests each produce one missing finding. Equal-valued aliases in an
explicit state remain missing; changing the state to a different authored color
closes the gap. A justified scoped exception keeps its finding reported and
accepted, while an empty reason does not. A packaged but unbound real font is
missing until a font-family token binds it. Confirmed R2 violations block acceptance;
an unused part's advisory coverage alone does not. Finding pointers are resolved
against their reported repository-relative files and observed values.

202 cases collect; compilation and whitespace checks pass. A local diagnostic
initialized and committed the real Git fixture, verifying a clean main branch and
no remotes. Non-browser execution still stops at absent candidate vocabulary
(119 setup errors, 83 browser cases deselected). Logs:
`/tmp/kinbase-tester-m4-inventory-collection.log`, `/tmp/kinbase-tester-m4-inventory.log`.
M4 remains in progress. Explicit required-asset-variant inventory syntax is not
specified by the kind-string array; variant-specific coverage awaits clarification.

M4 amendment 17 makes the Tailwind export directly browser-consumable. The same
independent consumer now verifies both adapters without a compiler. Tailwind's
own build consumption of `@theme static` remains an explicit gap: verify it in
the target design-system repository during Apply.

`test_m4_apply.py` adds four real-browser Apply cases (both adapters, with/without
`--branch`). Two independently authored pages carry different persistent paint
markers and red card surfaces. The hand-off must retain each original screenshot
and show the exported green surface in each injected preview; OCR is not used.
TASK metadata, complete export bytes and inventory findings are checked. Disposable
Git repositories have local identities and a local bare remote: original files
and main remain unchanged, remote refs remain unchanged, and only the requested
local branch may be created. Committed export bytes are read from that branch,
without requiring Apply to leave it checked out. All processes have deadlines.

207 cases collect; compilation and whitespace checks pass. Non-browser execution
remains blocked by absent candidate vocabulary (119 setup errors, 88 browser
cases deselected). Logs: `/tmp/kinbase-tester-m4-apply-collection.log` and
`/tmp/kinbase-tester-m4-apply.log`. Browser assertions await the Validator; M4's
workbench and Kinbase seam coverage remain in progress.

M4's no-JS Apply case starts at `/apply`, selects a language/adapter, supplies a
real temporary target repository and local page URL, and follows visible forms or
links to the bundle. It checks the same independently authored screenshot effects,
export bytes, task metadata and findings as the CLI cases. It permits a fixed UI
target directory where no target-dir field is offered; CLI tests pin the explicit
argument. A project-local workbench launcher makes test TOML settings effective.

Two unavailable-Kinbase cases configure a nonexistent executable. Preview, both
exports, capture/draft and generate/derive must still succeed. Grid and viewer
must disclose unknown status with an unavailable reason. The no-JS feedback form
must append author, versioned target, exact comment and timestamp locally, report
"not sent (Kinbase unavailable)", and leave language bytes and validation unchanged.
The available-adapter seam remains pending a public initialization/fact contract;
stand-in executables will prove composition only, never real Kinbase behavior.
BFF inventory drafting remains out of scope pending the user's BFF decision (D3).

210 cases collect; compilation and whitespace checks pass. Local non-browser
execution still reports 119 prerequisite errors (missing candidate vocabulary),
with 91 browser cases deselected. Logs:
`/tmp/kinbase-tester-m4-workbench-collection.log`, `/tmp/kinbase-tester-m4-workbench.log`.
These browser assertions await the Validator; no local product pass is claimed.

M4 amendment 19 pins inventory assets as `kind` or `kind:variant`. Two new cases
verify a bare bound logo needs no on-dark variant, an explicit on-dark request is
missing until that bound asset supplies it, and a separate unbound logo cannot
satisfy it merely by being packaged. The existing primary binding stays unchanged:
the amended contract asks whether the bound asset has the variant. A mixed request
list independently checks exact missing members and prevents a same-named variant
of another asset kind from satisfying the request. Removing only the unsupplied
requirements restores acceptance. Asset-exception scope syntax remains unspecified
by the construct/slot/state scope grammar; that case awaits clarification.

212 cases collect; compilation and whitespace checks pass. The non-browser suite
still cannot execute product assertions without candidate vocabulary (121 setup
errors, 91 browser cases deselected). Logs:
`/tmp/kinbase-tester-m4-variants-collection.log`, `/tmp/kinbase-tester-m4-variants.log`.

M4 amendment 18 proposes a machine-applicable statement convention:
`{"kinbase-design":{"values":{"<working-copy JSON pointer>":"<value>"}}}`.
This convention awaits confirmation with the Kinbase owner (G2). It is not a
claim that arbitrary Kinbase prose can be executed as a design rule. Authoritative
free text must remain visible for manual application; lower standing remains a
suggestion. Positive fixed-input tests still need the public initialized-repository
fixture and exact source-provenance representation from the pending question.

`fixtures/kinbase/seam.py` supplies real stand-in `kinbase`/`kin` executables at the
explicitly authorized external seam. They append argv and return test-authored
JSON for the existing explain/questions/submit commands, rejecting other commands.
These prove adapter composition only, not real Kinbase behavior, authority
resolution, persistence or publication. Both unavailable cases put these executables
first on PATH so an erroneous submit cannot invoke the user's real Kinbase client.
The missing-binary journey and feedback checks now also run with a working stand-in
and a Git-only repository lacking Kinbase initialization. No submit may occur.
A test-driver-only process-environment field carries this PATH through CLI calls
and workbench startup; no product implementation is replaced or imported.

214 cases collect; compilation and whitespace checks pass. Stand-in diagnostics
launched the real executable, round-tripped a JSON design-fact response, verified
argv logging and unsupported-command rejection, and checked TOML/PATH setup.
Non-browser execution still stops at absent candidate vocabulary (121 setup errors,
93 browser cases deselected). Logs: `/tmp/kinbase-tester-m4-seam-collection.log` and
`/tmp/kinbase-tester-m4-seam.log`. Browser behavior remains unverified locally.

Validator repair 2b01fa1a reported 190/191 against the M3 checkpoint: a clearly
visible shape/formality pair changed 0.73% of the page, below the 1% floor. The
whole-page threshold now applies only when a pair varies hue-family,
value-contrast, saturation, type-pairing, type-scale or density. A pair containing
only shape/formality/whimsy still records its pixel share, but acceptance relies
on the existing per-dimension prominent-element paint and semantic-effect checks.
Mixed pairs with any broad paint/type/spacing dimension retain the 1% floor.
All per-dimension checks remain unchanged.

214 tests collect; compilation and whitespace checks pass. Non-browser execution
remains blocked by absent candidate vocabulary (121 prerequisite errors, 93 browser
cases deselected). Logs: `/tmp/kinbase-tester-perceptual-repair-collection.log` and
`/tmp/kinbase-tester-perceptual-repair.log`. The Validator must rerun the browser
case. M4's pending initialization/provenance and asset-exception questions remain
open; this checkpoint completes only the requested perceptual-test repair.

M4 amendment 21 closes the asset-exception scope gap. Two independent cases use
`overview/asset/logo:on-dark` and bare `overview/asset/logo` scopes with rule
`missing`. Exact variants cover only themselves; bare kinds cover bare and variant
requests on that page. Neither leaks across kinds or pages. All seeded missing
findings remain reported with their original file/pointer/rule/observed values,
and each covered finding identifies the exception by its inventory JSON pointer
(e.g. `/exceptions/0`). Acceptance remains false until all required gaps are
covered. A separate absent-font case verifies that a variant exception cannot
cover a bare-kind request and an empty justification cannot establish acceptance.

216 cases collect; compilation and whitespace checks pass. Non-browser execution
remains blocked by absent candidate vocabulary (123 prerequisite errors, 93 browser
cases deselected). Logs: `/tmp/kinbase-tester-m4-exceptions-collection.log` and
`/tmp/kinbase-tester-m4-exceptions.log`. Available-Kinbase seam coverage still awaits
the public initialization evidence and exact source-provenance representation.

M4 amendment 20 closes the availability/fixed-input fixture gap. The executable
seam now implements `kinbase fsck --repo ... --json`; exit status, not an invented
filesystem marker, decides initialization. The unavailable-repository cases
explicitly return fsck failure and verify its reason and command arguments.

`test_m4_kinbase_facts.py` uses two configured standard keys. Authoritative in-scope
hue=200 and density=10 facts must be settled before choices and excluded from every
offered pair. Controls cover lower standing, wrong scope, conflict, unknown,
authoritative free text and unrelated JSON. Real derive/check/save cases verify
rendered hue, Kinbase provenance on chromatic primary/attention token leaves and
base-hue colors, the same provenance in shared storage, and privacy. Pointer
facts target an existing public candidate token rather than guessing generated
token names; their exact value and RFC-6901-escaped source location survive repair
and save. A combined dimensions+values fact exercises both members. Suggestions
and manual standards produce no Kinbase source provenance. Every read command
uses the configured repo, logical key, decision string and JSON flag.

The convention remains a G2 proposal awaiting the Kinbase owner's confirmation.
These are executable-seam composition tests, not evidence that real Kinbase has
ratified, resolved or persisted any fixture fact. Direct diagnostics exercised
fsck success/failure, explain, all three submit types, receipts and argv recording.
The full working suite collects 231 cases; compilation/whitespace checks pass.
Local execution still stops at missing candidate vocabulary (130 prerequisite
errors, 101 browser cases deselected); the no-JS receipt tests are the next
checkpoint. Logs: `/tmp/kinbase-tester-m4-facts-collection.log` and
`/tmp/kinbase-tester-m4-facts.log`.

`test_m4_kinbase_workbench.py` completes the M4 no-JS seam coverage. Comment and
flag forms submit as concept/question, append local feedback, display the
stand-in's receipt, and leave the fixed hue, working language bytes and validation
report unchanged. The direction form submits a decision naming language@hash and
scope. A receipt leaves the direction unknown; only a later explain response makes
it current, and a conflict response is displayed as conflict. Workbench restarts
between externally changed facts avoid assuming an undocumented cache TTL.
Authoritative free text is shown verbatim for manual application, while lower
standing is presented as a suggestion and remains unsettled. Form selectors use
visible operations/native controls, not private routes or implementation classes.

M4 test authorship is complete against amendments 15–21. All browser operations,
server readiness/teardown and subprocess calls have finite bounds. 231 cases
collect; compilation and whitespace checks pass. Local non-browser execution is
still blocked at the candidate-vocabulary prerequisite (130 setup errors, 101
browser cases deselected). The Validator must execute the suite against the
integrated candidate; no local product pass is claimed. Final logs:
`/tmp/kinbase-tester-m4-complete-collection.log`, `/tmp/kinbase-tester-m4-complete.log`.
The explicit evidence gaps remain real Kinbase behavior behind the stand-ins and
Tailwind compiler integration in the target design-system repo; BFF inventory
inference remains out of scope pending D3.

Validator repair a4c13859 (candidate 3cad39c, M4 withheld) reported 190/191: a
text-free texture band legitimately changed paint with whimsy. Amendment 11d now
allows background-color/background-image/border-color changes on purely decorative
rows. The snapshot explicitly includes native links and ARIA widget/link roles,
and records content-slot ancestry and child content/controls. Text, slots,
controls, links and wrappers containing them cannot gain the exemption. Shape
radii already belong to shape; unrelated font, spacing and paint changes still fail.

The requested broader isolation audit also removes incidental constraints on the
same dimension: formality tracking may affect typography beyond the title while
the required title relation remains; labels/captions can demonstrate formality's
visible effect; cards and controls can demonstrate shape. Density/shape must still
produce an increasing specimen but need not uniformly increase every individual
space/radius. Primary lightness may change during value-contrast; otherwise it
stays fixed, as do unrelated hue/saturation coordinates. The explicit 11c ban on
transforming title/subtitle/body and the positive modular-scale, attention-hue,
contrast and visible-paint requirements remain intact.

A local diagnostic matrix accepts the three decorative paint properties and shape
radii, rejects the exemption for text/slots/native controls/links/ARIA widgets and
content wrappers, rejects unrelated font/padding changes, and checks label/caption
formality and card/control shape eligibility. Snapshot JavaScript syntax, Python
compilation and whitespace checks pass. All 231 tests collect. Non-browser
execution remains blocked by absent candidate vocabulary (130 prerequisite errors,
101 browser cases deselected). Logs:
`/tmp/kinbase-tester-decoration-11d-collection.log`, `/tmp/kinbase-tester-decoration-11d.log`.
A Validator browser rerun is required; no local product pass is claimed.

Amendment 11e corrects the earlier example: the recoloured element was an
error-state content root with a light attention wash, not a decorative band.
Whimsy isolation now recognizes attention-family paint on any element by circular
hue distance <=2 degrees on each side of the pair. Tints/washes may differ from
the attention foreground in lightness and saturation; exact RGB equality is no
longer required. Gradient checks permit unchanged neutral stops while requiring
each changed stop to follow its corresponding attention hue. The independent
11d decorative allowance and unrelated-property checks remain intact.

Local diagnostics cover content roots, slots, controls and links, pale washes,
359-to-1 degree wraparound, acceptance at 2 degrees and rejection beyond it,
unchanged neutral gradient stops, unrelated hue/angle rejection, and the prior
decorative/font/spacing controls. Compilation and whitespace checks pass; 231
tests collect. Non-browser execution remains blocked by absent candidate
vocabulary (130 prerequisite errors, 101 browser cases deselected). Logs:
`/tmp/kinbase-tester-attention-11e-collection.log`, `/tmp/kinbase-tester-attention-11e.log`.
Browser verification awaits the Validator.

Validator run 1462f53c (tester dbcbe13, candidate d7b76da) reported 227/231.
The feedback driver now accepts a labelled flag/question checkbox, clearing it
for the comment case and checking it for the question case. Labelled radio and
select choices are also accepted without requiring their form values to be the
literal kind names. A visible control can override a hidden default kind, and
semantic buttons remain supported. The external argv still must submit the
requested concept/question kind, retain the instruction-like feedback text, and
report the receipt while fixed inputs and validation remain unchanged.
The two omitted-language-findings inventory failures and the missing Apply bundle
are product-side per the review; those assertions remain unchanged.

231 tests collect; Python compilation and whitespace checks pass. Non-browser
execution remains blocked at absent candidate vocabulary (130 prerequisite errors,
101 browser cases deselected). Logs:
`/tmp/kinbase-tester-feedback-control-collection.log`, `/tmp/kinbase-tester-feedback-control.log`.
The repaired real-browser feedback case awaits the Validator's rerun.

The Validator's hands-on M4 gaps add two checks. Tailwind exports must declare
color and breakpoint variables inside `@theme static` with one namespace prefix,
rejecting names such as `--color-color-ink` and `--breakpoint-breakpoint-md`.
The parser isolates theme blocks, ignores quoted/commented braces and declarations,
and does not credit the separate browser-ready `:root` rules. This checks the
published naming requirement; actual Tailwind compiler integration remains a gap.

Both adapters now exercise Apply on a real Git repository with no inventory and
no page URLs. Success requires a complete hand-off/export and an accepted report
retaining an absent-inventory coverage advisory. Failure must name the inventory
file and provide an actionable explanation; an uncaught OS traceback fails.
Neither outcome may silently invent an inventory or modify the target repository.
The test accepts either documented handling policy rather than choosing one.

233 cases collect; compilation and whitespace checks pass. Local parser/message
diagnostics accept valid names and reject duplicate prefixes, missing theme
namespaces and declarations found only outside the theme. Non-browser execution
remains blocked by absent candidate vocabulary (132 prerequisite errors, 101
browser cases deselected). Logs: `/tmp/kinbase-tester-m4-final-gaps-collection.log`
and `/tmp/kinbase-tester-m4-final-gaps.log`. Integrated verification awaits the Validator.

Validator run b9e037cd (candidate 80e686a) reported 231/233. Amendment 22 resolves
the two remaining test-side pointer failures: mixed inventory reports explicitly
label each finding `source: inventory|language`. The report driver now requires
that discriminator, resolves inventory files from the site repository and language
files from the library root, confines the path to its selected root, and compares
the pointed value with `observed`. It no longer interprets language-relative paths
as repository-relative paths. Exception-preservation checks retain source identity;
seeded language R2/coverage findings must identify the language source. Apply's
absent-inventory advisory must identify the inventory source.

Local diagnostics used identically named JSON files containing different values
under the two roots, verified both pointers, and rejected a wrong root, absent or
unknown source, and a path escaping its source root. Python compilation and
whitespace checks pass; all 233 tests collect. Non-browser product execution
remains blocked by absent candidate vocabulary (132 prerequisite errors, 101
browser cases deselected). Logs: `/tmp/kinbase-tester-m4-source-collection.log`
and `/tmp/kinbase-tester-m4-source.log`. Integrated verification awaits the Validator.

## Content-page examples — 2026-11-08

Authority: task `design-examples-20261108`, public contract amendments 01 and 02
(Q-0001-db56bbe351a4). `test_content_pages.py` exercises the real render-page CLI
and output files using synthetic content created by `content_support.py`. The
fixture contains guide prose and optional collection cards, PNG pixels generated
locally and a hand-authored SVG; no real customer or third-party content is stored.

The first increment checks byte-identical HTML across Harbor/Lantern, semantic
landmarks/headings/lists/captions/links, literal hostile text, domain-word structure
invariance, image decoding and moved-bundle references, precise input findings,
path/symlink/URL refusals, and refusal to overwrite a non-bundle directory. Each
negative family has a valid source control. These catch lost content, broken
portable output, executable text, arbitrary file access and overwritten user work.
CSS reference parsing covers ordinary URL/import serialization; actual browser
loading, content visibility, contrast and non-color distinction remain pending.
Packaged font/license inclusion and offline syscall-level observation are also
not established by these file checks. No doubles, masks or mutation claims.

Local command: supplied runtime `python -m pytest tests/test_content_pages.py
--collect-only -q` collected 21 cases; compilation and `git diff --check` passed.
`python -m pytest tests/test_content_pages.py -x -q --tb=short` attempted the first
case, which failed because this lane has no `kinbase_design` module. That is a
prerequisite failure, not semantic red evidence. All product claims remain **gap**
until the Validator runs this test commit with an identified candidate commit.
No inherited tests were removed or changed in this increment.

Amendment 03 (Q-0006-94f04e2ae242) adds nine export cases through the declared
`figma.snapshot(..., api=...)` seam. Synthetic API JSON supplies conditions; the
real snapshot, exporter CLI and JSONL files supply observations. The publisher
oracle checks the exact fields, metadata lengths, id, refs, timezone and flattened
UTF-8 byte limit. Cases include metadata at/over 256 characters, a naive source
time, a long multibyte comment, a useful positive export and byte-idempotent
re-export. Every hazardous case first exports a valid control. There is no claim
about the real Figma wire protocol. Ref-count/id-format checks inspect every
written record but do not yet have an input capable of forcing each invalid form.
Command stdout/stderr are recorded for semantic omission-reason review; the suite
does not equate nonempty status output with a proven useful reason.

This increment also narrows the domain-word relation to tags, semantic hooks and
resource/link addresses. Generated accessibility labels may legitimately contain
the changed words; pinning all attributes would have overconstrained the contract.
No candidate result motivated this correction. Both modules collect 30 cases and
compile. Product evidence remains **gap** (implementation absent); no new product
run or sensitivity success is claimed.

Hook/mapping/grammar increment: `test_content_hooks_mapping.py` checks public hook
agreement with page/export contracts and validates nearest-construct slot ownership,
required slots and declared parts. Mapping cases test variant precedence, nested
collection fields, action arrays, wrapped/unwrapped source pointers, unmapped
sections/fields, literal hostile text, nonstring refusal and renderable output.
`test_content_properties.py` adds valid/invalid pairs from amendment 02, provenance,
resolvable findings, hidden-content refusal at four scopes and the eight forbidden
reordering/replacement properties. Existing Harbor/Lantern validation remains a
positive control. Compilation and collection succeeded (37 cases in these modules).
All runtime claims remain **gap** in this implementation-free lane.

Two inherited expectations are updated solely for amendment 02: the closed resolver
property set now includes the ratified additions; adapter header checking excludes
`hooks.json` because that artifact describes vocabulary, not language/version
metadata. Its exact contract/agreement is checked by the new hook test. No prior
behavior coverage is deleted. The shared content fixture now copies all shipped
languages so browser checks can enumerate the delivered library without asserting
a fixed language count or deriving expected design values from it.

Rendered acceptance increment adds `test_content_browser.py`,
`content_browser_support.py` and `test_content_layout_browser.py`. The Validator
must run these outside the lane sandbox. For every shipped language at collection
time, guide/card pages are checked at 375 and 1280 CSS px with JavaScript disabled:
actual image decode (including scrolling lazy images), visible unclipped text and
controls, source copy, local anchors, page overflow and browser network requests.
Harbor/Lantern must preserve HTML, accessibility order and links while differing
in horizontal construct geometry and typography. Hook selectors are exercised by
Chromium. A real loopback request proves the source observer is live before local
rendering and remote-src rejection are required to leave its request count alone.
This is bounded evidence for the supplied source, not a syscall audit of all egress.

Layout tests use independently authored consumer HTML plus real generic export
CSS. They measure grid columns/gaps at 767/768/769/1279/1280, row/column spans,
self-alignment, centering and aspect ratio, and inspect actual authored stripe
pixels for cover/contain/position and black shadow paint. A part override changes
columns at 768. The consumer is an export boundary test; it does not pretend to
prove arbitrary content-page wrapper choices. Solid-surface contrast composites
real ancestor backgrounds with WCAG math; image/gradient/group-opacity cases are
reported as **gap requiring pixel/manual assessment**, never accepted using a
made-up background. Pseudo-element overlays are not comprehensively modeled.

Additional CLI checks cover the remaining supported image formats, required
members, retained seeded truncation corpus, licence notices, and vocabulary markup
ownership despite a valid language variant. Synthetic SVG is parsed here and the
shared SVG logo is decoded in Chromium. The shared library fixture now includes
its shipped FONT-LICENSE.txt, preserving the actual export input. Browser
compilation/collection is successful; no Chromium execution or semantic mutation
result is claimed from this sandbox. New product checks remain **gap** until the
Validator supplies an integrated run. No inherited assertions were weakened here.

Amendment 04 repair, from the Validator's first integrated review: the shared
fixture combined a declared v1 language with the CLI's now-v2 default vocabulary,
causing R1 unknown construct/slot failures. This was a test setup defect under the
changed version-selection contract. The `vocabulary` fixture now requests the
version declared in the hand-authored language.json, and completion asserts that
the versions agree. Existing v1 slot/role/state pins remain intact and explicitly
name v1. A separate test requires default vocabulary/hooks to equal the newest
installed version, explicit v1 to remain available, and unknown versions to exit 2.
The existing content hook round trip now explicitly requires the content-capable
v2 contract.

`test_vocabulary_versions.py` adds the amendment's compatibility relation: the
same authored v1 language with only v1 installed versus with v1/v2 coexisting must
have equal validation findings, resolution, preview HTML/CSS, and rendered-check
outcomes/coverage/findings. The browser comparison masks only screenshot paths,
whose artifacts run_check separately decodes and checks. A valid v1 language is
also required to receive a vocabulary finding when asked for a content page.
These expose consumers accidentally following a global newest version instead of
the language's declared version; no captured product baseline supplies expectations.

Rechecked compilation, whitespace, collection (330 total cases), synthetic image
fixture decoding and contrast arithmetic; all passed. The representative command
`python -m pytest tests/test_vocabulary.py -x -q --tb=short` now visibly requests
`vocabulary --vocabulary v1`, then stops at this lane's absent kinbase_design module
(one setup error). No integrated pass or new semantic red is claimed. The Validator
has not yet supplied other content results or an exact candidate commit for the
first run. Repaired execution, including the new compatibility relation, remains
**gap** pending integration; prior reported cascading failures are retained above.

Amendment 05 corrects the Validator's earlier hook-value ambiguity. Hook contract
slot keys remain bare, while selectors and rendered attributes now must carry
`construct.slot`. The HTML round trip resolves that qualified construct against
actual ancestors (including an outer owner across nested constructs), rejects
undeclared or unqualified slots, and retains required-slot evidence per construct
instance. Allowed element declarations accept either a single tag or a nonempty
array; the browser selector check applies the same rule. The existing round trip
now includes captioned and uncaptioned media together. No other expectations moved.

Compilation, whitespace checks and all 330-case collection pass again. Bounded
helper-only diagnostics accepted qualified outer-owner slots and figure/img
alternatives, and rejected unqualified slots, absent owners, undeclared slots,
wrong tags and missing required slots. These establish helper behavior only; they
are not product sensitivity evidence. Integrated product/browser execution of this
repair remains **gap**, pending the Validator's next source-free report.

Amendment 06 adds honest acceptance status to every successful render-page helper
call: `validated` must be true, `rendered_check` must be accepted/rejected/unchecked,
and `accepted` must be exactly the rendered-accepted predicate for that statically
valid bundle. The helper still verifies the actual output files. No prior file or
semantic assertions are removed.

`test_content_acceptance.py` adds a fresh unchecked bundle plus static rejection,
and a real-check history test. The history uses Lantern's existing accepted narrow
baseline and an authored wide-only white-on-white slot, so passing at 320 and
rejecting at 1280 concern the same language version. It checks accepted after the
real passing report, unchecked after a version change, accepted on restoration
while that check is still latest, rejected after the same version's newer failing
check, and unchecked when the latest check is for a different version even though
an older report for the restored version exists. All check output directories are
outside the default location. The negative report must identify the seeded contrast
violation. No report files or timestamps are fabricated, patched or slept around.

Compilation, whitespace, 332-case collection and synthetic fixture/contrast
arithmetic diagnostics pass. `python -m pytest tests/test_content_acceptance.py
-m 'not browser' -q --tb=short` reports one failure at the absent kinbase_design
module, with the browser sequence deselected. Product acceptance-history evidence
therefore remains **gap**; the Validator must run the real Chromium sequence.
The prior hook-helper diagnostic evidence is unchanged and retained above.

Amendment 07 adds body-only sections. Two real render-page relations (with a hero
h1 and with a page-title h1) insert untitled sections before/between titled blocks.
Their bodies must appear once in the declared section construct with no heading;
the complete heading text/order/levels must match the original page, with exactly
one expected h1 and no skipped levels. The full-kind case also runs the hook round
trip so required-slot metadata cannot contradict the now-optional section title.
The existing invalid-content cases now reject explicit empty/null/number/list/
object/boolean section titles at their source pointer. Existing hero-title refusal
is retained, with CTA and collection-item required-title cases added alongside it.

The existing wrapped/unwrapped mapping fixture now includes a prose record without
its mapped heading field. It must become an untitled section, retain its paragraph,
render successfully, and avoid a missing-title finding. Unmapped-source expectations
are shifted only for the appended fixture record; all prior value and pointer
assertions remain in place. No candidate output supplied an expected value.

Compilation, whitespace and 342-case collection pass, as do repeated synthetic
image/contrast diagnostics and a direct fixture-shape diagnostic. The command
`python -m pytest tests/test_content_pages.py -k untitled -x -q --tb=short` stops in
the first baseline render because kinbase_design is absent here (one failure,
40 deselected). Untitled-section behavior remains **gap** pending integrated
execution; that prerequisite failure is not behavioral sensitivity evidence.

Validator review of integrated candidate `bde66a7` with Tester `d1e0fd9` reported
330 passed and 14 failed. These are retained as reported integrated results, not a
local rerun or results for later Tester commits. Most failures were classified as
product defects and sent to the Coder. The Tester correction concerns the M3
pair-isolation observation: CSSOM grid-template-columns returned used single-track
widths (1256.81px versus 1223.22px) that followed the permitted padding change.

`paint_snapshot` now reads grid-template-columns through computedStyleMap, alongside
its existing Typed OM width observation. The [CSS Typed OM computed-map contract](https://drafts.css-houdini.org/css-typed-om/#computed-stylepropertymapreadonly-objects)
exposes computed values rather than CSSOM's layout-dependent resolved values. The
property remains in the leak rule, so a genuinely changed grid treatment is still
forbidden outside its permitted dimensions. No blanket density exemption or
numeric tolerance was added. Browser extraction must still be rerun by the
Validator; it cannot be verified from the author sandbox.

The non-coercion mapping assertion now explicitly requires section content to be
an array and each entry to be an object before inspecting paragraphs. Both raw
numeric 17 and coerced string "17" in a paragraph are rejected with a specific
message. The previously reported malformed-content failure therefore remains a
product failure rather than an incidental Python TypeError.

Compilation, whitespace and all 342-case collection passed again. A bounded
oracle diagnostic accepts changing box width plus density padding with unchanged
computed grid treatment, and still rejects actual grid/color treatment changes.
This diagnostic verifies the assertion logic only, not browser extraction or
product sensitivity. The repaired integrated results remain **gap** pending rerun;
previous source-free failures and the reported 330 passes are preserved above.
