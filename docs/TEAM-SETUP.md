# Team deployment and shared design resources

## Deployment model

Run the workbench locally for each person, from a pinned Git revision. Keep each person's
workspace private. Share approved language versions/assets through a private team Git repository
(or an approved folder in an existing repository), reviewed like other changes. Do not put source
captures, private Figma documents, company standards, credentials or personal feedback in this
public tool repository. A Git checkout is not concurrent multi-user storage; each person uses a
local clone and reviews/pushes changes through the team's normal process.

```
./scripts/setup-local.sh --with-browser
.venv/bin/kinbase-design serve --library /path/to/private-library/library
```

The setup script uses pinned runtime package versions and installs the tool into a local `.venv`.
It does not modify shell profiles, configure credentials or contact Company memory. Chromium
installation is opt-in. Platform wheels/browser availability must be verified on the target host.
The server remains loopback-only: no shared web deployment is claimed. A centrally hosted UI
would additionally need identity, workspace isolation, authorization and job ownership.

## Figma source acquisition

Use a token for the intended company account, supplied as `FIGMA_ACCESS_TOKEN` by your existing
secret manager. Never put it on a command line, in TOML, or in Git. There is deliberately no
fallback to another project's environment variable.

```
.venv/bin/kinbase-design figma identity
.venv/bin/kinbase-design figma pull --file-key FILE_KEY --version VERSION_ID
.venv/bin/kinbase-design figma pull --file-key FILE_KEY --version VERSION_ID --source-node 1:2 --source-node 3:4
```

`identity` reads Figma's `/me`; check its result before selecting files. Reading a file requires
appropriate Figma file-content permission. A successful identity lookup does not prove access to
any particular file. No credentials have been validated by this implementation's offline checks.

`pull` records the actual returned version and immutable raw file tree in the private workspace.
Observed solid fills and text styles become DTCG tokens, routed through the existing artifact and
draft operations. Use the returned artifact id with `draft --from ID --language NAME`.
Identical source bytes, version and requested selection produce the same artifact identity; changed API metadata is retained as a new snapshot. This is a source snapshot,
not synchronization, a Figma plugin, or an approved design standard. Optional PNG node renders, live variables and comments are available through explicit flags.
Model-based semantic interpretation of images/layout is not implemented.

Repeat `--source-node ID` to request source nodes through the `ids` query on Figma's
[file endpoint](https://developers.figma.com/docs/rest-api/file-endpoints/), together with
`version` when supplied. Without it, acquisition keeps its whole-file behavior. This differs
from `--render-node`, which requests optional PNGs. The Python operation appends the optional
`snapshot(..., source_nodes=())` argument; existing positional arguments retain their meanings.
IDs are trimmed, deduplicated and sorted. The normalized list appears as `source_nodes` in the
receipt and `details.source.source_nodes` in the immutable artifact metadata, only when selected.
Figma may include ancestors, dependencies and pages: the complete returned response is retained,
not filtered to an exclusive subtree. A missing requested node fails before capture artifacts are
created. The existing 100 MiB response and 100,000-node traversal limits still apply.

## Company learning: one service, separate evidence and authority

Reuse the existing Wander Company Kinbase deployment and its scoped source publishers, not a
second Company store or a copy of its database/seed. Each repository retains its own `.kin`
codebase evidence; private personal memory is separate. Configure the installed Kinbase client
with that deployment's endpoint, trusted Company key and a per-user facts token via the Company's
existing onboarding process. Do not copy operator signing/admin keys to designers' laptops.

The design tool's existing `[kinbase]` configuration points at the initialized/certified local
repository and registered design-standard/direction logical keys. Check availability with the
actual client. Unknown or conflicting standards remain visible, not invented.

Figma snapshots are observations. To make them part of shared learning, extend the existing
Company source publisher with version/node provenance and the approved file scope. Keep machine
observations capped at the existing machine standing; Lauren's design rulings belong to an
explicit design authority scope. A document importer alone is not sufficient: generic documents
may default to Personal, and copying a snapshot into `.kin` does not establish Company authority.
Vision interpretation, when added, runs outside the authoritative reducer and retains its source
image/version and uncertainty. Feedback must not silently become a mandatory standard.

Still required from the existing Company deployment owners: approved Figma account/files, the
publisher adapter and refresh schedule, Lauren's registered design scope/logical keys, and a
verified end-to-end source change -> observation -> authorized ruling -> refreshed design input.
This release does not claim that live learning or automatic Figma monitoring is connected.

## Optional Figma evidence and Company publisher handoff

```
.venv/bin/kinbase-design figma pull --file-key FILE --version VERSION --render-node 1:2 --variables --comments
.venv/bin/kinbase-design evidence-export --artifact ARTIFACT --out /private/company-corpus/design-evidence/observations-ARTIFACT.jsonl
```

Rendering is pinned to the captured file version and restricted to requested nodes present in
that file. PNGs feed existing image sampling and visual-reference ingestion. API tokens never
travel to image hosts. Failed/denied optional endpoints are reported as gaps without discarding
the core snapshot. A partial pull is not complete evidence.

Variables and comments endpoints return **file-wide, live, unversioned** state, even when the
document was requested with source-node selection or at an older version. Their observation
timestamps and this limitation are retained. The optional local variables endpoint requires
full Enterprise organization membership and `file_variables:read`, as described in Figma's
[variables documentation](https://developers.figma.com/docs/rest-api/variables-endpoints/).
Color variables preserve mode identity; same-mode aliases resolve without inventing cross-mode
values. Other variable types and unresolved aliases remain raw source evidence. Comments stay in private artifacts until explicitly exported to the private Company corpus;
a commenter name or Figma account ID is not automatically Company authority. Exports label
comment text as unverified source observations and excerpts when bounded.

Evidence export produces `design-evidence/1` JSONL for a corresponding adapter in the existing
Company publisher. Records carry version/node/source identity, immutable artifact digest and
machine authorship. Render references are evidence pointers and comment text is attributed source evidence, not semantic vision claims
or automatic design rulings. Status is `prepared-not-submitted`; neither source acquisition nor
export contacts Kinbase. Do not place this evidence in the public design tool repository.
Only the approved Company publisher should submit it with its existing capped machine standing.
The publisher adapter and authorized deployment must be verified before claiming shared learning.
Lauren's delegated design authority requires the Company policy to support it; never relabel her
as founder or infer authority from a typed name.

Observation IDs are stable by Figma file and evidence kind, plus node ID for node values/renders
or comment ID for comments. Versions, artifact digests and values remain provenance, not identity.
All measured properties of a node form one replaceable observation, so changing or removing a
field updates that observation rather than leaving the old field as an independent current fact.
Records without the required source node/comment identity are not exported. Entirely deleted
nodes/comments and nodes losing all measured values still require explicit publisher retraction;
absence in a partial snapshot is not a deletion. The additive handoff does not implement that
retraction or determine whether an intentionally historical snapshot should replace current
observations. Publish current captures in source order, not arbitrary historical replays.
For versioned node/render evidence, `updated_at` uses Figma's `lastModified` when available;
`source.time_basis` records `source-modified`. Live endpoints use `observed`. Legacy snapshots
without source time use `capture-fallback`, which is not evidence of version freshness and must
not automatically supersede an existing Company observation. Capture time does not make an
older source version newer.

Before writing an evidence export, every record is checked against the Company's publisher
contract: the exact top-level/source field sets, 64-character lowercase hex identity, bounded
source strings (256 characters), 1–16 nonempty evidence references (2048 characters each),
full whitespace-flattened publisher text (fixed prefix, non-ASCII-preserving sorted source JSON,
separator and statement) at most 16 KiB, and a valid timezone-qualified ISO timestamp.
Any rejected record fails the entire export visibly before creating/replacing the output.
Nothing is silently truncated to meet admission bounds. This validation does not add retraction:
absent observations still cannot retract prior publisher state.
