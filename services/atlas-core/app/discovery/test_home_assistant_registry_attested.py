from __future__ import annotations

import asyncio
import inspect
import traceback
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.discovery import home_assistant_ghcr_acquisition as acquisition
from app.discovery import home_assistant_registry_attested as integration
from app.discovery import home_assistant_sigstore_verifier as sigstore
from app.discovery.models import ImageReleaseEvidenceSourceClass

_TIME = datetime(2026, 8, 21, 20, 54, 36, tzinfo=UTC)


class _FakeAcquirer:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    async def acquire(self):
        if self.error is not None:
            raise self.error
        return self.result


def _acquired(*bundles: bytes):
    return acquisition._HomeAssistantGHCRAcquisition(
        release_version=acquisition._RELEASE,
        image_reference=acquisition._IMAGE_REFERENCE,
        index_digest=acquisition._EXPECTED_DIGEST,
        index_media_type=acquisition._INDEX_MEDIA_TYPE,
        index_bytes=b"fixture index representation",
        sigstore_bundles=bundles,
    )


def _verified(**changes):
    values = {
        "release_version": sigstore._RELEASE,
        "image_digest": sigstore._IMAGE_DIGEST,
        "source_commit_sha": sigstore._WORKFLOW_SHA,
        "authenticated_ref": sigstore._REF,
        "authenticated_repository": sigstore._REPOSITORY,
        "authenticated_workflow_identity": sigstore._IDENTITY,
        "authenticated_workflow_name": sigstore._WORKFLOW_NAME,
        "integrated_at": _TIME,
    }
    values.update(changes)
    return sigstore._VerifiedHomeAssistantAttestation(**values)


def _collect(monkeypatch, acquired, verifier=lambda **_: _verified()):
    monkeypatch.setattr(
        integration, "_HomeAssistantGHCRAcquirer", lambda: _FakeAcquirer(acquired)
    )
    monkeypatch.setattr(integration, "verify_home_assistant_2026_8_3_bundle", verifier)
    return asyncio.run(
        integration.HomeAssistantRegistryAttestedAdapter().collect_async()
    )


def _assert_failure(monkeypatch, reason, acquired, verifier=lambda **_: _verified()):
    with pytest.raises(integration.HomeAssistantRegistryAttestedError) as caught:
        _collect(monkeypatch, acquired, verifier)
    assert caught.value.reason is reason
    assert str(caught.value) == reason.value
    assert caught.value.__cause__ is None


def test_constructor_has_no_acquirer_or_verifier_parameter() -> None:
    assert (
        inspect.signature(integration.HomeAssistantRegistryAttestedAdapter).parameters
        == {}
    )


def test_one_valid_bundle_produces_exact_registry_attested_result(monkeypatch) -> None:
    result = _collect(monkeypatch, _acquired(b"bundle"))
    assert result.candidate.model_dump() == {
        "schema_version": "collector-candidate-fact-v1",
        "release_version": "2026.8.3",
        "image_reference": "ghcr.io/home-assistant/home-assistant",
        "image_digest": acquisition._EXPECTED_DIGEST,
        "attested_at": _TIME,
    }
    assert result.row.model_dump() == {
        "catalog_item_id": "home-assistant",
        "release_version": "2026.8.3",
        "image_reference": "ghcr.io/home-assistant/home-assistant",
        "image_digest": acquisition._EXPECTED_DIGEST,
        "source_class": ImageReleaseEvidenceSourceClass.REGISTRY_ATTESTED,
        "source_id": "collector:home-assistant-ghcr-cosign",
        "attested_at": _TIME,
    }


def test_equivalent_valid_bundles_produce_same_deterministic_row(monkeypatch) -> None:
    two = _collect(monkeypatch, _acquired(b"one", b"two")).row
    one = _collect(monkeypatch, _acquired(b"one")).row
    assert two == one


def test_acquisition_failure_is_fully_redacted(monkeypatch) -> None:
    markers = "TOKEN_MARKER RAW_BUNDLE_MARKER CERTIFICATE_MARKER REKOR_MARKER SIGSTORE_INTERNAL_MARKER"
    monkeypatch.setattr(
        integration,
        "_HomeAssistantGHCRAcquirer",
        lambda: _FakeAcquirer(error=RuntimeError(markers)),
    )
    with pytest.raises(integration.HomeAssistantRegistryAttestedError) as caught:
        asyncio.run(integration.HomeAssistantRegistryAttestedAdapter().collect_async())
    assert (
        caught.value.reason
        is integration.HomeAssistantRegistryAttestedFailure.ACQUISITION_FAILED
    )
    assert caught.value.__cause__ is None
    rendered = "".join(traceback.format_exception(caught.value))
    assert all(marker not in rendered for marker in markers.split())


def test_zero_bundles_fails_no_valid_signature(monkeypatch) -> None:
    _assert_failure(
        monkeypatch,
        integration.HomeAssistantRegistryAttestedFailure.NO_VALID_SIGNATURE,
        _acquired(),
    )


@pytest.mark.parametrize(
    "bundles",
    [(b"bad-one", b"bad-two"), (b"bad-one", b"bad-two", b"bad-three")],
)
def test_all_invalid_multiple_bundles_attempts_every_bundle(
    monkeypatch, bundles
) -> None:
    calls = []

    def invalid(*, bundle_bytes):
        calls.append(bundle_bytes)
        raise sigstore.HomeAssistantSigstoreVerificationError("REKOR_MARKER")

    _assert_failure(
        monkeypatch,
        integration.HomeAssistantRegistryAttestedFailure.CRYPTOGRAPHIC_VERIFICATION_FAILED,
        _acquired(*bundles),
        invalid,
    )
    assert calls == list(bundles)


@pytest.mark.parametrize("bundles", [(b"bad", b"good"), (b"good", b"bad")])
def test_valid_and_invalid_orderings_fail_after_attempting_both(
    monkeypatch, bundles
) -> None:
    calls = []

    def verifier(*, bundle_bytes):
        calls.append(bundle_bytes)
        if bundle_bytes == b"bad":
            raise sigstore.HomeAssistantSigstoreVerificationError("CERTIFICATE_MARKER")
        return _verified()

    _assert_failure(
        monkeypatch,
        integration.HomeAssistantRegistryAttestedFailure.CRYPTOGRAPHIC_VERIFICATION_FAILED,
        _acquired(*bundles),
        verifier,
    )
    assert calls == list(bundles)


@pytest.mark.parametrize(
    "bundles",
    [(b"bad", b"one", b"two"), (b"two", b"bad", b"one"), (b"one", b"two", b"bad")],
)
def test_invalid_and_contradictory_valid_is_order_invariant(
    monkeypatch, bundles
) -> None:
    calls = []

    def verifier(*, bundle_bytes):
        calls.append(bundle_bytes)
        if bundle_bytes == b"bad":
            raise RuntimeError("SIGSTORE_INTERNAL_MARKER")
        if bundle_bytes == b"two":
            return _verified(integrated_at=datetime(2026, 8, 22, tzinfo=UTC))
        return _verified()

    _assert_failure(
        monkeypatch,
        integration.HomeAssistantRegistryAttestedFailure.CRYPTOGRAPHIC_VERIFICATION_FAILED,
        _acquired(*bundles),
        verifier,
    )
    assert calls == list(bundles)


def test_verification_failure_traceback_is_fully_redacted(monkeypatch) -> None:
    markers = "TOKEN_MARKER RAW_BUNDLE_MARKER CERTIFICATE_MARKER REKOR_MARKER SIGSTORE_INTERNAL_MARKER"

    def invalid(**_):
        raise RuntimeError(markers)

    with pytest.raises(integration.HomeAssistantRegistryAttestedError) as caught:
        _collect(monkeypatch, _acquired(b"raw"), invalid)
    assert (
        caught.value.reason
        is integration.HomeAssistantRegistryAttestedFailure.CRYPTOGRAPHIC_VERIFICATION_FAILED
    )
    assert caught.value.__cause__ is None
    rendered = "".join(traceback.format_exception(caught.value))
    assert all(marker not in rendered for marker in markers.split())


def test_contradictory_valid_signatures_fail_closed(monkeypatch) -> None:
    results = iter(
        [_verified(), _verified(integrated_at=datetime(2026, 8, 22, tzinfo=UTC))]
    )
    _assert_failure(
        monkeypatch,
        integration.HomeAssistantRegistryAttestedFailure.CONTRADICTORY_VERIFIED_SIGNATURES,
        _acquired(b"one", b"two"),
        lambda **_: next(results),
    )


def test_digest_disagreement_fails(monkeypatch) -> None:
    _assert_failure(
        monkeypatch,
        integration.HomeAssistantRegistryAttestedFailure.DIGEST_DISAGREEMENT,
        replace(_acquired(b"bundle"), index_digest="sha256:" + "0" * 64),
    )


@pytest.mark.parametrize(
    "acquired",
    [
        replace(_acquired(b"bundle"), release_version="2026.8.4"),
        replace(_acquired(b"bundle"), image_reference="example.invalid/image"),
    ],
)
def test_acquisition_release_or_image_disagreement_fails(monkeypatch, acquired) -> None:
    _assert_failure(
        monkeypatch,
        integration.HomeAssistantRegistryAttestedFailure.RELEASE_IDENTITY_DISAGREEMENT,
        acquired,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"release_version": "2026.8.4"},
        {"authenticated_ref": "refs/tags/wrong"},
        {"authenticated_repository": "wrong/repository"},
        {"authenticated_workflow_identity": "https://wrong.invalid"},
        {"authenticated_workflow_name": "wrong"},
        {"source_commit_sha": "0" * 40},
    ],
)
def test_verified_release_or_identity_disagreement_fails(monkeypatch, changes) -> None:
    _assert_failure(
        monkeypatch,
        integration.HomeAssistantRegistryAttestedFailure.RELEASE_IDENTITY_DISAGREEMENT,
        _acquired(b"bundle"),
        lambda **_: _verified(**changes),
    )


@pytest.mark.parametrize("timestamp", [None, _TIME.replace(tzinfo=None)])
def test_missing_or_unauthenticated_timestamp_fails(monkeypatch, timestamp) -> None:
    _assert_failure(
        monkeypatch,
        integration.HomeAssistantRegistryAttestedFailure.MISSING_AUTHENTICATED_TIMESTAMP,
        _acquired(b"bundle"),
        lambda **_: _verified(integrated_at=timestamp),
    )


def test_private_proof_values_cannot_be_supplied_to_adapter_api() -> None:
    acquisition_value = _acquired(b"bundle")
    verified_value = _verified()
    with pytest.raises(TypeError):
        integration.HomeAssistantRegistryAttestedAdapter(acquirer=acquisition_value)
    with pytest.raises(TypeError):
        integration.HomeAssistantRegistryAttestedAdapter(verifier=verified_value)
