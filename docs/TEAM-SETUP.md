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
```

`identity` reads Figma's `/me`; check its result before selecting files. Reading a file requires
appropriate Figma file-content permission. A successful identity lookup does not prove access to
any particular file. No credentials have been validated by this implementation's offline checks.

`pull` records the actual returned version and immutable raw file tree in the private workspace.
Observed solid fills and text styles become DTCG tokens, routed through the existing artifact and
draft operations. Use the returned artifact id with `draft --from ID --language NAME`.
Identical source bytes and version produce the same artifact identity; changed API metadata is retained as a new snapshot. This is a source snapshot,
not synchronization, a Figma plugin, or an approved design standard. Raster previews, variables,
comments and model-based interpretation of the raw layout are not implemented here.

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
