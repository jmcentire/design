# Kinbase Design — Plan

Planning only. Nothing has been built, committed, deployed or messaged. SPEC.md is the contract;
this plan adds no requirements. Root reviews this plan independently.

## Approach

Build the core first: vocabulary, language schema, asset manifest, resolver and static renderer.
Put the visual workbench on it from the start, because the workbench is the product. Stress the
schema against real sites before building the authoring journeys. Connect Kinbase as the learning
and authority layer: feedback flows out as evidence, and current design standards flow in as
inputs.

Each milestone runs as a Factory task. The Validator writes separate Builder and Tester briefs.
The Tester derives its checks independently from SPEC.md. Bounds live in config.

New code lives in one new repository. Name and location are root's or dot's call; the working
name is `kinbase-design`. It is one local app (a workbench with server-rendered pages and JS
enhancement) plus a CLI over the same operations, for agents.

## Milestones

### M0 — Core, workbench shell, schema stress test
Build:
- Vocabulary v1, including the semantic contracts.
- Sample set v1 and its HTML generator.
- Language schema (R1–R5, variants, declared behaviors, asset bindings) and its error format.
- Asset manifest and packaging, and the resolver with hashing.
- A configurable library root, so the library can live in its own repo or in a subfolder of an
  existing GitHub project (U). No separate service.
- One hand-authored language, with a logo and a font asset.
- Static preview generator.
- **Workbench**: the library grid and the preview viewer (width switcher, state gallery).

Stress test (timeboxed spike, results recorded):
- Express three real pages in Vocabulary v1: a wandercom site page, a site-builder-test-sites
  fixture, and a page-sections preview.
- Run a throwaway ingest spike on them to find structure that needs variants, values that will
  not quantize, and the assets they need.
- Revise v1 from what the spike finds.

Exit: B1, B2, B3 and B16 pass with independent tests. The library browse/preview part of B15
works. The spike findings are recorded.

### M1 — Rendered checks, acceptance and the independent loop
Build the browser check harness:
- **Contrast** by an established method (EA: axe-core `color-contrast`), with imagery sent to
  `needs-review`.
- **Role conformance.**
- **Clipping, reflow and targets**, evaluated against declared behaviors and WCAG exceptions.
- **Asset loading.**
- **Keyboard, focus and no-JS static navigation.**
- **Supplemental OCR.**
- **Screenshots.**

Also build the findings types and the acceptance rule (SPEC §6.7). Then run one Builder/Tester
loop on a second language that uses a structural variant.

Exit: B4 and B9 pass. Acceptance fails on a seeded required `missing` finding and on a seeded
confirmed `violation`, and passes with a justified exception. The loop is triaged under the
round-3/4 rule.

### M2 — Ingest journey and artifact import
Build:
- Capture of public pages across a width sweep, with the capture review screen.
- Extraction and quantization.
- Mapping restricted to Vocabulary enums.
- Asset discovery and promotion.
- Import of images, mocks, wireframes, Figma exports and DTCG JSON.
- Provenance tracking, and the split between local workspace and library.
- Reconstructed-page fidelity review across the capture widths.
- Visual questions.

Exit: B5, B7 and B8 pass on site-builder-test-sites fixtures. A reconstructed-versus-captured
review is recorded for one real site. The ingest part of B15 works.

### M3 — Generate journey
Build: the visual interview, asset drop and promotion, the mood board page, A/B rounds over the
choice log with derived settled dimensions, and theory-based derivation with bounded repair
(reusing the color-engine if it fits).

Exit: B6 passes. One end-to-end workbench session on the user's beach-vacation brief ends in a
language the user picked through A/B. The generate part of B15 works.

### M4 — Apply, inventory, Kinbase direction
Build:
- Generic export with asset packaging, plus the first adapter (D2).
- Inventory schema with justified exceptions; the Apply screen showing site findings.
- Factory hand-off with before/after screenshots.
- The kinbase adapter, for the learning loop (SPEC §7.2), using existing commands only:
  - feedback and proposals as evidence via `kin kinbase submit`;
  - current design standards and direction read via `kinbase explain|project`, applied as fixed
    inputs (authoritative) or suggestions (lower standing);
  - authority questions via `kinbase questions`;
  - badges for direction and for conflicts with current standards.

  This is scoped by D1 and the answers to G1–G7.

Exit: B10–B14 and B17 pass, and the Apply part of B15 works. With Kinbase unavailable, standards
show as unknown.

Kinbase work that can start early, with no code and no external messages from this planning task:
at M0 kickoff, the user or root raises G1–G4 and G6 with the Kinbase owner and the Company steward:
- registering design authority scopes, with Lauren as the authority;
- the logical-key convention for design facts;
- resubmission identity;
- which repos are certified, including the one that holds the library subfolder;
- feedback identity.

Figma, Slack, Linear and Google Docs adapters are not present in the inspected kinbase@c9267ae
adapter list (G5). Whether any exists in a current deployment is part of the kickoff questions.
Any new Kinbase source adapter is Kinbase work, with its own access decisions, and is outside this
plan. Until one is confirmed, those sources enter through committed exports and workbench
feedback. M4 builds only what the answers support.

### M5 — Meaning layer (SPEC §12)
Mechanizes the M2 mapping step and makes the role clarification operational for mappings.

- **P1 Discovery over one corpus.** Built: CSS custom property, DTCG and prose sources; candidate
  mappings with provenance; the mapped-or-gap invariant. Not run on a real published system: the
  intended corpus is a public documentation site that this environment's network policy blocks.
  P1's hand review of mapping precision on a sample is therefore still open.
- **P2 A language from mappings.** Built: draft, apply and save through the ingest path, with the
  standing of each placed value on record. Foundations only; component treatments still come from
  the existing capture and fidelity review.
- **P3 Certification workflow.** Built: local choice, correction and supersession with author and
  history; certification read from Kinbase's scoped authority; proposals sent as evidence.
  Certification throughput is unmeasured, and depends on G1, G2 and G6.
- **P4 Exposure.** Built over the CLI and workbench: impact and definition answers with sources,
  uncertified mappings labelled. No MCP server.

Exit: B18–B21 pass.

## Factory briefs (per milestone)

- **Builder** receives: the milestone's SPEC sections, R1–R5, the pinned vocabulary and
  `lang@hash`, the asset bindings, and repository conventions.
- **Tester** receives: the B-criteria, the public schema, the workbench routes and CLI surface,
  and independently written expected design values. It does not receive the implementation or
  the builder's plan.
- **Evidence**: rendered behavior in a real browser, workbench journeys exercised end to end,
  and resolver cases with hand-written expected values. Doc regexes, class or literal pins,
  purposeless screenshots and tests of doubles do not count.
- **Validator** runs checks on the exact candidate commit, applies the acceptance rule, reports
  gaps, and escalates under the round-3/4 rule.

## Decisions needed

| Id | Needed by | Blocks |
|---|---|---|
| Repo name and location | M0 | start |
| D1 Kinbase learning loop; G1–G7 answers | M4 (ask at M0 kickoff) | feedback loop, standards as inputs, direction, authority questions |
| D2 First apply target | M4 | adapter |
| D3 Which BFF; inventory convention | M4 | inventory drafting |
| D4 Figma API adapter | none | optional |

## Risks

- **Ingest fidelity**: the M0 spike tests it early. Fidelity is judged on reconstructed pages
  across widths, then confirmed before and after Apply.
- **Structural variants as a back door for semantic drift**: guarded by R5. Content changes
  remain Vocabulary changes.
- **Kinbase is an unproven proof of concept with no design concept. Figma, Slack, Linear and
  Google Docs adapters are not present in the inspected kinbase@c9267ae adapter list.** That is
  unconfirmed for current deployments. All Kinbase use goes through one adapter, and core journeys
  degrade to "standards unknown". Learning starts from the sources Kinbase can observe today (Git,
  GitHub reviews, repo docs) plus workbench feedback.
- **Feedback could be mistaken for rules.** Only the scoped authority's approvals and answers
  create authoritative design facts (B17). Everything else stays evidence.
- **Workbench scope creep**: journeys are limited to the B15 set. "Few constraints, inspiration"
  favors defaults over options.

## Not in this plan

No hosted service, database, rights review, sign-off or ratification ceremonies, deploy gates,
drift monitoring, resolver chain, retention machinery, Figma plugin, Kinbase code changes, or new
Kinbase source adapters, subscriptions or credentials.
