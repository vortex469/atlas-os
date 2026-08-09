#!/bin/sh
set -eu

: "${CODEX_HOME:=/opt/atlas/.codex}"
: "${CODEX_AUTH_SOURCE:=/run/secrets/codex-auth.json}"

fail() {
    printf '%s\n' "atlas-agent startup gate failed: $1" >&2
    exit 1
}

[ -f "$CODEX_AUTH_SOURCE" ] || fail "Codex auth source is missing"
[ -r "$CODEX_AUTH_SOURCE" ] || fail "Codex auth source is not readable"
mkdir -p "$CODEX_HOME"

old_umask=$(umask)
umask 077
cp "$CODEX_AUTH_SOURCE" "$CODEX_HOME/auth.json"
umask "$old_umask"
chmod 0600 "$CODEX_HOME/auth.json"

[ -f "$CODEX_HOME/auth.json" ] || fail "Codex auth was not provisioned"
[ -r "$CODEX_HOME/auth.json" ] || fail "Provisioned Codex auth is not readable"
[ "$(stat -c '%a' "$CODEX_HOME/auth.json")" = "600" ] || fail "Provisioned Codex auth mode is not 0600"

if ! codex login status >/dev/null 2>&1; then
    fail "Codex authentication status is not authenticated"
fi

exec "$@"
