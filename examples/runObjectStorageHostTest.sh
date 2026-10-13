#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"
test_dir=$(mktemp -d)
trap 'rm -f "$test_dir/host-test"; rmdir "$test_dir"' EXIT

${CC:-clang} -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror \
    -fsanitize=address,undefined -fno-sanitize-recover=all \
    objectStorageMemStoreTest.c objectStorageMemStore.c -I../programs/local -lpthread \
    -o "$test_dir/host-test"
"$test_dir/host-test"
CHDB_TEST_SERVICE_THREAD=1 "$test_dir/host-test"
