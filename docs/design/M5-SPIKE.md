# M5 meaning-layer spike: Palermo

2026-11-12. One bounded run of meaning discovery over a real published design system, to test
SPEC §12 against a source nobody here authored. The fetched files, the corpus, both drafts and the
check reports stayed in a private scratch workspace. No Palermo language, value table or asset is
in this repository; the names and values quoted below are observations.

No mapping was certified and no reviewer made a choice. Kinbase is not configured here. The
precision notes are one read by the builder, not Jeremy's hand review, which P1 still needs.

## Source

| What | Where | Read as |
| --- | --- | --- |
| Colour documentation | `palermo.tryprofound.com/docs/colors` | printed Light and Dark values per token |
| Shipped stylesheet | the docs site's main compiled stylesheet (one file, 277 kB) | CSS custom properties, the corpus |

The proposal's premise is that Palermo's component code is not published; this run read only the
docs site. That site turned out to publish two sets of values that disagree (below). Component
pages were not captured, and no component treatment was reconstructed.

## What discovery produced

1,309 custom property declarations in the file. 727 sit outside a root or theme scope (utility
classes and components setting a property for themselves) and were not read as tokens. 141 are a
theme layer re-exporting a property under its own name. The remaining 441 define **283 tokens**
across three contexts: `base`, `light`, `dark`.

| Token type | Candidates | Gaps |
| --- | --- | --- |
| colour | 32 | 90 |
| dimension | 56 | 11 |
| font weight | 23 | 0 |
| font family | 3 | 0 |
| number | 0 | 15 |
| untyped (shadows, easings, animations) | 0 | 53 |
| **total** | **114** | **169** |

Every token is mapped or a recorded gap: 111 `vocabulary`, 34 `unsupported-value`, 24 `unmapped`.

## Vocabulary pressure

89 of the 122 colour tokens ask for meaning Vocabulary v1 does not have.

| Pressure | Colour tokens |
| --- | --- |
| Hue-named (nine hue ramps, plus `text-red`, `bg-green`, `fill-blue` and the like) | 64 |
| Workflow and node colours | 13 |
| Shadow and ring colours (elevation) | 8 |
| Inverse pairing (`text-inverse`, `fill-inverse`) | 2 |
| Data visualisation, overlay | 2 |

The proposal expected the workflow colours. The larger pressure is hue: half the palette names an
appearance, and four emphases cannot hold nine hues. Some of it is ordinary meaning under a hue
name (`text-red` is very likely the attention colour), which a reviewer can map with one choice.
The ramps themselves are a Vocabulary version question. The spike widened nothing.

The inverse pair matters more than its count. The primary control fill has no expressible text
colour without it, and that is one of the rendered-check failures below.

## Precision of the colour candidates

Builder's read of all 32, against Palermo's own names and documentation:

- **Property**: 31 of 32 right. `brand-icon-ring` was read as a text colour. It carries an
  `unread-words` doubt and is never placed.
- **Emphasis**: sound for `text-primary`, `bg-base`, `bg-primary` and `control-primary`. The ranked
  scales (`secondary` to `quinary` across text, background and fill, 11 tokens) all land on
  `muted`, which is a guess. Every one is flagged `ordinal-scale` and `collision`.
- **State**: `hover` and `selected` read correctly on five control and fill tokens.
- 12 candidates carry a qualifier the heuristic did not read (`sidebar`, `tooltip`, `header`,
  `sunburst`, `gray`). None of them is placed.

Without review, four colour tokens were placed: `text-primary`, `bg-base`, `control-bg` and
`control-primary`. The three-way tie for muted text was left for a reviewer, as were six title
sizes and nine body sizes.

## The documentation disagrees with the stylesheet

The colours page prints a Light and a Dark value for 50 tokens, all of which exist in the
stylesheet the same site ships. Compared value by value:

- 72 of the 100 printed values differ from the shipped ones. Dark `bg-base` is printed as
  `#1e1e1e` and shipped as `#121110`. Light `bg-blue` is printed as `#376cff1a` and shipped as
  `#eff6ff`.
- 71 colour tokens in the stylesheet are not in the printed table.

The corpus took the stylesheet. Either set may be the stale one, and nothing public says which.
This sharpens the proposal's docs-only risk: a fidelity claim has to name which published values it
was measured against.

## Values the schema could not hold exactly

37 colour tokens state a wide-gamut `lab()` value or a `color-mix()` under `@supports`, after an
sRGB value. The corpus keeps the source's own sRGB value and records the override beside it (69
declarations). The tool converted one value, the keyword `transparent`, so there is no colour
conversion error to bound. The loss is stated instead: wide-gamut browsers render those 37 tokens
differently from the language.

Where a token has both a `base` declaration and a themed one, the themed one is taken. Cascade
order between the two was not evaluated.

## Drafts and checks

`palermo-light` and `palermo-dark` were drafted and saved privately. Both pass R1–R5 validation.
Neither passes the rendered checks on the five pages at 320, 768 and 1280, so **P2's exit is not
met**:

| Finding | Light | Dark | Cause |
| --- | --- | --- | --- |
| Target size (WCAG 2.5.8) | 16 | 16 | Roles with no type-size mapping keep the smallest type token, 10px. Nine body sizes and six title sizes are tied and wait for a reviewer. |
| Control boundary contrast (1.4.11) | 1 | 1 | No border token is placeable. `border-gray` is `#eee`, about 1.2:1 on white, so a reviewer's choice alone will not clear this. |
| Text contrast (1.4.3) | 0 | 2 | The primary control fill is paired with ordinary text. Its real partner is `text-inverse`, a Vocabulary gap. |
| Needs review | 6 | 6 | Text over imagery, as for any language. |

The meaning check on `palermo-light` reports 36 advisory findings of one kind: ingest's default
type size aliases `radius-10`, because ingest reuses any source token with an equal value. The
rendered value is right and the alias is wrong, which is the class of fault this layer exists to
show.

## What the run changed in the product

Found on Palermo, fixed generally, each with a test on an invented fixture:

- Only root and theme scopes define tokens. A utility class that sets a custom property is an
  override, not a definition.
- A theme layer's self-reference (`--x: var(--x)`) is not a value.
- When a later declaration cannot be held exactly, the source's own earlier value is kept and the
  override recorded.
- Hex shorthand is notation, not a conversion.
- A hue-named colour is a `vocabulary` gap, not neutral text.
- `--name--line-height` style suffixes name the property.
- "Primary" is a rank only beside a "secondary" in the same family. `control-primary` is not one.
- Tied candidates are not guessed between. A candidate with an unread qualifier is not placed.
- Where an emphasis has no text colour, the neutral colour stands in rather than an unrelated
  default. The default surface is also the page background.
- Ingest no longer counts negative or tracking and leading values in the type scale. Before this
  fix the drafts set every font size to a `-0.25px` letter-spacing token.

## Still open

- Jeremy's hand review of mapping precision on a sample (P1).
- Reviewer choices for type sizes, muted text and the hue-named status colours, then certification
  (P2, P3). None exists.
- Component treatments (Button, Card, Input, Badge, Tabs) through capture and fidelity review.
- A decision on inverse pairing and hue ramps in the Vocabulary.
- Whether the printed table or the stylesheet is Palermo's intended source of values.
- A role with no type-size token of its own. One token maps to one role, so a body size cannot
  also serve the action role.
