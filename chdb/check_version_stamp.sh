#!/bin/bash
# Fail a release build when the version stamped into the shipped header does not match
# the tag being released.
#
# vars.sh resolves the version from whatever git tags it can see, and this repository also
# carries upstream ClickHouse tags. The primary lookup in setup.py takes the newest tag in the
# whole repository, not the newest chdb-core release, and only rejects an upstream tag such as
# v26.7.2.59-stable because it has four components. Both fallbacks below it end at "0.0.0".
# Any of those paths would ship an engine that misreports itself through chdb_version(), and
# downstream bindings trust that string.
#
# Usage: check_version_stamp.sh <tag> [header]

set -euo pipefail

tag="${1:?usage: check_version_stamp.sh <tag> [header]}"
header="${2:-programs/local/chdb.h}"
expected="${tag#v}"

if [ ! -f "$header" ]; then
    echo "check_version_stamp: $header not found" >&2
    exit 1
fi

actual=$(sed -nE 's|^#define CHDB_VERSION "(.*)"$|\1|p' "$header")

if [ -z "$actual" ]; then
    echo "check_version_stamp: no CHDB_VERSION define in $header" >&2
    exit 1
fi

if [ "$actual" != "$expected" ]; then
    echo "check_version_stamp: $header says '$actual', release tag is '$expected'" >&2
    exit 1
fi

echo "check_version_stamp: $header carries $actual"
