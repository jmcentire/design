# Independent M0 acceptance tests

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
