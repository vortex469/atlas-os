from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import FrozenInstanceError, asdict
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sigstore.models import TrustedRoot
from sigstore_models.trustroot import v1 as trustroot_v1

import app.discovery.home_assistant_sigstore_verifier as verifier_module
from app.discovery.home_assistant_sigstore_verifier import (
    HomeAssistantSigstoreVerificationError,
    _validate_statement,
    verify_home_assistant_2026_8_3_bundle,
)

_FIXTURE = (
    Path(__file__).parent / "testdata/home_assistant_sigstore/ha-2026.8.3-bundle.json"
)
_FIXTURE_SHA256 = "733e4755b02bb6786eeb51942dff588e8f043dcca13bc99a2b9fe0dd3e225520"
_TRUST_ROOT = Path(__file__).parent / "trust/sigstore-production-trusted-root.json"
_TRUST_ROOT_SHA256 = "6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66"
_DIGEST = "sha256:14931c6b13756317849f46da1d01b45937a1150db66c081cfe529d48215943fe"


def _verify(bundle: bytes | None = None):
    return verify_home_assistant_2026_8_3_bundle(
        bundle_bytes=_FIXTURE.read_bytes() if bundle is None else bundle
    )


def _mutated_bundle(path: tuple[str | int, ...], mutate) -> bytes:
    document = json.loads(_FIXTURE.read_bytes())
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = mutate(target[path[-1]])
    return json.dumps(document, separators=(",", ":")).encode()


def _flip_base64(value: str) -> str:
    raw = bytearray(base64.b64decode(value))
    raw[len(raw) // 2] ^= 1
    return base64.b64encode(raw).decode()


def test_checked_in_fixture_identity_and_media_type() -> None:
    fixture = _FIXTURE.read_bytes()
    assert hashlib.sha256(fixture).hexdigest() == _FIXTURE_SHA256
    assert json.loads(fixture)["mediaType"] == (
        "application/vnd.dev.sigstore.bundle.v0.3+json"
    )


def test_checked_in_trust_root_identity_and_parseability() -> None:
    trust_root = _TRUST_ROOT.read_bytes()
    assert len(trust_root) == 6787
    assert hashlib.sha256(trust_root).hexdigest() == _TRUST_ROOT_SHA256
    assert TrustedRoot.from_file(str(_TRUST_ROOT)) is not None


def test_exact_fixture_verifies() -> None:
    result = _verify()
    assert asdict(result) == {
        "release_version": "2026.8.3",
        "image_digest": _DIGEST,
        "source_commit_sha": "759e4658f40b3ccb671d418b8a0ed95224bf4561",
        "authenticated_ref": "refs/tags/2026.8.3",
        "authenticated_repository": "home-assistant/core",
        "authenticated_workflow_identity": "https://github.com/home-assistant/core/.github/workflows/builder.yml@refs/tags/2026.8.3",
        "authenticated_workflow_name": "Build images",
        "integrated_at": datetime(2026, 8, 21, 20, 54, 36, tzinfo=UTC),
    }
    with pytest.raises(FrozenInstanceError):
        result.release_version = "other"


def _verify_with_authenticated_times(monkeypatch, times, *, raw_entries=False):
    document = json.loads(_FIXTURE.read_bytes())
    payload = base64.b64decode(document["dsseEnvelope"]["payload"])
    entries = (
        times
        if raw_entries
        else [SimpleNamespace(integrated_time=value) for value in times]
    )
    bundle = SimpleNamespace(
        _inner=SimpleNamespace(
            media_type=verifier_module._BUNDLE_MEDIA_TYPE,
            verification_material=SimpleNamespace(tlog_entries=entries),
        )
    )

    class FakeBundle:
        @staticmethod
        def from_json(_bundle_bytes):
            return bundle

    class FakeVerifier:
        def __init__(self, *, trusted_root):
            assert trusted_root is not None

        def verify_dsse(self, *, bundle, policy):
            assert bundle is not None
            assert policy is not None
            return verifier_module._DSSE_PAYLOAD_TYPE, payload

    monkeypatch.setattr("sigstore.models.Bundle", FakeBundle)
    monkeypatch.setattr("sigstore.verify.Verifier", FakeVerifier)
    monkeypatch.setattr(verifier_module, "_load_trusted_root", object)
    return _verify(b"controlled bundle bytes")


def _verify_with_missing_authenticated_time(monkeypatch):
    return _verify_with_authenticated_times(
        monkeypatch, [SimpleNamespace()], raw_entries=True
    )


def test_exactly_one_authenticated_tlog_entry_returns_utc_time(monkeypatch) -> None:
    result = _verify_with_authenticated_times(monkeypatch, [1787345676])
    assert result.integrated_at == datetime(2026, 8, 21, 20, 54, 36, tzinfo=UTC)
    assert result.integrated_at.tzinfo is UTC


@pytest.mark.parametrize("times", [[], [1787345676, 1787345676]])
def test_tlog_entry_count_must_be_exactly_one(monkeypatch, times) -> None:
    with pytest.raises(HomeAssistantSigstoreVerificationError, match="exactly one"):
        _verify_with_authenticated_times(monkeypatch, times)


def test_missing_integrated_time_fails(monkeypatch) -> None:
    with pytest.raises(HomeAssistantSigstoreVerificationError, match="time is invalid"):
        _verify_with_missing_authenticated_time(monkeypatch)


@pytest.mark.parametrize(
    "value",
    [None, "1787345676", 1787345676.0, True, -1, 253402300800],
)
def test_integrated_time_must_be_bounded_integer(monkeypatch, value) -> None:
    with pytest.raises(HomeAssistantSigstoreVerificationError, match="time is invalid"):
        _verify_with_authenticated_times(monkeypatch, [value])


def test_one_byte_trust_root_mutation_fails_before_sigstore_verification(
    monkeypatch, tmp_path: Path
) -> None:
    mutated = bytearray(_TRUST_ROOT.read_bytes())
    whitespace = mutated.index(b" ")
    mutated[whitespace] = ord("\t")
    path = tmp_path / "trusted-root.json"
    path.write_bytes(mutated)
    monkeypatch.setattr(verifier_module, "_TRUSTED_ROOT_PATH", path)

    called = False

    def forbidden_verify(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Sigstore verification must not run")

    monkeypatch.setattr("sigstore.verify.Verifier.verify_dsse", forbidden_verify)
    with pytest.raises(
        HomeAssistantSigstoreVerificationError,
        match="reviewed Sigstore trust root does not match",
    ):
        _verify()
    assert not called


def test_different_valid_trusted_root_is_rejected(monkeypatch, tmp_path: Path) -> None:
    different = json.dumps(json.loads(_TRUST_ROOT.read_bytes())).encode()
    assert TrustedRoot(trustroot_v1.TrustedRoot.from_json(different)) is not None
    path = tmp_path / "different-valid-trusted-root.json"
    path.write_bytes(different)
    monkeypatch.setattr(verifier_module, "_TRUSTED_ROOT_PATH", path)

    with pytest.raises(
        HomeAssistantSigstoreVerificationError,
        match="reviewed Sigstore trust root does not match",
    ):
        _verify()


def test_result_constructor_is_not_treated_as_provenance() -> None:
    constructed = verifier_module._VerifiedHomeAssistantAttestation(
        release_version="unverified",
        image_digest="unverified",
        source_commit_sha="unverified",
        authenticated_ref="unverified",
        authenticated_repository="unverified",
        authenticated_workflow_identity="unverified",
        authenticated_workflow_name="unverified",
        integrated_at=datetime(2000, 1, 1, tzinfo=UTC),
    )
    assert constructed.release_version == "unverified"


def test_only_bundle_bytes_are_caller_controlled() -> None:
    import inspect

    assert list(
        inspect.signature(verify_home_assistant_2026_8_3_bundle).parameters
    ) == ["bundle_bytes"]


def test_malformed_bundle_json_is_rejected() -> None:
    with pytest.raises(
        HomeAssistantSigstoreVerificationError, match="verification failed"
    ):
        _verify(b"{not-json")


@pytest.mark.parametrize(
    "path",
    [
        ("dsseEnvelope", "payload"),
        ("dsseEnvelope", "signatures", 0, "sig"),
    ],
)
def test_modified_signed_dsse_material_is_rejected(path) -> None:
    with pytest.raises(
        HomeAssistantSigstoreVerificationError, match="verification failed"
    ):
        _verify(_mutated_bundle(path, _flip_base64))


@pytest.mark.parametrize(
    ("name", "replacement"),
    [
        ("_ISSUER", "https://wrong.example"),
        (
            "_IDENTITY",
            "https://github.com/home-assistant/core/wrong.yml@refs/tags/2026.8.3",
        ),
        ("_REPOSITORY", "wrong/repository"),
        ("_REF", "refs/tags/2026.8.4"),
        ("_WORKFLOW_SHA", "0" * 40),
        ("_WORKFLOW_NAME", "Wrong workflow"),
    ],
)
def test_wrong_code_owned_certificate_policy_is_rejected(
    monkeypatch, name: str, replacement: str
) -> None:
    monkeypatch.setattr(verifier_module, name, replacement)
    with pytest.raises(
        HomeAssistantSigstoreVerificationError, match="verification failed"
    ):
        _verify()


def _statement(**changes) -> bytes:
    value = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"digest": {"sha256": _DIGEST[7:]}, "annotations": {}}],
        "predicateType": "https://sigstore.dev/cosign/sign/v1",
        "predicate": {},
    }
    value.update(changes)
    return json.dumps(value).encode()


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        _statement(_type="wrong"),
        _statement(predicateType="wrong"),
        _statement(predicate={"extra": True}),
        _statement(extra=True),
        _statement(subject=[]),
        _statement(
            subject=[
                {"digest": {"sha256": _DIGEST[7:]}, "annotations": {}},
                {"digest": {"sha256": _DIGEST[7:]}, "annotations": {}},
            ]
        ),
        _statement(subject=[{"digest": {"sha256": "0" * 64}, "annotations": {}}]),
        _statement(
            subject=[
                {
                    "digest": {"sha256": _DIGEST[7:], "sha512": "extra"},
                    "annotations": {},
                }
            ]
        ),
        b'{"_type":"https://in-toto.io/Statement/v1","_type":"duplicate","subject":[],"predicateType":"https://sigstore.dev/cosign/sign/v1","predicate":{}}',
    ],
)
def test_malformed_or_ambiguous_statement_is_rejected(payload: bytes) -> None:
    with pytest.raises(HomeAssistantSigstoreVerificationError):
        _validate_statement(payload)


def test_wrong_payload_type_is_cryptographically_rejected() -> None:
    bundle = _mutated_bundle(("dsseEnvelope", "payloadType"), lambda _: "wrong")
    with pytest.raises(
        HomeAssistantSigstoreVerificationError, match="verification failed"
    ):
        _verify(bundle)


def test_corrupted_rekor_inclusion_promise_is_rejected() -> None:
    path = (
        "verificationMaterial",
        "tlogEntries",
        0,
        "inclusionPromise",
        "signedEntryTimestamp",
    )
    with pytest.raises(
        HomeAssistantSigstoreVerificationError, match="verification failed"
    ):
        _verify(_mutated_bundle(path, _flip_base64))


def test_independently_corrupted_rekor_inclusion_proof_is_rejected() -> None:
    path = (
        "verificationMaterial",
        "tlogEntries",
        0,
        "inclusionProof",
        "hashes",
        0,
    )
    with pytest.raises(
        HomeAssistantSigstoreVerificationError, match="verification failed"
    ):
        _verify(_mutated_bundle(path, _flip_base64))


def test_corrupted_certificate_is_rejected() -> None:
    bundle = _mutated_bundle(
        ("verificationMaterial", "certificate", "rawBytes"), _flip_base64
    )
    with pytest.raises(
        HomeAssistantSigstoreVerificationError, match="verification failed"
    ):
        _verify(bundle)
