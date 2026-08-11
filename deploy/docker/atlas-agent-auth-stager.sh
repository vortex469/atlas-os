#!/bin/sh
set -eu

source_path=${1:?missing source path}
destination_path=${2:?missing destination path}

fail() {
    printf '%s\n' "atlas-agent auth staging failed: $1" >&2
    exit 1
}

[ -f "$source_path" ] || fail "auth source is missing"
[ -r "$source_path" ] || fail "auth source is not readable"

destination_dir=${destination_path%/*}
mkdir -p "$destination_dir"
umask 077
temporary_path="$destination_path.tmp"
rm -f "$destination_path" "$temporary_path"
trap 'rm -f "$temporary_path"' EXIT
cp "$source_path" "$temporary_path"
chmod 0600 "$temporary_path"
chown 10001:10001 "$temporary_path"
mv -f "$temporary_path" "$destination_path"
