#!/usr/bin/env bash

cd /opt/atlas/services/atlas-core || return 1
source .venv/bin/activate

echo "Atlas Core development environment ready."
