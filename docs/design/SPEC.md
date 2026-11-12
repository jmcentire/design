# Kinbase Design — Specification

Status: planning draft, not ratified.

Review history:
- reviewed once each by Sim and Advocate, then by a bounded Constrain pass;
- then corrected twice by root review:
  1. structural variants, JS scope, WCAG exceptions, contrast method, ingest fidelity;
  2. visual workbench, concrete Kinbase integration, design assets, honest acceptance;
- then updated for Jeremy's clarification of Kinbase's learning and authority role, and of
  library storage.

None of these corrections went through Sim, Advocate or Constrain (REVIEW.md §7–9).
Jeremy's direction: "Excellent. Few constraints, inspiration."

Labels: **(U)** user direction from request.md or the root-relayed quotes; **(V)** verified code or
document at a cited revision; **(EA)** engineering assumption or proposal.

## 1. Intent

Kinbase Design (U: "Kinbase, sorry") is a **visual workbench and library** of reusable design
languages, built on Kinbase. Every language previews as a static, clickable, multi-page lorem-ipsum
site. People use the workbench; a CLI exists for automation and agents and is not the product.

Required capabilities (U):
1. **Browse and reuse** the library visually.
2. **Ingest** an existing website into a design language that preserves its appearance.
3. **Guided generate**: interview the user, collect their assets, build a mood board, offer A/B
   screen samples, converge, then derive the full system using design and UI/UX theory.
4. **Apply** a chosen language to a frontend or site.
5. **Start from partial artifacts**: URL, images, mocks, Figma exports, wireframes, assets or a
   brief. Derive the rest. Ask with rendered samples rather than dry questions. Keep track of what
   came from a source and what was inferred.

Ingest and generate are distinct (U). In ingest, the target is the authority for appearance. In
generate, artifacts are seeds and fixed constraints, and the user's choices drive convergence.

Reference model (U): CSS Zen Garden, read as **separation**. Meaning, structure and content are
owned apart from presentation. A language may declare structural layout variants that honor each
construct's semantic contract (§4.2). The fixed sample DOM is one demonstration of the principle,
not a mandate. Modern components, states and interactions extend fixed HTML (U).

Design posture (U): few constraints, and inspiration first. Rules exist where they protect meaning,
accessibility or honest validation. Everything else is a default the user can change.

**Kinbase's purpose here is the same as for software** (U, verbatim): "Monitoring docs and figma
and slack and linear and git to establish shifting standards and behaviors. To allow this system
to learn as it receives feedback from users (with authority ladder so Lauren's feedback matters
more than a CS team member's)."

The design system therefore **learns**:
- Kinbase observes design sources and feedback, and establishes the current design standards
  under scoped authority, with provenance.
- Kinbase Design reads those standards and applies them in its journeys.
- Workbench feedback flows back to Kinbase as evidence.

Within the design authority scope, Lauren Dorman's feedback outranks generic CS feedback. That
ordering comes from Kinbase's scoped-authority model, not from a ranking inside Kinbase Design
(§7).

## 2. Authorities

One owner per fact (ARCHITECTURE A1).

| Fact | Owner |
|---|---|
| Constructs, slots, roles, states, interaction contracts, context copy, sample sets | **Vocabulary** (versioned, in the library) |
| Presentation: tokens, roles, layout and variants, components, overrides, declared intentional behaviors, asset bindings | **Language version** (immutable, in the library) |
| Approved design assets (fonts, logos, images, icons) and their variants | **Language package** (content-addressed, in the library) |
| Private source originals (captures, uploads, mood boards, A/B choice log) | The user's **local workspace** (never shared) |
| Current design standards and direction learned from sources and feedback; which language is the direction for a scope; design questions for an authority | **Kinbase**: observations reduced into signed facts and owned Unknowns under scoped authority (§7) |
| Pages a site renders, the constructs/states/assets it requires, and site-specific justified exceptions | The **site's repo** (inventory file) |
| Content (actual records and values) | **Upstream data owners** (BFF/APIs) |
| Endpoint contracts and actions | **The BFF**. It owns no appearance and carries no design ids (U). |

## 3. Vocabulary (presentation-free)

- **Construct**: a universal UI concept. The seed list (EA) is page shell, nav, search bar, filter
  group, listing card, gallery, detail header, form, empty state, error state and footer. M0 checks
  it by expressing three real pages.
- **Slot**: a construct-local content position (`listing-card.price`) with a **text role** and a
  default **emphasis**. Media slots declare an asset kind, such as `nav.logo → logo`. (V:
  page-sections PropertyCard has only className overrides; content slots are new here.)
- **Text role** (hierarchy): title, subtitle, body, subtext, label, caption. Non-text roles: media,
  action, control.
- **Emphasis**: neutral, primary, attention, muted. The user's roles title/body/primary/subtext/
  attention map onto role × emphasis (U, InDesign analogy).
- **State**: default, hover, focus-visible, active, disabled, selected, expanded, loading, empty,
  error. Each construct declares which states apply.
- **Interaction contract**: what an action does (navigate, toggle filter, submit search, open
  gallery). It describes behavior, never look.
- **Semantic contract** (per construct): required slots, semantic elements and landmarks, heading
  level per role, native controls and their accessible names, reading and focus order.
- **Context** (U): universal copy and field types used in previews.
- **Sample set**: page compositions plus stress content (long word, long title, missing image, 0,
  1 and many items). Sample HTML is generated from the sample set, Context and lorem text.

## 4. Language

### 4.1 Parts
Each part references earlier parts, Vocabulary ids and the language's own assets.
1. **Style**: tokens in W3C DTCG format, with Kinbase Design data under `$extensions` (V:
   design-system tokens are DTCG built by Terrazzo). Covers color, type, space, radius,
   elevation, motion and breakpoints. A font-family token may bind to font assets.
2. **Roles**: maps role × emphasis to tokens. These are the horizontal defaults.
3. **Layout**: containers, grid, stack and page regions, plus **structural variants**.
   Variants are alternative markup templates for a construct, for example a card with media on
   top, to the left, or as an overlay.
4. **Components**: per-construct treatment, meaning the chosen variant, slot arrangement,
   visuals per state, and **asset bindings** (for example `nav.logo → logo:primary`, with a
   variant per surface).
5. **Overrides**: records of the form `{scope: construct[.slot][.state][@breakpoint],
   properties → token refs, reason}`. They cover intentional exceptions (U). Deleting one restores
   inheritance (A52). At most one override per exact scope; specificity runs construct < slot <
   state < breakpoint.
6. **Declared intentional behaviors**: deliberate behavior that a generic check would otherwise
   flag. Examples: `truncate: line-clamp 2` with the full text available elsewhere, a compact
   inline control under a WCAG exception, a horizontally scrolling carousel.

Resolution order: most specific override, then component treatment, then role default, then
token. Values are computed, never copied.

### 4.2 Composition rules (executable validation)
- **R1**: every reference resolves, whether to a token, role, construct or asset id.
- **R2**: raw values appear only in Style, and each parses as its token type.
- **R3**: every role × emphasis a component uses declares a foreground/surface pairing. Ratios
  are measured on rendered output only (§8).
- **R4**: layout uses only declared breakpoints and space tokens.
- **R5**: structure respects the semantic contract. Arrangement that CSS can reach over the
  default DOM needs no declaration. A declared variant must keep every required slot exactly once
  with its role, the declared semantic elements and landmarks, native controls with their
  accessible names, and the declared reading and focus order. Changing content is a Vocabulary
  change.

Failures name the rule, file, JSON pointer, observed value and expected constraint. A language's
scales, palette and assets are the closed set its components and overrides may use (U).

### 4.3 Versions and packages
- **Version.** A language version pins a vocabulary version. Its identity is the SHA-256 of the
  RFC 8785 canonical JSON of the presentation facts plus the asset manifest, which lists assets by
  content hash. Provenance sits beside the version, outside the hash. A working copy is mutable; a
  version is minted on export or proposal.
- **Package.** A **language package** is the unit of reuse: the version document, its asset
  files (stored by content hash) and the asset manifest. Consumers reference
  `lang@hash`. Assets are referenced as `lang@hash#asset-id[:variant]`.

## 5. Sources, assets and provenance

### 5.1 Private source originals
Every input becomes an immutable, timestamped **source artifact** in the user's local workspace:
URL capture (DOM, computed styles, screenshots across widths), image, mock, wireframe, Figma
export, uploaded asset original, brief, or interview answer. Originals are never shared. Later
comparisons use captures, not live URLs.

Every language value has provenance:
- `source`: an artifact plus a location inside it;
- `inferred`: the method and its inputs;
- `chosen`: a visual choice id.

The provenance stored in the shared library holds only kind, opaque artifact id, location and
method. If an original is erased, its pointer reads "source removed".

### 5.2 Approved design assets (minimal manifest)
Assets a design needs across consumers are **promoted** by the user from originals or uploads
into the language package. Promotion is a deliberate act in the workbench, not a rights gate.
Rights are the user's responsibility (U).

Each manifest entry:
```json
{ "id": "logo", "kind": "logo|font|image|icon",
  "variants": { "primary": {"file": "sha256/…", "format": "svg"},
                "on-dark": {"file": "sha256/…", "format": "svg"} },
  "meta": { "font": {"family": "…", "weight": 700, "style": "normal"} } }
```
- **Bindings** connect assets to the design: font-family tokens bind to font assets, and media
  slots bind to `asset-id:variant`, with variants per surface or per breakpoint where needed.
- **Packaging**: export copies the bound files into the target, applies the target's referencing
  convention (CSS `@font-face` and `url()`, or adapter paths), and records `lang@hash#asset-id`
  in the generated header.
- **Asset gaps** are `missing` findings. Examples:
  - a binding names an absent asset or variant;
  - a role uses a font weight or style that no font asset supplies;
  - a site's inventory requires an asset kind that the language lacks.

Variants are needed only when usability requires them. If the existing logo renders legibly on a
dark surface, no separate on-dark file is required. The rendered check (§8) judges usability, not
whether a file with a given name exists.

Supplied assets are used unchanged.

### 5.3 Figma (U: no connector assumed)
- **Import** by manual export. Frames become mocks. Variables and styles exported as
  DTCG-compatible JSON become `source` tokens. Exported images and fonts become originals the user
  can promote.
- **Handoff**: DTCG JSON, the asset files and rendered sample frames.
- **API adapter**: optional future work, not claimed available.

## 6. Workbench journeys and capabilities

The product is a **local visual workbench**: one local app serving server-rendered pages, with
JavaScript as enhancement (Factory frontend practice; Kinbase founder ruling 329fe2cc44b4:
agent-friendly first, JS for effect and help).
- The same operations are exposed through a CLI for Factory agents and automation.
- The CLI is internal or optional, not the user experience.

### 6.1 Library (browse, preview, compare, reuse)
- **Browse**: a grid of language cards, each with thumbnail, provenance summary, findings summary,
  and Kinbase badges. The badges show scopes where the language is the current direction, and
  conflicts with current design standards.
- **Feedback**: comment on or flag any preview, page or construct. Feedback is recorded with its
  author and target and sent to Kinbase as evidence (§7.2).
- **Preview**: open a language's static preview site in the viewer, with a width switcher, a
  state gallery, and a toggle to show role, emphasis and asset annotations on hover.
- **Compare**: two languages side by side on one sample set.
- **Fork**: an independent authority, with the fork point recorded.
- **Assets**: a panel showing the asset manifest, variants and gaps.

### 6.2 Ingest journey (target is the authority)
1. **Enter** URLs or drop artifacts. Capture runs on public pages across a width sweep, plus
   breakpoints taken from media queries. v1 presents no credentials. For a private site, the user
   drops screenshots or exports.
2. **Capture review**: thumbnails per width, with any capture problems shown.
3. **Extraction and quantization** (tolerances in config).
   - Construct and role mapping restricts LLM output to Vocabulary ids and token references.
   - Page text is treated as data, never as instructions.
4. **Draft language** opens with the extracted palette, type scale, spacing and found assets
   (logo and fonts offered for promotion).
5. **Fidelity review**: representative captured pages are reconstructed from Vocabulary
   constructs and variants, filled with captured content kept in the local workspace. They are
   rendered with the draft language at the capture widths and shown side by side with the
   captures, alongside the measured facts (color ΔE2000, font family, type scale ratio, spacing
   base). Divergences become coverage findings or visual questions.
6. **Visual questions** fill gaps (§6.4). Divergences from current Kinbase design standards are
   also asked visually.
7. **Save** to the library. Optionally, propose it as direction in Kinbase. The proposal becomes
   current only through the scoped authority (§7.2).

Before/after comparison on the target's own pages at Apply is the final confirmation. Test bed
(V): wandercom/site-builder-test-sites.

### 6.3 Generate journey (user choices drive)
1. **Visual interview**: palette strips, type specimens, density and shape examples, and
   formality and mood sliders with live sample swatches. Covers colors, styles, themes, feelings,
   formality and audience. Example brief (U): a casual site for young families; a relaxing but
   engaging beach vacation; blues, greens and turquoise; whimsical flair.
2. **Assets and partial artifacts**: the user drops logos, fonts, palettes, images, mocks and
   wireframes. Their values enter as `source` and stay fixed. Assets are promoted into the
   package. Authoritative Kinbase design facts in scope are also fixed inputs. Lower-standing
   facts appear as suggestions (§7.2).
3. **Mood board** page: assets, candidate palettes, type pairings, and shape and texture cues. The
   user can pin or remove items.
4. **A/B rounds**: two candidates on the same sample screen, differing on one or two unsettled
   dimensions.
   - The stored fact is the choice: `(pair, A hash, B hash, A|B|neither, comment)`.
   - Settled dimensions are derived and can be revised.
   - "Neither" widens the variation.
   - The user can stop at any time; the round cap is in config.
   - This is Bayesian-filter-like in spirit; literal Bayesian computation is not required (U).
5. **Derive** the full system from the assets, settled preferences and theory: color harmony and
   contrast, modular type scale, spacing rhythm, hierarchy, affordance and Gestalt.
   - Validate against R1–R5, with bounded repair.
   - EA: reuse the design-system color-engine (V: `resolveTokens`; the page-sections
     ThemeCustomizer previews themes from seeds).
6. **Review** the derived preview site, then save. Optionally, propose it as direction (§7.2).

### 6.4 Visual questions
For a missing or ambiguous value, render 2–4 candidates on the relevant construct and state, and
ask the user to pick. The pick is recorded as `chosen`. Machine checks prove conformance, not
taste.

### 6.5 Static preview
- **Pages**: generated home, search results, listing detail, form and state gallery pages.
- **Without JavaScript**: the static pages render, basic navigation works, and every declared
  state is depicted. Live interactions may require JavaScript.
- **Interactive states**: hover, focus and active are reachable with pointer and keyboard.
- **Zen Garden demonstration**: languages that use only default variants produce byte-identical
  HTML on a pinned sample set. Languages with declared variants keep identical content and
  semantic contract.

### 6.6 Apply journey
1. Choose a target site/repo and an adapter.
2. See the findings for that site: its inventory against the language, including asset gaps.
3. Export.
   - Export is a pure function of (language version, adapter version).
   - It produces generic CSS custom properties, role and emphasis classes, and packaged assets,
     plus target adapters.
   - Verified target shapes (V):
     - **design-system**: DTCG → Terrazzo → Tailwind v4 `@theme static` with
       `[data-theme='light'|'dark']`;
     - **page-sections**: `PageSectionTheme` plus permissive `--wos-*` variables.
   - Generated files carry a plain header naming `lang@hash` and `adapter@version`.
4. Hand off a Factory task that produces a branch or PR, with before/after screenshots of the
   site's own pages. Kinbase Design never merges or deploys.

### 6.7 Site inventory, findings and acceptance
- The site's repo owns its **inventory**. For each page or BFF endpoint the site renders, it
  lists the constructs, states and asset kinds used, the endpoint reference, the observed
  contract version, and any **justified exceptions**. An exception is a finding scope plus a
  reason.
- Endpoint-to-construct mapping is a frontend design decision. Kinbase Design can draft it from a
  BFF contract.
- Current BFF state (V): wandercom/bff-site has three authed routes; PR #3 is open and blocked.
  wandercom/sites-harness is described as the Sites BFF.

Findings, typed:
- `missing`: a construct, slot, state or asset that the inventory or language requires is
  untreated or absent.
- `violation`: a validation rule failed (R1–R5), or a rendered check failed and the failure is
  confirmed.
- `needs-review`: a rendered check could not decide (for example, text over imagery).
- `coverage`: something was not observed in a source artifact.

**Acceptance is honest validation, not deployment bureaucracy.** A language, or a Factory
candidate applying it to a site, **fails acceptance** while any of these remain:
- a required `missing` finding;
- a confirmed `violation`.

Two kinds of exception are allowed:
- a declared intentional behavior in the language;
- a justified exception in the site inventory.

Every exception is reported. `coverage` findings are advisory. `needs-review` findings go to a
human or LLM reviewer, and are never counted as a pass. There are no sign-off ceremonies, no
approval records and no deploy gates. The Factory Validator applies these results when judging
acceptance.

## 7. Kinbase: learning design standards under scoped authority

Jeremy confirmed the identity and the purpose (U, §1). Below, the existing Kinbase capabilities are
separated from the adapters and configuration this use would need. All are verified against
wandercom/kinbase@c9267ae: `spec/architecture.md` §4 and §6, `spec/glossary.md`, `spec/cli.md`,
and the Kindex reader guide. Kinbase is a proof of concept: its acceptance suite passes (371 nodes),
but the outcome experiment has not run and the concept is unproven. It has no design concept yet.

### 7.1 What Kinbase already does (V)
- **Source adapters** implement `probe`, `scan` and `reconcile`, with stable native ids,
  revision binding and idempotence. The initial kinds:
  - `git_history`: commits, diffs, reverts;
  - `github_export`: `gh` JSON for issues, PRs, reviews and merged/closed state;
  - `docs_adr`: Markdown, RST and text in repositories, with ADR status;
  - `repo_code`;
  - `repo_tests`;
  - `codex_jsonl` and `claude_jsonl` (coding transcripts);
  - `runtime_evidence`;
  - `kindex`;
  - `authority_answer`.
- **Origin trust class** on repository evidence: `merged-default`, `approved-pr`,
  `unreviewed-branch`, `uncommitted-worktree`. Anything below `merged-default` is ineligible for
  trusted durable direction unless an authorized event cites it.
- **Extraction and admission**: observations become candidate atoms (claim, constraint,
  decision, observation, Unknown). Only an approval by the scoped authority or maintainer
  (`kinbase proposals decide … --approve-digest`) or a signed authority answer admits them as
  facts. "No accept-all command exists."
- **Scoped authority**: the AuthorityRegistry maps an exact question scope to a named person, a
  key and a channel. Facts tokens list exact `authority_scope` strings, with no wildcards. "None
  inherits another's authority by role prestige."
- **Standing caps by provenance** (Kindex view of Kinbase facts): human provenance can reach
  authoritative; transcript and human_review reach at most prevalent; agent provenance reaches at
  most present. Submissions through `kin kinbase submit` always carry agent provenance.
- **Reducer** (per logical key):
  - applies authority and scope eligibility, explicit retraction and parent-bound supersession;
  - collapses duplicates and separates corroboration from common-source repetition;
  - uses recency only within an authority-equivalent set;
  - surfaces conflict and produces an owned Unknown when the current fact is ambiguous.
- **Reads**: `kinbase explain`, `kinbase project` and session hooks put the current facts and
  Unknowns into coding sessions. `kinbase questions ask|answer` route a question to its scoped
  authority.

### 7.2 How the design system learns (EA: proposal using 7.1)
1. **Design sources Kinbase can observe today.** The library is stored in a Git repository: its
   own repo, or a subfolder of an existing GitHub project (§9). That makes language versions,
   asset changes and design docs observable through `git_history`, `docs_adr` and `github_export`.
   PR reviews and comments by Lauren, a CS team member or anyone else arrive with reviewer
   identity, and merged changes carry `merged-default` trust.
2. **Workbench feedback as evidence.** A comment on a preview or a flag on a component is
   recorded with its author and the target `lang@hash` and construct.
   - It goes to Kinbase through existing intake (`kin kinbase submit --type
     concept|question`).
   - Intake carries agent provenance, so the result is an observation or a candidate. It can
     never become a mandatory rule by itself.
3. **Authority ladder.** Ordering comes from Kinbase's scoped authority, not from Kinbase Design.
   - Lauren Dorman would be registered as the authority for design question scopes, by the
     Company steward and on configuration. Her signed answers and digest approvals within that
     scope admit authoritative design facts.
   - A CS team member's feedback stays observation-level evidence. It can corroborate, raise an
     owned Unknown, or prompt a question to Lauren, but it cannot set design direction.
   - Lauren's authority covers design scopes only. It is not universal across domains.
4. **No automatic promotion.**
   - Unreviewed feedback, recurring complaints and A/B tendencies remain evidence.
   - They become standards only through the scoped authority's approval or answer.
   - When evidence conflicts or is insufficient, Kinbase's reducer yields an owned Unknown, which
     reaches Lauren through `kinbase questions ask`.
5. **Kinbase Design applies the current standards.** The workbench reads the current design facts
   for the relevant scope (`kinbase explain`/`project`) and uses them by standing:
   - **Authoritative design facts** in scope are fixed inputs, like supplied assets, with
     `source: kinbase:<fact>` provenance. Examples: "brand X keeps palette P", "listing cards
     never truncate price".
   - **Lower-standing facts** are shown as suggestions and seeds, in keeping with the
     few-constraints, inspiration posture.
   - **Generate** respects fixed inputs and uses suggestions as priors for A/B candidates.
   - **Ingest** flags divergences from current standards as visual questions.
   - **Library** badges show which languages conflict with the current standards, so a new
     version can be made. Language versions stay immutable.
6. **Direction for a scope** ("use `lang@hash` for site S") is one more design fact.
   - It is proposed from the workbench as a `decision` candidate.
   - It becomes current only through the scoped authority.
   - The Factory Validator pins whatever `explain` reports as current, or the `lang@hash` the
     task names explicitly. Conflicts and Unknowns are surfaced to the user, never guessed.
7. **Coding sessions** in Kinbase-certified repos receive the current design facts through
   Kinbase's existing hooks and projection. Builders see Lauren's standards without extra wiring.
   Executable checks stay in Kinbase Design's validator, because a fact informs and does not
   enforce (U).

Preview, ingest, generate and export keep working with Kinbase unavailable. Standards then show as
*unknown (Kinbase unreachable)*, and nothing is invented.

### 7.3 Required adapters, configuration and gaps (not assumed to exist)
- **G1 Design authority scopes.** Design question scopes need to be registered with Lauren as the
  named authority (person, key, channel). This is registry configuration; no design scope is
  verified to exist.
- **G2 Logical keys.** The convention for design facts (per brand, site, construct or rule) that
  lets `explain` find "the current standard for X" is not defined.
- **G3 Resubmission identity.** Supersession and retraction are reducer behavior (V). Whether
  identical resubmitted text counts as a new event is unverified.
- **G4 Certification.** Which wandercom repos are Kinbase-initialized and certified is unknown.
  Without certification, no hooks, projection or observation of the library's repo happen.
- **G5 Source adapters not found.** **Figma, Slack, Linear and Google Docs adapters are not
  present in the inspected kinbase@c9267ae source adapter list** (`spec/architecture.md` §4;
  `docs_adr` covers repository text files only). This does not prove that no such adapter exists
  in a current deployment or another branch: confirm with the Kinbase owner. If none exists, each
  would be a new adapter under the §4 contract, with its own access permissions and credentials,
  which are not assumed. Until one is confirmed, plan for those sources to reach Kinbase only
  through exports committed to a repo (for example, Figma
  exports into the library folder) or through feedback recorded in the workbench.
- **G6 Workbench feedback identity.** `kin kinbase submit` always records agent provenance. To
  carry the human author's standing directly, feedback would need a Kinbase source adapter or an
  authority path that preserves principal identity. Until then, authority flows only through
  Lauren's approvals and answers, or through her GitHub reviews.
- **G7 Proof-of-concept acceptability.** Whether Jeremy accepts an unproven Kinbase in this
  production design loop.

## 8. Independent design testing loop

Factory roles apply (V: SOFTWARE-FACTORY.md). The Validator gives each role its own brief:
- **Builder**: the task; the pinned `lang@hash` (normally the current Kinbase direction); the
  applicable authoritative design facts, with their Kinbase fact ids; rules R1–R5; the constructs
  to build; and the asset bindings.
- **Tester** (independent): the expected design values, the expected behaviors, the declared
  intentional behaviors, justified exceptions and the rules. The Tester gets no builder code. It
  renders from the language package at the exact candidate commit.

Rendered checks run in a real browser at configured widths.
- **Contrast**: an established rendered/computed method (EA: axe-core `color-contrast` or
  equivalent).
  - The computed foreground is checked against the alpha-composed effective background, and
    gradients against the stops under the text.
  - Thresholds: WCAG 2.2, 4.5:1 for text and 3:1 for large text; WCAG 1.4.11, 3:1 for non-text UI.
  - Text over imagery, or over backgrounds the method cannot resolve, is `needs-review`.
- **Role conformance**: computed styles equal resolved values. The resolver has its own
  hand-written expected cases.
- **Clipping and truncation**: text must not be clipped unintentionally. A declared intentional
  truncation passes when the full content remains available.
- **Reflow and targets**: no two-dimensional scrolling at 320 CSS px (WCAG 1.4.10), except
  exempt or declared content. Targets meet 24×24 CSS px (WCAG 2.5.8) unless an exception
  applies: spacing, equivalent, inline, user-agent control, or essential. The applied exception
  is reported.
- **Assets**: bound fonts load and are used; no binding resolves to a missing file. Logos and
  images render visibly and legibly on every surface where they appear: non-text contrast
  (WCAG 1.4.11) where it applies, otherwise `needs-review` with a screenshot. Usability is
  judged, not the presence of a variant.
- **Interaction**: keyboard reachability, visible focus and state styles. Static pages and basic
  navigation work without JavaScript.
- **Legibility/OCR**: supplemental signal only (U).
- **Screenshots**: per page and per width, for fitness review. Never pixel-pinned.

The Tester checks conformance, not taste. The following are not evidence: regex over docs,
arbitrary class or literal pins, purposeless screenshots, tests of doubles (U). No
design-grammar checker exists in wandercom (V). agent-skills#118 is an open draft (V).

**Loop discipline** (U): drop unproductive objections immediately; reassess at round 3; escalate
by round 4.

## 9. Architecture and layout

Helland/DDD/Hickey: bounded contexts as modules, one local deployable (the workbench app plus its
CLI), no hosted service, no database.

**Modules**:
- vocabulary;
- language (schema, validation, resolver);
- assets (manifest, bindings, packaging);
- render;
- artifacts (capture and import);
- generate;
- export (adapters);
- inventory and findings;
- kinbase: one adapter over existing commands. It sends feedback and proposals through
  `kin kinbase submit`, reads standards through `kinbase explain|project` and `kin kinbase sync`,
  and routes authority questions through `kinbase questions`;
- meaning: candidate mappings from source tokens to Vocabulary enums, local review, Kinbase
  certification, the contract check, and impact/definition answers (§12);
- workbench (web UI);
- cli.

External boundaries sit behind adapters: the browser, the LLM, Figma exports, target repos, BFF
contracts and Kinbase. Bounds live in config (A55).

**Storage (U: "Asset and element library can be a subfolder in a GitHub project").** The shared
library root is a configurable path in any Git repository. It can be its own repository, or a
subfolder of an existing GitHub project, such as `design/` next to the site code. A subfolder
needs no separate repository or service. It also puts the library where Kinbase's existing
`git_history`, `docs_adr` and `github_export` adapters can observe it, once that repo is certified
(G4). Pushing and PRs follow the user's normal Git permissions; Kinbase Design claims no remote
publishing rights.

```
shared library root (own repo or a subfolder of a GitHub project)
  vocabulary/<version>/
  languages/<id>/working.json
  languages/<id>/versions/<hash>.json      version + asset manifest
  languages/<id>/assets/sha256/<hash>      approved design assets
  languages/<id>/provenance/<hash>.json    opaque pointers only
  generated/                               derived CSS, sample HTML, preview screenshots
local workspace (private)
  artifacts/<artifact-id>/                 capture and upload originals, mood boards
  sessions/<id>/choices.jsonl
  meaning/<corpus>/corpus.json             tokens, candidate mappings, gaps, usage evidence
  meaning/<corpus>/decisions.jsonl         append-only local choices
  meaning/<corpus>/certified.json          the latest Kinbase certification snapshot
```

## 10. Behavioral acceptance

- **B1**: languages that use default variants produce byte-identical sample HTML. A declared
  variant keeps text, slots, roles, accessible names and landmarks. A contract-breaking variant
  is rejected (R5).
- **B2**: an unresolved reference or ill-typed token is rejected, naming the rule, pointer and
  value.
- **B3**: deleting an override restores the role default in rendered output.
- **B4**:
  - A text/background pair below threshold is a `violation` with the measured ratio.
  - Imagery or an unresolved background is `needs-review`, never a pass.
  - Clipping, reflow and target results honor declared behaviors and WCAG exceptions, and name
    the criterion or exception applied.
- **B5**: ingesting a fixture site yields:
  - a language within tolerances on measured facts;
  - reconstructed pages rendered at the capture widths beside the captures, with divergences
    recorded;
  - coverage findings.
- **B6**: a guided session uses supplied assets unchanged. Every choice is retained locally.
  Superseding a choice changes the derived settled dimensions.
- **B7**: missing values are asked as rendered candidates, and picks are recorded as `chosen`.
- **B8**: every value has provenance. Shared provenance has no URLs or paths.
- **B9**: without JavaScript, static preview pages render, navigate, and depict every declared
  state.
- **B10**: export is byte-identical for identical inputs. Computed styles from the exported CSS
  equal resolver values. Bound asset files are packaged and referenced.
- **B11**: given a site inventory, `missing` findings list exactly the untreated
  constructs/states and absent assets or variants. Acceptance fails while a required `missing`
  finding or a confirmed `violation` remains without a declared behavior or justified exception.
  `coverage` findings do not fail acceptance.
- **B12**: Apply hands off a branch/PR with before/after screenshots. It never merges or deploys.
- **B13**: preview, ingest, generate and export work with Kinbase unavailable, showing standards
  and direction as unknown.
- **B14**: "propose as direction" submits a `decision` candidate naming `lang@hash` and reports
  the receipt as received. The direction badge reflects what `kinbase explain` reports for the
  scope, including conflict or Unknown. A proposal is never shown as current until Kinbase
  reports it current.
- **B17**: workbench feedback reaches Kinbase as evidence, with its author and target. Feedback
  from someone who is not the design scope's authority never changes a fixed input or a
  validation outcome by itself. An authoritative design fact in scope, as `explain` reports it,
  is applied as a fixed input with Kinbase provenance. A lower-standing fact is offered only as a
  suggestion.
- **B15**: through the workbench alone, a user can complete four journeys without the CLI:
  - browse and compare the library;
  - run ingest to a reviewed draft;
  - run generate through the mood board and A/B to a derived language;
  - open the Apply hand-off.
- **B16**: promoting an asset copies it into the package by content hash. The private original
  stays in the local workspace. A binding to an absent asset appears as a `missing` finding. A
  logo or image that is not legible on a surface where it appears is a `violation` or
  `needs-review`. A variant is required only when usability requires one.

- **B18**: discovery over a token source leaves every token either mapped or recorded as a gap
  with a reason. Every mapping uses only Vocabulary ids and closed-set properties. Nothing is
  certified by discovery, by a document's text, or by a local choice.
- **B19**: only an authoritative, trusted, in-scope current Kinbase fact certifies a mapping. A
  lower-standing, out-of-scope, conflicting or ungrounded fact certifies nothing. With Kinbase
  unavailable, certification is unknown and nothing is sent.
- **B20**: a corrected mapping changes resolved output after re-apply, leaves no trace of the
  withdrawn mapping, and its provenance (candidate, each decision, any certifying fact) is
  retrievable. Shared provenance carries the token path and standing, and no reviewer name, note,
  URL or path.
- **B21**: the meaning check reports a broken certified contract as a `violation` naming the fact
  and scope, and a broken uncertified mapping as advisory `coverage`. Impact and definition answers
  name the file and JSON pointer behind each part, and label every uncertified mapping.

## 11. Open decisions and deferred assumptions

- **D1**: the Kinbase learning loop in §7.2, and the gaps G1–G7. Above all:
  - registering design authority scopes, with Lauren as the authority;
  - logical keys;
  - which design sources get new Kinbase adapters (Figma, Slack, Linear, Google Docs) and with
    what access;
  - whether workbench feedback should carry human identity;
  - acceptance of the proof-of-concept status.
- **D2**: first apply target: design-system tokens or page-sections theme.
- **D3**: which BFF is meant (bff-site or sites-harness), and whether site owners accept the
  inventory file convention.
- **D4**: whether a Figma API adapter is wanted.

Deferred future contracts (nothing is built yet): the `$extensions` key, the inventory schema,
the asset manifest schema details, the export header format, the adapter variable mapping (cite
page-sections html-section-authoring.ts lines 14–56 when built), and the text and logical-key
conventions for Kinbase direction facts.

## 12. Meaning layer (EA)

Sections 3 to 8 enforce the structure of a language. They do not hold the meaning of the foreign
artifacts ingest reads: which source token is a surface and which an emphasis, and what moves when
a value changes. That meaning was reconstructed by hand at every ingest. The meaning layer keeps
it, with the same discipline as the rest of the system: one owner per fact, provenance on every
value, and authority from Kinbase.

The pattern is the certified context layer used for enterprise metadata (discover, ground,
validate, expose, learn), applied to design. Only the shape is borrowed.

1. **Discover.** From immutable private artifacts (CSS custom properties, DTCG JSON, prose), draft
   a candidate mapping for every token, with the artifact and location it came from. Heuristics
   are deterministic and labelled heuristic. Prose that names a token is usage evidence with a
   location. Text is data, never an instruction, and never a rule.
2. **Ground.** A mapping is `{property, emphasis?, role?, state?}` over the closed property set
   and the Vocabulary enums. The ontology proposes; the Vocabulary disposes. A name that asks for
   meaning the Vocabulary lacks is a recorded gap, and widening the Vocabulary is a Vocabulary
   version decision, never a side effect of an import.
3. **Validate.** The meaning check compares a language's token references with the mappings. Only
   a certified contract can fail it. Everything of lower standing is advisory (§6.7).
4. **Expose.** Impact and definition questions are answered over the CLI and the workbench, with
   the file and JSON pointer behind each part. The resolver computes which treatments move.
5. **Learn.** Standing is ordered `certified > chosen > candidate`. A reviewer's local choice is
   recorded with its author and supersedes earlier choices; it stays a choice. Certification is
   read from Kinbase under §7.2: an authoritative, trusted, in-scope current fact, by the scoped
   authority. Local choices can be proposed as a `decision` candidate; a receipt is not
   certification. Kinbase Design ranks no one.

A language drafted from a corpus goes through the ingest path (§6.2) and is saved like any other
draft. Its role values record the mapping and standing that placed them, and a certified one
carries `source: kinbase:<fact>`. Nothing blocks saving a language built from uncertified
mappings: the standing is on record, and the check reports it.

Boundaries:
- Behaviour does not import. Interaction logic belongs to shared templates and Vocabulary
  interaction contracts, not to a language.
- A language holds one context. A source with light and dark values yields one language per
  context; the unexpressed context is a coverage finding.
- The mapping convention inside Kinbase statements (`mappings`, keyed by corpus and token path) is
  proposed and awaits the Kinbase owner, with the rest of G2.
- No run over a real published design system is recorded yet, and no MCP server exists.

