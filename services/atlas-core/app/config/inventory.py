from pathlib import Path

import yaml

# Atlas root = /opt/atlas
ATLAS_ROOT = Path(__file__).resolve().parents[4]
INVENTORY_FILE = ATLAS_ROOT / "inventory" / "services.yaml"


def load_inventory():
    with open(INVENTORY_FILE, "r") as f:
        return yaml.safe_load(f)
