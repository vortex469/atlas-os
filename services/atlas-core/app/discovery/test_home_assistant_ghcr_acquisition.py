from __future__ import annotations

import asyncio
import hashlib
import json
import ssl
import time
from collections import deque
from pathlib import Path

import pytest

import app.discovery.home_assistant_ghcr_acquisition as acquisition


def _json(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


def _digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


class _FakeTransport:
    def __init__(self, responses: list[acquisition._Response]) -> None:
        self.responses = deque(responses)
        self.calls: list[dict[str, object]] = []

    async def get(self, **kwargs) -> acquisition._Response:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.popleft()


def _response(
    status: int,
    body: bytes = b"",
    *,
    media: str = "application/json",
    **headers: str,
) -> acquisition._Response:
    return acquisition._Response(
        status=status,
        headers={"content-type": media, **headers},
        body=body,
    )


def _challenge(value: str | None = None) -> acquisition._Response:
    return _response(
        401,
        **{
            "www-authenticate": value
            or 'Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:home-assistant/home-assistant:pull"'
        },
    )


def _scenario(
    monkeypatch,
    *,
    final_index: bytes | None = None,
    bundle: bytes | None = None,
) -> tuple[_FakeTransport, bytes, bytes]:
    index = _json(
        {
            "schemaVersion": 2,
            "mediaType": acquisition._INDEX_MEDIA_TYPE,
            "manifests": [
                {
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "digest": f"sha256:{'1' * 64}",
                    "size": 100,
                }
            ],
        }
    )
    expected = _digest(index)
    monkeypatch.setattr(acquisition, "_EXPECTED_DIGEST", expected)
    bundle = (
        bundle
        or (
            Path(__file__).parent
            / "testdata/home_assistant_sigstore/ha-2026.8.3-bundle.json"
        ).read_bytes()
    )
    bundle_descriptor = {
        "mediaType": acquisition._BUNDLE_MEDIA_TYPE,
        "digest": _digest(bundle),
        "size": len(bundle),
    }
    artifact = _json(
        {
            "schemaVersion": 2,
            "mediaType": acquisition._ARTIFACT_MEDIA_TYPE,
            "artifactType": acquisition._BUNDLE_MEDIA_TYPE,
            "subject": {
                "mediaType": acquisition._INDEX_MEDIA_TYPE,
                "digest": expected,
                "size": len(index),
            },
            "layers": [bundle_descriptor],
        }
    )
    artifact_digest = _digest(artifact)
    referrers = _json(
        {
            "schemaVersion": 2,
            "mediaType": acquisition._INDEX_MEDIA_TYPE,
            "manifests": [
                {
                    "mediaType": acquisition._ARTIFACT_MEDIA_TYPE,
                    "digest": artifact_digest,
                    "size": len(artifact),
                    "artifactType": acquisition._BUNDLE_MEDIA_TYPE,
                }
            ],
        }
    )
    index_response = lambda value: _response(
        200,
        value,
        media=acquisition._INDEX_MEDIA_TYPE,
        **{"docker-content-digest": _digest(value)},
    )
    fake = _FakeTransport(
        [
            _challenge(),
            _response(200, b'{"token":"secret"}'),
            index_response(index),
            _response(200, referrers, media=acquisition._INDEX_MEDIA_TYPE),
            _response(200, artifact, media=acquisition._ARTIFACT_MEDIA_TYPE),
            _response(200, bundle, media=acquisition._BUNDLE_MEDIA_TYPE),
            index_response(final_index or index),
        ]
    )
    return fake, index, bundle


def test_exact_acquisition_and_fixed_request_flow(monkeypatch) -> None:
    fake, index, bundle = _scenario(monkeypatch)
    result = asyncio.run(
        acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire()
    )
    assert result.index_bytes == index
    assert result.index_digest == _digest(index)
    assert result.index_media_type == acquisition._INDEX_MEDIA_TYPE
    assert result.sigstore_bundles == (bundle,)
    assert [call["path"] for call in fake.calls[:4]] == [
        acquisition._MANIFEST_PATH,
        acquisition._TOKEN_PATH,
        acquisition._MANIFEST_PATH,
        acquisition._REFERRERS_PATH,
    ]
    assert fake.calls[1]["host"] == "ghcr.io"
    assert fake.calls[1].get("authorization") is None
    assert fake.calls[2]["authorization"] == "Bearer secret"
    assert all(call["host"] == "ghcr.io" for call in fake.calls)


@pytest.mark.parametrize(
    "value",
    [
        'Bearer realm="https://evil.example/token",service="ghcr.io",scope="repository:home-assistant/home-assistant:pull"',
        'Bearer realm="https://ghcr.io/token",service="wrong",scope="repository:home-assistant/home-assistant:pull"',
        'Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:other/repo:pull"',
        'Bearer realm="https://ghcr.io/token",realm="https://ghcr.io/token",service="ghcr.io",scope="repository:home-assistant/home-assistant:pull"',
        'Bearer realm="https://ghcr.io/token,service="ghcr.io",scope="repository:home-assistant/home-assistant:pull"',
        'Basic realm="https://ghcr.io/token"',
        'bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:home-assistant/home-assistant:pull"',
    ],
)
def test_challenge_rejections(value: str) -> None:
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        acquisition._challenge(value)
    assert caught.value.reason == acquisition._FailureReason.CHALLENGE_INVALID


def test_valid_challenge() -> None:
    acquisition._challenge(
        'Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:home-assistant/home-assistant:pull"'
    )


@pytest.mark.parametrize(
    "body",
    [
        b'{"token":"a","token":"b"}',
        b"{}",
        b'{"token":"a","access_token":"b"}',
        b'{"token":""}',
    ],
)
def test_invalid_token_json(body: bytes) -> None:
    fake = _FakeTransport([_challenge(), _response(200, body)])
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire())
    assert caught.value.reason == acquisition._FailureReason.TOKEN_RESPONSE_INVALID


def test_oversized_token_and_wrong_content_type() -> None:
    body = _json({"token": "x" * (acquisition._MAX_TOKEN_BYTES + 1)})
    for response in (
        _response(200, body),
        _response(200, b'{"token":"x"}', media="text/plain"),
    ):
        fake = _FakeTransport([_challenge(), response])
        with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
            asyncio.run(
                acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire()
            )
        assert caught.value.reason == acquisition._FailureReason.TOKEN_RESPONSE_INVALID


def test_redirect_is_refused() -> None:
    fake = _FakeTransport([_response(302)])
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire())
    assert caught.value.reason == acquisition._FailureReason.REDIRECT_REFUSED


@pytest.mark.parametrize(
    ("media", "digest", "body", "reason"),
    [
        ("application/vnd.oci.image.manifest.v1+json", "valid", None, "index_required"),
        (
            "application/vnd.docker.distribution.manifest.list.v2+json",
            "valid",
            None,
            "index_required",
        ),
        (acquisition._INDEX_MEDIA_TYPE, "", None, "digest_mismatch"),
        (acquisition._INDEX_MEDIA_TYPE, "sha256:ABC", None, "digest_mismatch"),
        (acquisition._INDEX_MEDIA_TYPE, "sha256:" + "0" * 64, None, "digest_mismatch"),
        (acquisition._INDEX_MEDIA_TYPE, "valid", b"{}", "index_required"),
    ],
)
def test_index_rejections(monkeypatch, media, digest, body, reason) -> None:
    index = body or _json(
        {
            "schemaVersion": 2,
            "mediaType": acquisition._INDEX_MEDIA_TYPE,
            "manifests": [],
        }
    )
    actual = _digest(index)
    monkeypatch.setattr(acquisition, "_EXPECTED_DIGEST", actual)
    response = _response(
        200,
        index,
        media=media,
        **{"docker-content-digest": actual if digest == "valid" else digest},
    )
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        acquisition._HomeAssistantGHCRAcquirer._validate_index(response)
    assert caught.value.reason.value == reason


def test_missing_sigstore_artifact(monkeypatch) -> None:
    fake, _, _ = _scenario(monkeypatch)
    fake.responses[3] = _response(
        200,
        _json({"schemaVersion": 2, "manifests": []}),
        media=acquisition._INDEX_MEDIA_TYPE,
    )
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire())
    assert caught.value.reason == acquisition._FailureReason.SIGNATURE_MATERIAL_MISSING


def test_unrelated_subject_is_rejected(monkeypatch) -> None:
    fake, _, _ = _scenario(monkeypatch)
    manifest_response = fake.responses[4]
    document = json.loads(manifest_response.body)
    document["subject"]["digest"] = "sha256:" + "0" * 64
    mutated = _json(document)
    # Update referrer integrity so failure is specifically subject association.
    refs = json.loads(fake.responses[3].body)
    refs["manifests"][0]["digest"] = _digest(mutated)
    refs["manifests"][0]["size"] = len(mutated)
    fake.responses[3] = _response(200, _json(refs), media=acquisition._INDEX_MEDIA_TYPE)
    fake.responses[4] = _response(200, mutated, media=acquisition._ARTIFACT_MEDIA_TYPE)
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire())
    assert caught.value.reason == acquisition._FailureReason.REFERRERS_INVALID


@pytest.mark.parametrize("mutation", ["digest", "size", "media", "shape"])
def test_bundle_integrity_and_structure(monkeypatch, mutation: str) -> None:
    fake, _, bundle = _scenario(monkeypatch)
    if mutation == "shape":
        malformed = _json(
            {"mediaType": acquisition._BUNDLE_MEDIA_TYPE, "dsseEnvelope": {}}
        )
        fake.responses[5] = _response(
            200, malformed, media=acquisition._BUNDLE_MEDIA_TYPE
        )
    elif mutation == "media":
        fake.responses[5] = _response(200, bundle, media="application/json")
    elif mutation == "digest":
        fake.responses[5] = _response(
            200, bundle + b" ", media=acquisition._BUNDLE_MEDIA_TYPE
        )
    else:
        fake.responses[5] = _response(
            200, bundle[:-1], media=acquisition._BUNDLE_MEDIA_TYPE
        )
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError):
        asyncio.run(acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire())


def test_tag_mutation_fails_closed(monkeypatch) -> None:
    fake, index, _ = _scenario(monkeypatch)
    final = index + b" "
    fake.responses[-1] = _response(
        200,
        final,
        media=acquisition._INDEX_MEDIA_TYPE,
        **{"docker-content-digest": _digest(final)},
    )
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire())
    assert caught.value.reason == acquisition._FailureReason.TAG_MUTATED


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fd00:ec2::254"]
)
def test_disallowed_dns(address: str) -> None:
    async def resolver(host: str, port: int):
        return [address]

    transport = acquisition._PinnedGHCRTransport(resolver=resolver)
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(
            transport.get(
                host="ghcr.io", path="/x", accept="application/json", max_body_bytes=10
            )
        )
    assert caught.value.reason == acquisition._FailureReason.DNS_DISALLOWED


def test_http_parser_rejects_duplicate_headers() -> None:
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError):
        acquisition._parse_http_headers(
            b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nContent-Length: 1\r\n\r\n"
        )


@pytest.mark.parametrize(
    "suffix",
    [
        ",",
        ",   ",
        ',,service="ghcr.io"',
        '\\"',
    ],
)
def test_challenge_strict_separator_and_escape_rejections(suffix: str) -> None:
    value = (
        'Bearer realm="https://ghcr.io/token",service="ghcr.io",'
        'scope="repository:home-assistant/home-assistant:pull"' + suffix
    )
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        acquisition._challenge(value)
    assert caught.value.reason == acquisition._FailureReason.CHALLENGE_INVALID


@pytest.mark.parametrize(
    "value",
    [
        'Bearer ,realm="https://ghcr.io/token"',
        'Bearer realm="https://ghcr.io/token",,service="ghcr.io"',
        'Bearer realm="https://ghcr.io/token\\x",service="ghcr.io",scope="repository:home-assistant/home-assistant:pull"',
        'Bearer realm="https://ghcr.io/token',
        'Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:home-assistant/home-assistant:pull",other="x"',
        'Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:home-assistant/home-assistant:pull", Basic realm="x"',
    ],
)
def test_challenge_additional_malformed_forms(value: str) -> None:
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        acquisition._challenge(value)
    assert caught.value.reason == acquisition._FailureReason.CHALLENGE_INVALID


@pytest.mark.parametrize(
    "block",
    [
        b"HTTP/1.1 200 OK\r\nBad Name: x\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nContent-Length : 0\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nBad\x01Name: x\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nB\xffd: x\r\n\r\n",
    ],
)
def test_http_parser_rejects_invalid_field_names(block: bytes) -> None:
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        acquisition._parse_http_headers(block)
    assert caught.value.reason == acquisition._FailureReason.HTTP_INVALID


@pytest.mark.parametrize("value", ["+1", "-1", " 1", "1 ", "", "1x", "\t1"])
def test_content_length_requires_ascii_decimal(value: str) -> None:
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(acquisition._read_body(None, {"content-length": value}, 10))
    assert caught.value.reason == acquisition._FailureReason.HTTP_INVALID


def test_content_length_limit_exact_boundary_and_one_over() -> None:
    async def run() -> None:
        exact = asyncio.StreamReader()
        exact.feed_data(b"abc")
        exact.feed_eof()
        assert await acquisition._read_body(exact, {"content-length": "3"}, 3) == b"abc"
        over = asyncio.StreamReader()
        over.feed_data(b"abcd")
        over.feed_eof()
        with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
            await acquisition._read_body(over, {"content-length": "4"}, 3)
        assert caught.value.reason == acquisition._FailureReason.RESPONSE_TOO_LARGE

    asyncio.run(run())


def test_declared_over_remaining_budget_rejected_before_read() -> None:
    class NeverRead:
        async def readexactly(self, size: int) -> bytes:
            raise AssertionError("body read started")

    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(
            acquisition._read_body(NeverRead(), {"content-length": "4194304"}, 1)
        )
    assert caught.value.reason == acquisition._FailureReason.RESPONSE_TOO_LARGE


def test_incomplete_body_is_not_exposed_raw() -> None:
    async def run() -> None:
        reader = asyncio.StreamReader()
        reader.feed_data(b"a")
        reader.feed_eof()
        with pytest.raises(asyncio.IncompleteReadError):
            await acquisition._read_body(reader, {"content-length": "2"}, 2)

    asyncio.run(run())


def test_deep_json_recursion_is_typed() -> None:
    body = (b'{"x":' * 10000) + b"0" + (b"}" * 10000)
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        acquisition._strict_object(body, acquisition._FailureReason.INDEX_REQUIRED)
    assert caught.value.reason == acquisition._FailureReason.INDEX_REQUIRED
    assert caught.value.__cause__ is None


@pytest.mark.parametrize("body", [b"\xff", b"{not-json"])
def test_remote_json_parser_failures_have_no_cause(body: bytes) -> None:
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        acquisition._strict_object(body, acquisition._FailureReason.INDEX_REQUIRED)
    assert caught.value.reason == acquisition._FailureReason.INDEX_REQUIRED
    assert caught.value.__cause__ is None


def test_malformed_remote_http_headers_have_no_cause() -> None:
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        acquisition._parse_http_headers(b"HTTP/1.1 nope OK\r\nRemote: secret\r\n\r\n")
    assert caught.value.reason == acquisition._FailureReason.HTTP_INVALID
    assert caught.value.__cause__ is None


def _bundle_document() -> dict[str, object]:
    return json.loads(
        (
            Path(__file__).parent
            / "testdata/home_assistant_sigstore/ha-2026.8.3-bundle.json"
        ).read_bytes()
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "payload_null",
        "payload_type_object",
        "signatures_string",
        "zero_signatures",
        "too_many_signatures",
        "bad_signature",
        "empty_certificate",
        "bad_certificate",
        "tlogs_string",
        "zero_tlogs",
        "too_many_tlogs",
        "bad_tlog",
        "bad_timestamp",
        "empty_inclusion_proof",
        "empty_inclusion_promise",
        "hashes_string",
        "malformed_hash",
        "too_many_hashes",
        "malformed_checkpoint",
        "malformed_timestamp_entry",
        "unexpected_top_level",
    ],
)
def test_strict_bundle_structural_rejections(mutation: str) -> None:
    value = _bundle_document()
    dsse = value["dsseEnvelope"]
    verification = value["verificationMaterial"]
    if mutation == "payload_null":
        dsse["payload"] = None
    elif mutation == "payload_type_object":
        dsse["payloadType"] = {}
    elif mutation == "signatures_string":
        dsse["signatures"] = "x"
    elif mutation == "zero_signatures":
        dsse["signatures"] = []
    elif mutation == "too_many_signatures":
        dsse["signatures"] = [{"sig": "x"}] * (acquisition._MAX_BUNDLE_ENTRIES + 1)
    elif mutation == "bad_signature":
        dsse["signatures"] = [{"sig": None}]
    elif mutation == "empty_certificate":
        verification["certificate"] = {"rawBytes": ""}
    elif mutation == "bad_certificate":
        verification["certificate"] = "x"
    elif mutation == "tlogs_string":
        verification["tlogEntries"] = "x"
    elif mutation == "zero_tlogs":
        verification["tlogEntries"] = []
    elif mutation == "too_many_tlogs":
        verification["tlogEntries"] *= acquisition._MAX_BUNDLE_ENTRIES + 1
    elif mutation == "bad_tlog":
        verification["tlogEntries"] = [{}]
    elif mutation == "bad_timestamp":
        verification["timestampVerificationData"] = []
    elif mutation == "empty_inclusion_proof":
        verification["tlogEntries"][0]["inclusionProof"] = {}
    elif mutation == "empty_inclusion_promise":
        verification["tlogEntries"][0]["inclusionPromise"] = {}
    elif mutation == "hashes_string":
        verification["tlogEntries"][0]["inclusionProof"]["hashes"] = "not-a-list"
    elif mutation == "malformed_hash":
        verification["tlogEntries"][0]["inclusionProof"]["hashes"] = [""]
    elif mutation == "too_many_hashes":
        verification["tlogEntries"][0]["inclusionProof"]["hashes"] = ["x"] * (
            acquisition._MAX_TLOG_HASHES + 1
        )
    elif mutation == "malformed_checkpoint":
        verification["tlogEntries"][0]["inclusionProof"]["checkpoint"] = []
    elif mutation == "malformed_timestamp_entry":
        verification["timestampVerificationData"] = {
            "rfc3161Timestamps": [{"signedTimestamp": []}]
        }
    else:
        value["unexpected"] = "field"
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        acquisition._bundle_shape(_json(value))
    assert caught.value.reason == acquisition._FailureReason.DESCRIPTOR_INVALID


def test_duplicate_selected_referrer_is_rejected(monkeypatch) -> None:
    fake, _, _ = _scenario(monkeypatch)
    refs = json.loads(fake.responses[3].body)
    refs["manifests"].append(dict(refs["manifests"][0]))
    fake.responses[3] = _response(200, _json(refs), media=acquisition._INDEX_MEDIA_TYPE)
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire())
    assert caught.value.reason == acquisition._FailureReason.DESCRIPTOR_INVALID


def test_conflicting_duplicate_selected_referrer_is_rejected(monkeypatch) -> None:
    fake, _, _ = _scenario(monkeypatch)
    refs = json.loads(fake.responses[3].body)
    duplicate = dict(refs["manifests"][0])
    duplicate["size"] += 1
    refs["manifests"].append(duplicate)
    fake.responses[3] = _response(200, _json(refs), media=acquisition._INDEX_MEDIA_TYPE)
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire())
    assert caught.value.reason == acquisition._FailureReason.DESCRIPTOR_INVALID


def _add_second_artifact(fake: _FakeTransport, index: bytes, bundle: bytes) -> bytes:
    second_bundle = bundle.rstrip() + b" "
    second_artifact = _json(
        {
            "schemaVersion": 2,
            "mediaType": acquisition._ARTIFACT_MEDIA_TYPE,
            "artifactType": acquisition._BUNDLE_MEDIA_TYPE,
            "subject": {
                "mediaType": acquisition._INDEX_MEDIA_TYPE,
                "digest": _digest(index),
                "size": len(index),
            },
            "layers": [
                {
                    "mediaType": acquisition._BUNDLE_MEDIA_TYPE,
                    "digest": _digest(second_bundle),
                    "size": len(second_bundle),
                }
            ],
        }
    )
    first_artifact = fake.responses[4].body
    refs = json.loads(fake.responses[3].body)
    refs["manifests"].append(
        {
            "mediaType": acquisition._ARTIFACT_MEDIA_TYPE,
            "digest": _digest(second_artifact),
            "size": len(second_artifact),
            "artifactType": acquisition._BUNDLE_MEDIA_TYPE,
        }
    )
    prefix = list(fake.responses)[:3]
    ref_response = _response(200, _json(refs), media=acquisition._INDEX_MEDIA_TYPE)
    artifacts = {
        _digest(first_artifact): (first_artifact, bundle),
        _digest(second_artifact): (second_artifact, second_bundle),
    }
    acquired = []
    for digest in sorted(artifacts):
        artifact, material = artifacts[digest]
        acquired.extend(
            [
                _response(200, artifact, media=acquisition._ARTIFACT_MEDIA_TYPE),
                _response(200, material, media=acquisition._BUNDLE_MEDIA_TYPE),
            ]
        )
    fake.responses = deque(prefix + [ref_response] + acquired + [fake.responses[-1]])
    return second_bundle


def test_distinct_artifacts_are_deterministically_ordered(monkeypatch) -> None:
    fake, index, bundle = _scenario(monkeypatch)
    second = _add_second_artifact(fake, index, bundle)
    result = asyncio.run(
        acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire()
    )
    assert result.sigstore_bundles == tuple(
        body
        for _, body in sorted([(_digest(bundle), bundle), (_digest(second), second)])
    )


@pytest.mark.parametrize("otherwise_valid_index", [False, True])
def test_final_mutation_after_multiple_artifacts_fails(
    monkeypatch, otherwise_valid_index: bool
) -> None:
    fake, index, bundle = _scenario(monkeypatch)
    _add_second_artifact(fake, index, bundle)
    if otherwise_valid_index:
        document = json.loads(index)
        document["manifests"][0]["size"] += 1
        final = _json(document)
    else:
        final = index + b" "
    fake.responses[-1] = _response(
        200,
        final,
        media=acquisition._INDEX_MEDIA_TYPE,
        **{"docker-content-digest": _digest(final)},
    )
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire())
    assert caught.value.reason == acquisition._FailureReason.TAG_MUTATED


def test_acquisition_deadline_is_global_and_stops_new_requests(monkeypatch) -> None:
    class SlowTransport(_FakeTransport):
        async def get(self, **kwargs) -> acquisition._Response:
            self.calls.append(kwargs)
            await asyncio.sleep(0.012)
            if not self.responses:
                raise AssertionError("unexpected request")
            return self.responses.popleft()

    base, _, _ = _scenario(monkeypatch)
    slow = SlowTransport(list(base.responses))
    monkeypatch.setattr(acquisition, "_TOTAL_TIMEOUT", 0.025)
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(acquisition._HomeAssistantGHCRAcquirer(transport=slow).acquire())
    assert caught.value.reason == acquisition._FailureReason.TIMEOUT
    assert len(slow.calls) == 3
    assert slow.calls[1]["timeout"] < slow.calls[0]["timeout"]
    assert slow.calls[2]["timeout"] < slow.calls[1]["timeout"]


def test_absolute_deadline_cancels_transport_ignoring_timeout(monkeypatch) -> None:
    class IgnoringTransport:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def get(self, **kwargs) -> acquisition._Response:
            self.calls.append(kwargs)
            await asyncio.sleep(60)
            raise AssertionError("outer deadline did not cancel transport")

    transport = IgnoringTransport()
    monkeypatch.setattr(acquisition, "_TOTAL_TIMEOUT", 0.02)
    started = time.monotonic()
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(
            acquisition._HomeAssistantGHCRAcquirer(transport=transport).acquire()
        )
    elapsed = time.monotonic() - started
    assert caught.value.reason == acquisition._FailureReason.TIMEOUT
    assert caught.value.__cause__ is None
    assert len(transport.calls) == 1
    assert elapsed < 1


def test_hard_cumulative_limit_is_passed_to_transport(monkeypatch) -> None:
    fake, _, _ = _scenario(monkeypatch)
    first_size = len(fake.responses[0].body)
    token_size = len(fake.responses[1].body)
    monkeypatch.setattr(acquisition, "_MAX_TOTAL_BYTES", first_size + token_size)
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire())
    assert caught.value.reason == acquisition._FailureReason.RESPONSE_TOO_LARGE
    assert fake.calls[2]["max_body_bytes"] == 0


def test_transport_cannot_return_one_byte_over_cumulative_limit(monkeypatch) -> None:
    response = _challenge()
    fake = _FakeTransport(
        [acquisition._Response(response.status, response.headers, b"x")]
    )
    monkeypatch.setattr(acquisition, "_MAX_TOTAL_BYTES", 0)
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(acquisition._HomeAssistantGHCRAcquirer(transport=fake).acquire())
    assert caught.value.reason == acquisition._FailureReason.RESPONSE_TOO_LARGE


def test_exact_cumulative_boundary_succeeds() -> None:
    async def run() -> None:
        fake = _FakeTransport([_response(200, b"abc")])
        acquirer = acquisition._HomeAssistantGHCRAcquirer(transport=fake)
        loop = asyncio.get_running_loop()
        budget = acquisition._AcquisitionBudget(
            loop.time() + 1, acquisition._MAX_TOTAL_BYTES - 3
        )
        response = await acquirer._request(
            budget,
            host="ghcr.io",
            path="/x",
            accept="application/json",
            object_limit=10,
        )
        assert response.body == b"abc"
        assert budget.received == acquisition._MAX_TOTAL_BYTES
        assert fake.calls[0]["max_body_bytes"] == 3

    asyncio.run(run())


@pytest.mark.parametrize(
    "addresses",
    [[], ["8.8.8.8", "10.0.0.1"], ["::ffff:10.0.0.1"]],
)
def test_dns_answer_set_fail_closed(addresses: list[str]) -> None:
    async def resolver(host: str, port: int) -> list[str]:
        return addresses

    transport = acquisition._PinnedGHCRTransport(resolver=resolver)
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(
            transport.get(
                host="ghcr.io",
                path="/x",
                accept="application/json",
                max_body_bytes=1,
            )
        )
    assert caught.value.reason == acquisition._FailureReason.DNS_DISALLOWED


class _SocketWriter:
    def __init__(self, *, drain_error: Exception | None = None) -> None:
        self.drain_error = drain_error
        self.request = b""

    def write(self, value: bytes) -> None:
        self.request += value

    async def drain(self) -> None:
        if self.drain_error:
            raise self.drain_error

    def close(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass


def test_validated_ip_is_connected_with_ghcr_tls_sni(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def resolver(host: str, port: int) -> list[str]:
        return ["8.8.8.8"]

    async def open_connection(**kwargs):
        captured.update(kwargs)
        reader = asyncio.StreamReader()
        reader.feed_data(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
        reader.feed_eof()
        return reader, _SocketWriter()

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    result = asyncio.run(
        acquisition._PinnedGHCRTransport(resolver=resolver).get(
            host="ghcr.io",
            path="/x",
            accept="application/json",
            max_body_bytes=0,
        )
    )
    assert result.status == 200
    assert captured["host"] == "8.8.8.8"
    assert captured["server_hostname"] == "ghcr.io"


def test_socket_failure_is_typed_and_token_is_not_chained(monkeypatch) -> None:
    token = "top-secret-token"

    async def resolver(host: str, port: int) -> list[str]:
        return ["8.8.8.8"]

    async def open_connection(**kwargs):
        return asyncio.StreamReader(), _SocketWriter(drain_error=OSError(token))

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(
            acquisition._PinnedGHCRTransport(resolver=resolver).get(
                host="ghcr.io",
                path="/x",
                accept="application/json",
                authorization=f"Bearer {token}",
                max_body_bytes=1,
            )
        )
    assert caught.value.reason == acquisition._FailureReason.CONNECTION_FAILED
    assert token not in str(caught.value)
    assert token not in repr(caught.value)
    assert caught.value.__cause__ is None


def test_transport_incomplete_body_is_typed(monkeypatch) -> None:
    async def resolver(host: str, port: int) -> list[str]:
        return ["8.8.8.8"]

    async def open_connection(**kwargs):
        reader = asyncio.StreamReader()
        reader.feed_data(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\na")
        reader.feed_eof()
        return reader, _SocketWriter()

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(
            acquisition._PinnedGHCRTransport(resolver=resolver).get(
                host="ghcr.io", path="/x", accept="application/json", max_body_bytes=2
            )
        )
    assert caught.value.reason == acquisition._FailureReason.CONNECTION_FAILED


@pytest.mark.parametrize("failure", [OSError("socket"), ssl.SSLError("tls")])
def test_connection_and_tls_failures_are_typed(monkeypatch, failure: Exception) -> None:
    async def resolver(host: str, port: int) -> list[str]:
        return ["8.8.8.8"]

    async def open_connection(**kwargs):
        raise failure

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(
            acquisition._PinnedGHCRTransport(resolver=resolver).get(
                host="ghcr.io", path="/x", accept="application/json", max_body_bytes=0
            )
        )
    assert caught.value.reason == acquisition._FailureReason.CONNECTION_FAILED
    assert caught.value.__cause__ is None


def test_transport_parser_failure_is_typed(monkeypatch) -> None:
    async def resolver(host: str, port: int) -> list[str]:
        return ["8.8.8.8"]

    async def open_connection(**kwargs):
        reader = asyncio.StreamReader()
        reader.feed_data(b"NOT HTTP\r\nContent-Length: 0\r\n\r\n")
        reader.feed_eof()
        return reader, _SocketWriter()

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
        asyncio.run(
            acquisition._PinnedGHCRTransport(resolver=resolver).get(
                host="ghcr.io", path="/x", accept="application/json", max_body_bytes=0
            )
        )
    assert caught.value.reason == acquisition._FailureReason.HTTP_INVALID


@pytest.mark.parametrize("extra", [0, 1])
def test_maximum_header_boundary(monkeypatch, extra: int) -> None:
    async def resolver(host: str, port: int) -> list[str]:
        return ["8.8.8.8"]

    base = b"HTTP/1.1 200 OK\r\nX:\r\nContent-Length: 0\r\n"
    padding = b"a" * (acquisition._MAX_HEADER_BYTES - len(base) - 2 + extra)
    prefix = b"HTTP/1.1 200 OK\r\nX:" + padding + b"\r\nContent-Length: 0\r\n"

    async def open_connection(**kwargs):
        reader = asyncio.StreamReader(limit=kwargs["limit"])
        reader.feed_data(prefix + b"\r\n")
        reader.feed_eof()
        return reader, _SocketWriter()

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    transport = acquisition._PinnedGHCRTransport(resolver=resolver)
    if extra:
        with pytest.raises(acquisition._HomeAssistantGHCRAcquisitionError) as caught:
            asyncio.run(
                transport.get(
                    host="ghcr.io",
                    path="/x",
                    accept="application/json",
                    max_body_bytes=0,
                )
            )
        assert caught.value.reason == acquisition._FailureReason.HTTP_INVALID
    else:
        response = asyncio.run(
            transport.get(
                host="ghcr.io",
                path="/x",
                accept="application/json",
                max_body_bytes=0,
            )
        )
        assert response.body == b""
