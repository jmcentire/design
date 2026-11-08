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
