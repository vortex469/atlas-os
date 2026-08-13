#!/bin/sh
set -eu

CODEX_HOME=${CODEX_HOME:-/opt/atlas/.codex}
CODEX_AUTH_SOURCE=${CODEX_AUTH_SOURCE:-/run/secrets/codex-auth.json}

if [ -e "$CODEX_AUTH_SOURCE" ]; then
    if [ ! -f "$CODEX_AUTH_SOURCE" ] || [ ! -r "$CODEX_AUTH_SOURCE" ]; then
        echo "Codex auth source is not a readable regular file" >&2
        exit 78
    fi

    mkdir -p "$CODEX_HOME"
    old_umask=$(umask)
    umask 077
    cp "$CODEX_AUTH_SOURCE" "$CODEX_HOME/auth.json"
    umask "$old_umask"
    chmod 0600 "$CODEX_HOME/auth.json"
fi

exec "$@"
