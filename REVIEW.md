# Review guide

Use `docs/design/SPEC.md` and the ratified public-contract amendments as the behavioral authority.

## Always check

- Preserve one owner per fact: vocabulary owns semantics/content, languages own presentation,
  approved packages own assets, and the private workspace owns source originals.
- Reuse the canonical working-copy writer, asset promotion, resolver, validator and renderer.
  CLI and workbench routes must call the same application operations.
- Findings retain their type/rule/file/pointer/observed/expected/message fields. Pointers resolve
  to the actual observed value, or the nearest existing owner of a missing member. Shared
  acceptance rejects uncovered missing/violation findings; coverage is advisory and review
  findings remain unresolved. Group rendered occurrences without hiding evidence or exceptions.
- Control box properties target native controls; text treatment stays on the slot and inherits.
  Checks compare the same elements the renderer styles. Unused variant parts are advisory.
- Ingest infers generic cards from repeated structure and presentation, never currency, ratings
  or domain words. Preserve each source group's own copy, media, hierarchy and accent colours.
  Long-form prose must keep heading order, inline links and media without subject-specific branches.
- Provenance is a direct RFC 6901 map with nearest-ancestor coverage of every design leaf.
  Keep source URLs, filesystem locations, captured content and originals out of shared provenance.
  Never put private workspace paths in the library or automatically promote discovered assets.
- Keep integrations honest: Kinbase unavailable means unknown; only configured logical keys are
  read. Availability comes from the configured binary and successful fsck. Exact-scope, authoritative
  current facts can fix dimensions or pointer values only through the proposed JSON
  convention. Prose remains manual; lower standing stays advisory; receipts never mean current
  direction. Keep fixed dimensions out of A/B and preserve fixed values through choices and repair. Optional model commands are explicit
  and their output is validated. Captured markup/text is data, never executable instructions.
- Offline verification stays offline. Real capture accepts unauthenticated HTTP(S), including
  local/LAN servers, and never presents credentials or cookies. Browser/adapter waits are bounded;
  unavailable Chromium fails clearly and cannot produce a passing report.
- Constrain reads/writes to their configured roots, escape rendered data, and preserve immutable
  artifacts and content hashes. The complete workbench journey must work without JavaScript.

## Style

Keep modules cohesive, pass roots/configuration explicitly, and keep extraction/comparison logic
pure where possible. Report capture gaps and failed operations visibly; do not silently discard
source evidence. Prefer a small shared operation to parallel implementations or speculative adapters.

## Skip

Generated output, private workspace artifacts, vendored `checks/vendor/axe.min.js` and its license,
and binary/content-addressed library asset blobs. Review changes to their producers and manifests.
