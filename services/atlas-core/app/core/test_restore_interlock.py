from pathlib import Path

import pytest

from app.core.restore_interlock import RECOVERY_GUIDANCE, assert_restore_state_clean


def test_no_restore_namespace_allows_startup(tmp_path: Path) -> None:
    assert_restore_state_clean(tmp_path)


def test_empty_restore_namespace_allows_startup(tmp_path: Path) -> None:
    (tmp_path / ".atlas-restore").mkdir()
    assert_restore_state_clean(tmp_path)


@pytest.mark.parametrize(
    "phase",
    ("prepared", "old_generation_quarantined", "new_generation_installed", "committed"),
)
def test_any_durable_journal_blocks_startup(tmp_path: Path, phase: str) -> None:
    namespace = tmp_path / ".atlas-restore"
    namespace.mkdir()
    (namespace / "journal.json").write_text(f'{{"phase":"{phase}"}}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="atlas-data-restore"):
        assert_restore_state_clean(tmp_path)


@pytest.mark.parametrize("evidence", ("journal.json", "transaction", ".journal.json.tmp"))
def test_corrupt_or_unexpected_evidence_blocks_startup(
    tmp_path: Path, evidence: str
) -> None:
    namespace = tmp_path / ".atlas-restore"
    namespace.mkdir()
    (namespace / evidence).write_text("corrupt", encoding="utf-8")
    with pytest.raises(RuntimeError, match="recovery is required") as error:
        assert_restore_state_clean(tmp_path)
    assert str(error.value) == RECOVERY_GUIDANCE


def test_dangling_namespace_symlink_blocks_startup(tmp_path: Path) -> None:
    (tmp_path / ".atlas-restore").symlink_to(tmp_path / "missing")
    with pytest.raises(RuntimeError, match="atlas-data-restore"):
        assert_restore_state_clean(tmp_path)


def test_cleaned_completed_transaction_allows_startup(tmp_path: Path) -> None:
    namespace = tmp_path / ".atlas-restore"
    namespace.mkdir()
    (namespace / "journal.json").write_text('{"phase":"committed"}', encoding="utf-8")
    (namespace / "journal.json").unlink()
    namespace.rmdir()
    assert_restore_state_clean(tmp_path)


def test_lifespan_interlock_precedes_all_durable_store_initialization() -> None:
    main_source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")
    interlock = main_source.index("assert_restore_state_clean(")
    for durable_or_provider_initialization in (
        "OperatorIntentStore(",
        "OperatorSessionStore(",
        "OperatorSecurityAuditStore(",
        "load_provider_registry()",
        "OperationalDispatchLedger(",
        ".reconcile_startup()",
    ):
        assert interlock < main_source.index(durable_or_provider_initialization)
