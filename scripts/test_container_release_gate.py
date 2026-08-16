from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/container-release-gate"


def test_runtime_policy_probe_preserves_lxc_inventory_without_management_identity() -> (
    None
):
    gate = GATE.read_text(encoding="utf-8")

    assert "resources/110/expectation" in gate
    assert '"resource_id":"110"' in gate
    assert '"110":{"expected":"stopped"}' in gate
    assert '"vmid": 109' in gate
    assert '"type": "lxc"' in gate
    assert '"vmid": 110' in gate
    assert '"type": "qemu"' in gate
    assert (
        'assert {item.resource_id for item in observed.resources} == {"109", "110"}'
        in gate
    )
    assert "lxc_support.authoritative_identity_supported is False" in gate
    assert "lxc_support.provider_intent_capability_supported is False" in gate
    assert "lxc_projection.management_fingerprint is None" in gate
    assert "lxc_projection.mutation_available is False" in gate
    assert "qemu_projection.management_fingerprint is not None" in gate
    assert 'resources["109"].expectation.value == "stopped"' not in gate
