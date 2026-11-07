# M0 schema stress spike

2026-11-07. Bounded source inspection and throwaway mapping against the three supplied,
read-only clones. No network requests, browser captures, ingestion service, or pixel-fidelity
claim. Source observations below are inputs to Vocabulary v1, not imported site content.

## Sources and page expressions

| Source | Page / source path | Expression in Vocabulary v1 |
| --- | --- | --- |
| `wandercom/site-builder-test-sites@1866456` | `components/pages/home.tsx`, `components/hero.tsx`, `components/property-card.tsx` | `nav`, `hero` (eyebrow/title/body/two actions), `content-section` (about band), repeated `listing-card`, `content-section` (owner band), `footer` |
| `wandercom/site-builder-test-sites@1866456` | `components/pages/rentals.tsx`, `components/property-card.tsx`, `fixtures/casa-bonita/properties.json` | `nav`, compact `hero`, `content-section` (collection introduction), repeated `listing-card`, `footer` |
| `wandercom/page-sections@9d1447d` (`dev`) | `apps/sections-preview/src/data/sections/PropertyGallery.ts`, `apps/sections-preview/src/data/fixtures.ts`, `packages/components/src/shared/components/PropertyGallery/PropertyCard.tsx` | optional `content-section` heading plus a collection of `listing-card`; 0/1/many collections; `empty-state` for zero results; static `loading` depictions |

No production Wander site page or saved production HTML was found in the supplied clones.
`page-sections` includes real production-facing components and curated Wander CDN URLs, but
those are not a captured Wander page. The rentals fixture supplies the third inspected page;
production-page reconstruction remains unobserved. Remote assets were not fetched.

## Structural findings and vocabulary revision

The original seed lacked a hero and editorial band. Added `hero` and `content-section`, with
semantic headings, optional eyebrow, body, and separately named navigation actions. These
are content contracts; their layout is still owned by language treatment. `hero`'s main action
is optional because the rentals fixture's compact hero has no action. A hero can be compact
through spacing alone; that does not require a new DOM variant.

The fixture card wraps its entire content in an anchor and places location before title.
The pinned M0 card contract requires media/title/location/rating/price/action order, and only
allows div/span wrappers. Therefore that exact markup cannot be reproduced by a valid variant.
Mapping retains the destination in the action slot and the content order of the M0 contract;
the differing whole-card hit area and reading order are recorded fidelity gaps, not silently
accepted variants. The fixture's description and bedroom/sleeps metadata also exceed the pinned
card slots. They are not squeezed into `rating` or `price` under misleading roles.

The page-sections card explicitly supports vertical/horizontal layout, a separate content
region, and a media carousel. A permitted `listing-card` template for a content region is:

```html
<article>{{slot:media}}<div data-kd-part="content">{{slot:title}}{{slot:location}}{{slot:rating}}{{slot:price}}{{slot:action}}</div></article>
```

The wrapper supports component part styling while preserving required slots and order. A
horizontal orientation can use flex properties on the root; switching orientation alone does
not require a variant. Carousel controls, wishlist controls, and reveal-more interaction cannot
be introduced by a layout template: they would require vocabulary interaction contracts.
They are deferred rather than fabricated as presentation wrappers.

`PropertyCardDetails.tsx` also supports intentionally hidden prices and separately retained stay
links. The pinned M0 card has a required price slot. The spike does not reinterpret “required”:
this is a future vocabulary/version question for full-fidelity ingest.

Vocabulary now publishes ordered slot arrays with explicit `kind`, role, emphasis, requiredness,
asset kind, root, and contract reading/focus order and heading levels (contract amendment 01).
The state gallery must enumerate the vocabulary's declared states, not only language treatments.
Stress content lives in `samples.json` and context copy in `vocabulary.json`.

## Values and quantization

`site-builder-test-sites/app/globals.css` contains 4.75rem display text, 2.45rem secondary
headings, 0.76rem eyebrows, and gaps including 7, 9, 11, 17, 22, 28 and 64px. These are expressible
as exact dimension tokens; snapping them to a 4px or 8px scale would introduce measurable error.
No quantization is required by the M0 schema, so the token evaluator preserves these values.
A throwaway normalization check exercised dimensions, aliases and inheritance without rounding
them to a preferred scale.

The same sheet has `max(22px, calc((100% - var(--page)) / 2))` container padding,
`calc(100svh - 140px)` hero height, unequal fractional grids, and multi-value gaps. The closed
M0 property/value set cannot encode these expressions. They are explicit coverage limitations,
not literal CSS smuggled into token references. Breakpoint treatments can approximate fixed
sample widths, but no responsive fidelity result has been measured.

`wandercom/design-system@373cb5e`, `packages/tokens/src/*.tokens.json`, provides DTCG token-tree
examples; `packages/fonts/instrument-sans/` supplies the demonstration font. M0 implements the
contract's supported token subset, not arbitrary Terrazzo or CSS syntax.

## Assets

The Casa Bonita fixture needs its wordmark (`public/assets/logo.svg`) and local property
photographs (`public/assets/photos/`). Its stylesheet uses Georgia and Arial system families.
The page-sections examples require the remote curated photographs and logos enumerated in
`apps/sections-preview/src/data/fixtures.ts`, plus carousel/control icon treatment. Those assets
are not assumed downloaded or approved.

Harbor's authored SVG and unchanged `instrument-sans-normal.woff2` were each imported through
`import_file` and promoted through the shared `promote` operation. The library contains their
SHA-256 bytes and a font license notice. Their originals are under an external private workspace,
with no workspace paths in the library. The variable font is declared at 400/normal and
600/normal, both referring to the same bytes. The offline runtime lacks Brotli, so WOFF2 import
checks its container header; browser font decoding/usage remains a Validator/M1 check. Companion
TTF name-table metadata supplied the original copyright and SIL OFL notice.

## Observed checks and limits

Throwaway local checks passed for token normalization, override removal restoring role values,
required-slot reading order, malformed-schema findings, unchanged identity after renaming, asset
promotion and successful validation/minting of Harbor. These checks do not replace independent
Factory tests or rendered acceptance. M0 has no measured contrast, image legibility, screenshot
fidelity, or production Wander-page result; those remain unverified.
