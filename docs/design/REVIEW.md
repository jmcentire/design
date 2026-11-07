# Kinbase Design — Review record

Validator: Claude (claude-opus-5-5) in Claude Code. Date: 2026-11-07. Scope: planning only.
No product code, commits, pushes, PRs, deploys or external messages.
Sim and Advocate output is simulated advice, not user consent. The user directions are in
request.md, including its three 2026-11-07 sections: generate/ingest clarification, input modes,
and the naming correction "Kinbase, sorry". Chat messages relayed by dot's coordinating worker
were treated as orchestration guidance, not as user words.

## 1. Passes and receipts

| Pass | Input | Result | Evidence |
|---|---|---|---|
| Sim, attempt 1 | drafts/SPEC.v0.md | **FAILED before any model call**: Homebrew `python3` lacks `openai` ("Missing dependency: No module named 'openai'"), exit 1. | evidence/sim-v0.attempt1-* |
| Sim, attempt 2 | same input, `python3.14 ~/.claude/skills/simulacrum/run.py` (no installs) | exit 0. `phase=SPECIALIST agent=v9.1 model=claude-opus-5 stop_reason=end_turn complete=True` | evidence/sim-v0.out.txt, .err.txt |
| Advocate | `advocate review drafts/SPEC.v0.md --provider anthropic` (default model claude-opus-5, advocate 0.1.5) | exit 0. review_id 20261107T171314-7808131b. 7 personas ok (red_team, adversarial, sage, user, sme, good_friend, helland). 84 findings, 0 disagreements, $1.38 | evidence/advocate-v0.json, .digest.txt |
| Source verification | read-only subagent; gh + shallow temp clones of remote heads | 9 claims: 5 verified, 3 partly (with corrections), 1 not found | evidence/source-verification.md |
| Constrain, attempt 1 | `constrain --backend anthropic --model claude-opus-5-5 --max-tokens 16000 new -p drafts/constrain-prime.md` | **ABANDONED, contaminated**. Default `CONSTRAIN_KINDEX=on` loaded 43 items of Constrain's own project context, so the interview became about Constrain's defects. The prime yielded 3 items. Stopped after the first question; no answers given. | evidence/constrain-attempt1-kindex-contaminated/ |
| Constrain, attempt 2 | same command, `CONSTRAIN_KINDEX=off` (toggle verified at constrain/src/constrain/kindex_integration.py:39) | exit 0. Session c3499781, phase complete. 4 understand and 4 challenge exchanges (the session JSON records hidden posture = adversarial). Prime: 92 items. **Synthesis partial**: missing `--- CONSTRAINTS ---` delimiter; `constraints.yaml` written **empty (0 bytes)**; trust_policy, component_map and schema_hints **not written**. `prompt.md` (230 lines) and `boundary_register.yaml` written. The register has 17 UNVERIFIED errors and still lists two entries that `prompt.md` says were retracted (`kb-resolve-cmd`, `applied-manifest-file`). Exit 0 despite the empty file. | constrain/out.log, answers.log, prompt.md, boundary_register.yaml, refs/ |

Orchestration notes:
- My FIFO driver first sent `n ` (with a trailing space) to Constrain's Kindex onboarding prompt,
  which blocked it. dot's coordinating worker wrote an exact `n\n` to clear it. I fixed the driver.
- The worker also fixed my wait helper's prompt regex. It stopped only that stuck helper, not
  Constrain.
- Constrain was driven turn by turn. Each answer came from request.md user direction, verified
  code (copies with provenance in constrain/refs/SOURCES.md), or labelled engineering
  assumptions. No user consent was fabricated.
- **Backend choice, explicit:** Anthropic API, model claude-opus-5-5, max-tokens 16000. The key
  was resolved by Constrain's config; values were never printed.
- Constrain was not re-run after the partial synthesis. On the coordinator's instruction the pass
  is bounded and not ratified. Useful output came from the challenge exchanges and `prompt.md`;
  the YAML artifacts are not used as authority.

## 2. Triage: accepted

Grouped by change made. The source of each finding is in brackets: S = Sim; A = Advocate persona
and index (e.g. A-red0); C = Constrain.

- **Vocabulary and Language are two authorities, not one stack.** Interface removed from the
  language layers; the old R6 deleted (it is now unrepresentable); layer renamed "Roles".
  [S, A-sag0, A-sme3, A-use3, A-adv5]
- **CSS-reachable arrangement only (R5).** This was the condition for byte-identical HTML.
  *Superseded by root review (§7): R5 is now the semantic-contract rule, which allows declared
  structural variants.* [S, A-adv0, A-sme0, A-goo8]
- **Sample HTML is generated** from a versioned sample set + Context, so copy has one authority.
  Stress content added. [S, A-hel6, A-adv12]
- **Contrast is measured on rendered output only.** An inconclusive result is never a pass. R3
  now only requires declared pairings. *The glyph-pixel minimum algorithm was superseded by root
  review (§7): an established rendered/computed method replaces it, with imagery sent to review.*
  [S, A-adv1, A-sme2, A-red11, A-use4]
- **Findings are typed** (`missing` / `violation` / `coverage`), computed, and never gate.
  Capture coverage is separated from gaps. *Superseded by final correction 4 (§8): a required
  `missing` finding or a confirmed `violation` fails acceptance.* [S, A-use5]
- **A language version pins a vocabulary version.** Hash = RFC 8785 canonical JSON of presentation
  facts only; provenance is held beside the document. [S, A-adv8, A-sag2, A-hel4, A-red4]
- **The site's repo owns its inventory.** Endpoint→construct is a frontend decision; the BFF
  carries no design ids. [S, A-hel0, A-hel1]
- **The CSS-variable importer is dropped (old A9).** Replaced by deterministic export plus
  computed-style fidelity (B10). [S, A-adv2, A-sme6, A-use7]
- **Role conformance is distinct from resolver correctness.** The resolver gets hand-written
  expected cases. [S]
- **Store the A/B choice, not an attribution.** Settled dimensions are derived and revisable;
  "neither" widens variation; round cap in config. [S, A-adv10, A-sme8, A-use6, A-goo9, A-hel5]
- **Ingest before generate** (M2/M3), plus a timeboxed ingest spike in M0. [S, A-goo1, A-sag7]
- **Ingest promise made honest.** Quantization is an explicit step. *Fidelity is extended by root
  review (§7) to a rendered review of reconstructed versus captured pages across relevant widths.
  This is the "second rendering path" Sim flagged as missing.* [S, A-sme1, A-sme4, A-adv6,
  A-sag4]
- **Strict token typing (R2)**, for CSS-injection safety. LLM output is restricted to Vocabulary
  ids and validated; page text is data. [A-red0, A-red7]
- **Overrides are records** with one per scope and a total specificity order. [A-red8]
- **States are depicted vs. interactive**, a split of the old A7 (now B9). *Narrowed by root review
  (§7): the no-JS requirement covers only static previews and basic navigation.* [A-adv7]
- **Tester renders from the language document** at the exact commit. It verifies conformance, not
  fitness. [A-red6, A-adv11]
- **Worked surface:** provisional CLI listed, error format specified, DTCG `$extensions` named.
  [A-use1, A-use11, A-sme5]
- **Export:** an anti-corruption adapter per target; Apply = branch/PR, never merge or deploy.
  [A-goo4, A-hel2 (simplified)]
- **Local workspace vs. shared library.** Captures, uploads and choice logs never enter the shared
  Git library. Shared provenance holds opaque ids only. v1 ingest is public pages with no
  credentials. [C challenge 2]
- **Kinbase integration is one operation** that reports the receipt as-is, including unknown
  outcomes. The Validator pins an explicit `lang@hash` in briefs. *Superseded by final correction
  2 (§8): a concrete Kinbase role in the core journeys, built from verified capabilities, with
  gaps G1–G6.* [C challenges 1–3, after retraction]
- **Bounds in config** (A55), with no separate cost subsystem. [A-goo2, A-goo3 (reduced)]

## 3. Triage: rejected or reduced (with reason)

- **Cut OCR** [S, A-sme10]: rejected. The user explicitly asked for OCR as a signal. It is kept as
  a non-gating signal, with a deterministic paint/clip check added beside it.
- **Rights handling, private-by-default, legal machinery** [A-goo5]: rejected. The user made rights
  their own responsibility and asked for no rights gating.
- **Human promotion gate for drafts** [A-goo7]: rejected as an approval gate the user disallowed.
  The honest statement is kept instead: machine checks prove conformance; taste comes from the
  user's A/B choices.
- **Drop overrides from the MVP** [A-sag3]: rejected. The user explicitly requires explicit
  component overrides.
- **Move the testing loop out of the spec** [A-sag5]: reduced. The user asked for it in scope; it
  is kept concise.
- **Defer BFF mapping entirely** [A-sag8]: reduced. The user wants the durable inventory. It is
  owned by the site repo, and drafting it from contracts is optional.
- **Hosted library auth, publisher signatures** [A-red10]: rejected. There is no hosted service;
  Git with a remote is the shared library.
- **SSRF egress policy, asset magic-byte sniffing, id regex, atomic-write protocol, URL scrubbing,
  concurrency locks, spend ceiling** [A-red2, A-red3, A-red5, A-red9, A-red13]: reduced. Each is a
  speculative control for a local single-user CLI. They are replaced by "public pages only, no
  credentials" and "content stays in the local workspace".
- **Gap waivers** [A-hel7]: rejected at first. *Reversed in a minimal form by final correction 4
  (§8): a justified exception (finding scope plus reason) lives in the site inventory, and every
  exception is reported.*
- **Literal Bayesian or soft-distribution machinery** [A-sme8 option b]: rejected. The user said
  literal Bayesian computation is not required.
- **Cut the "Bayesian-like" sentence** [S]: rejected. It records the user's framing and the
  user's explicit limit on it.
- **RTL/CJK fixtures now** [A-adv12]: deferred. Stress content covers length and emptiness;
  script direction is not in the user's request.
- **Constrain challenge additions** (`kb resolve` fallback chain, publish read-back, "superseding
  X" text clause, `kinbase-design.applied.json` manifest and drift findings, never-delete
  retention, library-writer enforcement): **retracted by me in challenge round 3.** I had accepted
  them in rounds 1–2. The coordinator's triage was right: they are operational machinery outside
  the user's "fewest bindings" direction. Their underlying questions (supersession, concurrency,
  scope naming) are Kinbase's own governance and are listed as deferred.
- **Constrain register equality evidence for future interfaces**: not pursued. Kinbase Design-side
  literals do not exist yet and are recorded as future contracts (SPEC §11).

## 4. Source verification summary

Detail and line citations: evidence/source-verification.md. Revisions checked: design-system
373cb5e, page-sections 9d1447d, factory ccf8bfc, kinbase c9267ae, bff-site 6a79a1f, agent-skills
2c585ac. The local clones were stale and were not modified.

- **Lauren Dorman** is the design-system CODEOWNER (`* @laurendorman`). Verified.
- **Tokens:** DTCG via Terrazzo; Tailwind v4 `@theme static` with `[data-theme]`. Verified.
- **color-engine** `resolveTokens` contrast fallbacks: verified (keep seed if ≥3:1; below 2:1 use
  black/white; otherwise search OKLCh lightness). Text floors are 7 / 5.5 / 4.5 / 3.5 / 3.
- **page-sections:**
  - Zod schemas per section and preview SectionModules: verified.
  - **Correction:** README's `registry.ts` does not exist; hosts dispatch with an explicit switch.
  - **Correction:** PropertyCard "slots" are className overrides, not content slots.
  - `--wos-*` (33 variables) and `wos-*` primitives are permissive: verified.
- **bff-site:** three authed routes on dev. PR #3 is open and blocked (curated-list resolve and
  search, loose schema). **Ambiguity:** wandercom/sites-harness is described as the "Sites BFF".
- **agent-skills#118 (Atlas):** open draft, advisory only, unpublished rules, signoffs open. Not
  shipped.
- **wandercom/factory:** the builder renders and drives UI changes. **No design-grammar or token
  conformance checker exists.**
- **"Kenbase":** zero hits anywhere. Kinbase is a Rust PoC ("concept remains unproven") with no
  design concept. The user then confirmed Kinbase.
- **Reusable assets:** site-builder-test-sites (ingest fixtures), page-sections ThemeCustomizer,
  color-engine, wandershot, webprobe, pregen-preview.

Other local sources read:
- ~/Code/factory/docs/SOFTWARE-FACTORY.md
- ROLE-DOCTRINE.md
- practices/frontend-architecture.md (Zen Garden, progressive enhancement, container scoping,
  judicious globals)
- standards/ARCHITECTURE.md (A1, A9, A10, A23, A24, A30, A41, A52, A55)
- ~/Code/kindex-personal/docs/kinbase.md
- wandercom/kinbase@c9267ae README.md, spec/cli.md, spec/architecture.md, spec/glossary.md and
  spec/product.md (constrain/refs/kinbase-*.md)
- `kin kinbase submit|sync --help` (captured in constrain/refs/)
- the simulacrum SKILL.md
- advocate and constrain READMEs and source

## 5. Steps: exact status

- **Succeeded:**
  - read request.md, including three later sections;
  - Kindex `tag_start` and searches;
  - discovery;
  - doc reads;
  - source verification;
  - SPEC v0 written;
  - Sim (attempt 2);
  - Advocate;
  - triage and SPEC v1;
  - Constrain attempt 2 interview, with partial synthesis;
  - SPEC.md, PLAN.md, REVIEW.md written.
- **Failed:**
  - Sim attempt 1 (interpreter missing a module);
  - Constrain attempt 1 (context contamination; abandoned);
  - Constrain synthesis of constraints.yaml (empty) and three other artifacts (not written).
- **Not run:**
  - a second Sim/Advocate pass on SPEC v1 or the final SPEC;
  - a Constrain re-run to obtain the YAML artifacts;
  - `constrain validate` (it would fail on the 17 UNVERIFIED future-contract entries by design);
  - any Kinbase submission (planning only).

## 6. Unresolved

- **D1–D4** and the repo location (SPEC §11, PLAN).
- **Deferred Kinbase governance assumptions** (SPEC §11).
- **The final SPEC has not had its own adversarial pass.** Its main changes since v1 are:
  - the Kinbase rename;
  - local workspace vs. shared library;
  - retraction of the Constrain-era machinery;
  - the root-review corrections in §7;
  - the final corrections in §8 (workbench, concrete Kinbase role, assets, honest acceptance).
- **Kinbase gaps G1–G7** (SPEC §7.3), as refined in §9.

## 7. Root review corrections (applied after all passes; not re-reviewed)

The root review asked for five corrections before delivery. All five were applied to SPEC and
PLAN. No further Constrain, Sim or Advocate runs were made. The Constrain partial result (§1) is
unchanged. Its `prompt.md` still states the earlier CSS-only R5, pixel contrast and universal
no-JS wording, so on those points it is superseded by SPEC.md.

1. **Zen Garden means separation, not one mandatory DOM.**
   - R5 is now a semantic-contract rule: required slots exactly once with their roles, declared
     semantic elements and landmarks, native controls with accessible names, and DOM order
     matching reading and focus order.
   - Languages may declare structural layout variants in the Layout layer.
   - Byte-identical HTML is kept as one demonstration, for languages using default variants
     (SPEC §1, §4.1, §4.2, §6.5, B1).
   - This reverses my earlier acceptance of Sim's and Advocate's "CSS-reachable only" constraint.
     The root review is right that the user asked for separation and for modern components that
     extend fixed HTML, not for CSS-only restyling.
2. **No-JS scope.** Only static previews and basic navigation must work without JavaScript. Live
   interactions may require it (SPEC §6.5, §8, B9).
3. **WCAG exceptions and declared intent.**
   - Clipping and truncation pass when declared intentional with the full content available.
   - Reflow follows WCAG 1.4.10, with its exceptions and declared horizontal scroll.
   - Target size follows WCAG 2.5.8 and its five exceptions.
   - Results report which criterion or exception applied (SPEC §8, B4).
4. **Contrast method.** The glyph-pixel minimum I adopted from Advocate (A-red11, A-adv1) is
   replaced by an established rendered/computed check (EA: axe-core `color-contrast` or
   equivalent):
   - computed foreground against the alpha-composed effective background;
   - gradients checked against the stops under the text;
   - imagery and unresolved backgrounds sent to *needs review*, never passed;
   - OCR supplemental only (SPEC §8, B4).
5. **Ingest fidelity.**
   - Representative captured pages are reconstructed from Vocabulary constructs (with variants)
     using captured content kept in the local workspace.
   - Each reconstruction is rendered with the derived language at the capture widths.
   - It is reviewed side by side with the captures, beside the measured facts.
   - Apply before/after remains the final confirmation (SPEC §6.2, B5; PLAN M2).

Residual risk from these changes: structural variants could be used for semantic or content drift.
The guard is R5 validation. Variant authoring adds work at M0, and the M0 spike tests that cost.

## 8. Final root and independent review corrections (FINAL-CORRECTIONS.md; not re-reviewed)

Jeremy's latest (as relayed): "Excellent. Few constraints, inspiration." All four corrections
were applied by rewriting SPEC.md and PLAN.md. The §7 corrections stay in force. There were no
further Sim, Advocate or Constrain runs, and the Constrain partial-result record (§1) is unchanged.

1. **The product is a visual workbench, not a CLI.**
   - SPEC §1, §6 and B15 now specify a local web workbench (server-rendered, with JS as
     enhancement) with four journeys: Library (browse, preview, compare, assets, direction
     badges), Ingest (capture review, draft, fidelity review, visual questions), Generate (visual
     interview, assets, mood board, A/B, derive, review) and Apply (findings, export, Factory
     hand-off).
   - The CLI exposes the same operations for agents and is internal or optional.
   - My earlier "one CLI + static output" framing confused the minimal deployable with the
     product.
2. **"Use Kinbase" with a concrete role.** I inspected the Kinbase CLI contract
   (wandercom/kinbase@c9267ae `spec/cli.md`, copied to constrain/refs/kinbase-spec-cli.md),
   alongside the README and the Kindex reader guide.
   - **Verified capabilities used**: signed facts and the reducer (`explain`); named authorities;
     owned Unknowns (`questions ask|answer`); sessions, projection and hooks; digest-approved
     proposals; and intake via `kin kinbase submit` with types concept, decision, constraint and
     question.
   - **Proposed role** (SPEC §7.2): Kinbase is the authority for design direction and design
     governance, at the core decision points:
     - Save/Propose and "set as direction" submit decision facts;
     - the direction badge and the Validator's pin come from `explain`;
     - authority-level design questions are Kinbase Unknowns;
     - a few durable design rules are constraint facts that reach coding sessions through hooks
       and projection.
   - The library keeps documents and assets, which 16 KiB text atoms cannot hold.
   - **Gaps G1–G6 are labelled, not invented**: design authority scope, logical-key mapping,
     supersession and identity, which repos are certified, native ingest source (it would need
     Kinbase code), and proof-of-concept acceptability.
   - This replaces my earlier single optional publish, which bypassed Kinbase in every core
     journey.
   - Raising authority-level design questions as Kinbase Unknowns does not conflict with the
     no-approval-gates direction. They use Kinbase's existing ownership mechanism, and visual
     picks by the current user stay in the workbench.
3. **Minimal asset manifest.**
   - The language package now holds approved design assets (logo, font, image, icon) by content
     hash, with variants and metadata.
   - Bindings connect font-family tokens and media slots to `asset-id:variant`. Export packages
     the files and references them.
   - Private capture and upload originals stay in the local workspace, and promotion is a
     deliberate user act, not a rights gate.
   - Asset gaps (a missing asset or variant, an unsupplied font weight, a logo without an on-dark
     variant, a kind required by the inventory) are `missing` findings.
   - See SPEC §4.3, §5.2 and B16.
4. **Honest acceptance.**
   - "Findings never gate" is replaced. A required `missing` finding or a confirmed `violation`
     fails acceptance, unless it is covered by a declared intentional behavior (in the language)
     or a justified exception (in the site inventory). Every exception is reported.
   - `coverage` findings are advisory. `needs-review` findings go to review and never count as a
     pass.
   - There are no sign-offs, approval records or deploy gates; the Factory Validator applies the
     rule. See SPEC §6.7 and B11.

Residual risk: the Kinbase role depends on G1–G4 answers that are not yet available. If Kinbase
has no suitable design authority scope or logical-key convention, §7.2 narrows to decision
submission plus session context. The core journeys still work. *The Kinbase role in correction 2
is refined by §9.*

## 9. Kinbase role and storage clarification (KINBASE-ROLE-CLARIFICATION.md; not re-reviewed)

**Provenance.** The file records Jeremy's words as relayed by root:
- "Kinbase would serve the same purpose as it does for software. Monitoring docs and figma and
  slack and linear and git to establish shifting standards and behaviors. To allow this system to
  learn as it receives feedback from users (with authority ladder so Lauren's feedback matters
  more than a CS team member's)."
- "Asset and element library can be a subfolder in a GitHub project."

The constraints in that file come from root: no invented permissions or connectors, no universal
authority, no automatic promotion of feedback, the on-dark logo caution, and no new review passes.

**Sources verified for this change** (copies with provenance in constrain/refs/SOURCES.md):
- wandercom/kinbase@c9267ae `spec/architecture.md`:
  - §4, source adapter contract, initial adapter kinds, origin trust classes;
  - §6, reduction algorithm;
  - §7, authority-seeking loop: heading only; the section was not read in detail.
- `spec/glossary.md`: AuthorityRegistry, scoped authority ("None inherits another's authority by
  role prestige"), logical key.
- `spec/cli.md`: proposals with digest approval, questions, explain, project, hooks.
- Kindex reader guide: standing caps by provenance; `kin kinbase submit` always carries agent
  provenance.

**Changes.**
- SPEC §1 states the learning purpose.
- SPEC §7 is rewritten as three parts:
  - 7.1, what Kinbase does today;
  - 7.2, the proposed learning loop:
    - the library in Git, observed by existing adapters;
    - workbench feedback as evidence;
    - the authority ladder via scoped authority, with Lauren registered for design scopes only;
    - no automatic promotion;
    - authoritative facts as fixed inputs and lower-standing facts as suggestions;
    - direction as a `decision` candidate that becomes current only through the authority;
  - 7.3, gaps G1–G7, including **Figma, Slack, Linear and Google Docs adapters are not present in
    the inspected kinbase@c9267ae source adapter list (G5)**. That is not proof of absence in
    current deployments or other branches; confirm with the Kinbase owner. Also
    feedback identity (G6).
- SPEC §6 journeys gain feedback and standards badges.
- SPEC §8: the Builder brief carries the applicable authoritative facts.
- SPEC §9 adds a configurable library root (own repo or a subfolder of a GitHub project; no
  service; no claimed remote rights).
- SPEC §10: B13, B14 and B16 revised; B17 added.
- PLAN: the M0 storage option; the M4 learning-loop adapter; Kinbase questions raised at kickoff
  by the user or root (not by this task); new Kinbase adapters out of scope.

**On-dark logo caution applied.** An asset variant is required only when usability requires one.
The rendered check judges legibility on each surface (non-text contrast or `needs-review`), not
file presence (SPEC §5.2, §8, B16). This narrows my earlier "logo without on-dark variant" gap
example from §8.

**Not changed.** The fewer-constraints/inspiration posture, the §7 and §8 corrections, and the M0
scope beyond the storage option (which root reports as otherwise approved). Nothing invented:
monitoring permissions, connectors, ingestion implementations, cross-domain authority and
automatic promotion are all explicitly absent or listed as gaps.
