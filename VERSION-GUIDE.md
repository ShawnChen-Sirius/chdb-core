# chDB Version Numbering

Release tags look like `vX.Y.Z`, with `-rc.N` appended for pre-releases.

`X.Y` tracks the ClickHouse baseline the release is synced to, and `Z` counts chdb-core's own
releases on that baseline. `v26.5.0` is therefore the first chdb-core release built on the
ClickHouse 26.5 line — not a claim about any particular ClickHouse patch level.

| Tag | Date | ClickHouse baseline |
|---|---|---|
| `v26.1.0` | 2026-03-02 | 26.1 |
| `v26.3.0` | 2026-05-11 | 26.3 |
| `v26.5.0` | 2026-06-06 | 26.5 |
| `v26.5.1-rc.1` … `-rc.3` | 2026-06-18 … 07-30 | 26.5 |

Stable releases follow the upstream sync, so the gap between them is however long that sync takes
— 26 to 70 days for the three above. Pre-releases go out in between as needed.

Major version bumps are reserved for incompatible C API changes. The `v1` / `v2` / `v3` series
predate the ClickHouse-aligned scheme and do not follow the rule above.

## Pre-releases

Pre-release tags are `-rc.N`, numbered from 1: `v26.5.1-rc.1`, `v26.5.1-rc.2`, `v26.5.1-rc.3`.
They carry the same C API as the stable release they lead up to, and are meant for testing a
baseline sync before it is declared stable.

Pre-releases are published as GitHub release artifacts. Only stable versions go to PyPI, so
`pip install chdb-core` never resolves to an `-rc` build.

## Reading the version out of a build

Three places carry it, and they answer different questions.

**`chdb_version()`** — an exported C symbol returning the release tag without the leading `v`,
for example `26.5.0`. This is what downstream bindings should call: it reports the engine that
is actually loaded, which is not necessarily the one the caller was built against.

**`CHDB_VERSION`** — the same string as a compile-time constant in `chdb.h`, for C API users who
need it without opening a connection.

**`SELECT version()`** — the ClickHouse baseline version, four components, for example `26.5.1.1`.
This is ClickHouse's own number and does not match the chdb-core tag. Do not compare the two.

Both `chdb_version()` and `CHDB_VERSION` landed after `v26.5.1-rc.3`, so the first artifact
carrying them is the next release. Bindings targeting older engines need a fallback.

## How the version gets stamped

`chdb/vars.sh` derives the version from the git tag at build time and rewrites the
`CHDB_VERSION` line in `programs/local/chdb.h` before the header is packaged. The value committed
to the repository is only a default for source-only builds; a release artifact always carries the
tag it was built from.

Release builds verify this with `chdb/check_version_stamp.sh`, which fails the build if the
stamped value and the release tag disagree. That check matters because the repository also carries
upstream ClickHouse tags, and the tag lookup in `setup.py` picks the newest tag in the repository
rather than the newest chdb-core release — it currently rejects those upstream tags only because
they have four components.
