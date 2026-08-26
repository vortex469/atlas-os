"""Pure deterministic InstallationPlan v1 evaluator."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from itertools import combinations

from app.discovery.models import CatalogEntry
from app.installation_plan.adapters import (
    ArtifactObservation,
    CatalogSnapshot,
    CompatibilityAdapterInput,
)
from app.installation_plan.contract import (
    AbsenceFactInputV1,
    AbsenceIdentityInputV1,
    Application,
    ApplicationDecisionInputV1,
    ArtifactAbsentIdentityInputV1,
    ArtifactContentIdentityInputV1,
    ArtifactDecisionInputV1,
    ArtifactRejectedIdentityInputV1,
    ArtifactUnboundIdentityInputV1,
    Assumption,
    AssumptionDecisionInputV1,
    AssumptionIdentityInputV1,
    BindingAbsentIdentityInputV1,
    BindingDecisionInputV1,
    BindingIdentityInputV1,
    Blocker,
    BlockerDecisionInputV1,
    CatalogDecisionFingerprintInputV1,
    CatalogDecisionInputV1,
    CatalogSourceIdentityInputV1,
    Compatibility,
    CompatibilityAbsentInputV1,
    CompatibilityDecisionInputV1,
    CompatibilityEvaluatorIdentityInputV1,
    CompatibilityReleasedInputV1,
    Confirmation,
    ConfirmationDecisionInputV1,
    ConflictFactInputV1,
    DeploymentArtifact,
    Evidence,
    EvidenceDecisionInput,
    EvidenceIdInputV1,
    EvidenceImmutableIdentityInputV1,
    FingerprintInputV1,
    FreshnessDecisionInputV1,
    FreshnessIdentityInputV1,
    FreshnessPolicyIdentityInputV1,
    Image,
    ImageDecisionInputV1,
    InstallationPlan,
    MissingFact,
    MissingFactDecisionInputV1,
    Prerequisite,
    PrerequisiteDecisionInputV1,
    PrerequisiteDescriptorInputV1,
    PrerequisiteIdentityInputV1,
    Provenance,
    ProvenanceDecisionInputV1,
    RawEvidenceObservation,
    Relationship,
    RelationshipDecisionInputV1,
    RequirementDecisionInputV1,
    RequirementPortDecisionInputV1,
    Risk,
    RiskDecisionInputV1,
    SourceUnavailableFactInputV1,
    SourceUnavailableIdentityInputV1,
    canonical_json,
    compound_hash,
    fingerprint,
    version_components,
)

_WINDOWS = {
    "curated": 31536000,
    "registry_attested": 2592000,
    "upstream_signed": 604800,
}
_BLOCKER_ORDER = [
    "missing_deployment_binding",
    "missing_deployment_artifact",
    "invalid_deployment_artifact",
    "unsafe_deployment_artifact",
    "unknown_deployment_artifact",
    "missing_immutable_image_identity",
    "mutable_image_reference",
    "untrusted_evidence",
    "image_conflict",
    "image_mismatch",
    "unknown_image_state",
    "missing_accepted_evidence",
    "stale_evidence",
    "malformed_evidence",
    "provenance_conflict",
    "incompatible_application_environment",
    "unknown_compatibility",
    "missing_prerequisite",
    "missing_prerequisite_fact",
    "missing_target_identity",
    "required_operator_confirmation",
    "malformed_source_fact",
]
_RELATIONSHIP_ORDER = [
    "depends_on", "provides", "consumes", "requires", "integrates_with",
    "conflicts_with", "runs_on", "deployed_by", "compatible_with",
    "incompatible_with",
]
_PROVENANCE_SOURCE_ORDER = [
    "curated_catalog", "deployment_binding", "repository_observation",
    "image_release_evidence", "compatibility_evaluation", "prerequisite_source",
    "policy_evaluation",
]
_EVIDENCE_DISPOSITION_ORDER = [
    "accepted", "missing", "untrusted", "unsupported", "malformed", "unavailable",
    "conflicted", "mismatched",
]
_EVIDENCE_REASON_ORDER = [
    "accepted_fresh", "accepted_stale", "record_missing", "source_class_untrusted",
    "source_class_unsupported", "record_malformed", "timestamp_malformed",
    "digest_or_identity_malformed", "accepted_claim_conflict",
    "immutable_identity_conflict", "release_identity_mismatch", "source_unavailable",
]
_MISSING_FACT_ORDER = [
    "deployment_binding", "deployment_artifact", "immutable_image_identity",
    "accepted_evidence", "prerequisite_fact", "target_identity",
    "compatibility_fact", "source_fact",
]
_RISK_ORDER = ["evidence_approaching_expiry", "compatibility_warning"]
_ABSENCE_ORDER = [
    "deployment_binding", "deployment_artifact", "evidence_record",
    "compatibility_fact", "prerequisite_fact",
]
_CONFLICT_ORDER = ["image_claim", "provenance_identity", "immutable_identity"]


def _utc(value: datetime | str) -> str:
    if isinstance(value, str):
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        return value
    if value.tzinfo is None or value.utcoffset() is None or value.microsecond:
        raise ValueError("evaluation instant must be aware and whole-second")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _seconds(value: str) -> int:
    return int(
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp()
    )


def _decimal(value: float | None) -> str | None:
    if value is None:
        return None
    result = format(Decimal(str(value)).normalize(), "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def _release(entry: CatalogEntry) -> str | None:
    claim, item_version = entry.release_claim, entry.item.version
    if claim is not None and item_version is not None and claim.version != item_version:
        raise ValueError("catalog release conflict")
    return claim.version if claim is not None else item_version


def _evidence_immutable_identity(value: EvidenceImmutableIdentityInputV1) -> str:
    """Derive an evidence-row identity at the narrow collision boundary."""
    return compound_hash("atlas:image-evidence-row:v1", value)


def _plan_status(blocker_codes: set[str]) -> str:
    if blocker_codes & {"provenance_conflict", "image_conflict"}:
        return "conflicted"
    if "missing_deployment_artifact" in blocker_codes:
        return "missing_deployment_artifact"
    if "incompatible_application_environment" in blocker_codes:
        return "incompatible"
    if "stale_evidence" in blocker_codes:
        return "stale_evidence"
    if blocker_codes:
        return "insufficient_information"
    return "plan_ready_for_review"


def _catalog(snapshot: CatalogSnapshot) -> tuple[CatalogDecisionInputV1, str, str]:
    record, entry = snapshot.selected, snapshot.selected.entry
    if (
        entry.provenance.entry_id is None
        or entry.provenance.source_type.value != "curated"
        or entry.provenance.trust_level.value != "curated"
    ):
        raise ValueError("catalog provenance policy failure")
    requirements = entry.item.requirements
    relationships = tuple(
        sorted(
            (
                RelationshipDecisionInputV1(
                    kind=rel.type.value, item_id=rel.target, required=rel.required,
                    minimum_version=rel.minimum_version,
                    maximum_version=rel.maximum_version,
                )
                for rel in entry.item.relationships
            ),
            key=lambda x: (
                _RELATIONSHIP_ORDER.index(x.kind), x.item_id, x.required,
                x.minimum_version or "", x.maximum_version or "",
            ),
        )
    )
    ports = tuple(
        sorted(
            (
                RequirementPortDecisionInputV1(
                    port=p.port, protocol=p.protocol,
                    direction=p.direction, required=p.required,
                )
                for p in requirements.network.ports
            ),
            key=lambda x: (x.port, x.protocol, x.direction, x.required),
        )
    )
    binding = (
        None
        if entry.deployment_binding is None
        else {
            "kind": "docker-compose",
            "repository_path": entry.deployment_binding.compose_file,
            "service": entry.deployment_binding.compose_service,
        }
    )
    claim = (
        None
        if entry.release_claim is None
        else {
            "version": entry.release_claim.version,
            "published_at": entry.release_claim.published_at.astimezone(UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        }
    )
    decision = CatalogDecisionInputV1(
        schema_version=1, catalog_entry_id=entry.provenance.entry_id,
        item_id=entry.item.id, item_type=entry.item.type.value,
        item_status=entry.item.status.value, item_version=entry.item.version,
        release_claim=claim, release_version=_release(entry),
        provenance_source_type=entry.provenance.source_type.value,
        provenance_source_id=entry.provenance.source,
        provenance_entry_id=entry.provenance.entry_id,
        provenance_version=entry.provenance.version,
        provenance_trust_level=entry.provenance.trust_level.value,
        deployment_binding=binding,
        requirements=RequirementDecisionInputV1(
            capability_ids=tuple(sorted(c.id for c in requirements.capabilities)),
            cpu_cores_min=_decimal(requirements.resources.cpu_cores_min),
            memory_mb_min=requirements.resources.memory_mb_min,
            storage_gb_min=_decimal(requirements.resources.storage_gb_min),
            gpu_required=requirements.resources.gpu_required,
            gpu_memory_gb_min=_decimal(requirements.resources.gpu_memory_gb_min),
            architectures=tuple(sorted(requirements.platform.architectures)),
            operating_systems=tuple(sorted(requirements.platform.operating_systems)),
            runtimes=tuple(sorted(requirements.platform.runtimes)),
            devices=tuple(sorted(requirements.platform.devices)),
            ports=ports,
            requires_internet=requirements.network.requires_internet,
            requires_lan=requirements.network.requires_lan,
        ), relationships=relationships,
        reviewed_content_digest=record.reviewed_content_digest,
    )
    source_input = CatalogSourceIdentityInputV1(
        catalog_entry_id=decision.catalog_entry_id, item_id=decision.item_id,
        provenance_source_type=decision.provenance_source_type,
        provenance_source_id=decision.provenance_source_id,
        provenance_entry_id=decision.provenance_entry_id,
        provenance_version=decision.provenance_version,
        reviewed_content_digest=decision.reviewed_content_digest,
    )
    return (
        decision,
        compound_hash("atlas:catalog-decision:v1", decision),
        compound_hash("atlas:catalog-source:v1", source_input),
    )


def _prerequisites(
    catalog: CatalogDecisionInputV1, snapshot: CatalogSnapshot, catalog_identity: str
) -> tuple[list[Prerequisite], list[PrerequisiteDecisionInputV1], list[Provenance]]:
    rows: list[tuple[str, str, RelationshipDecisionInputV1 | None]] = []
    req = catalog.requirements
    if req.cpu_cores_min is not None:
        rows.append(("platform", f"cpu:{req.cpu_cores_min}", None))
    if req.memory_mb_min is not None:
        rows.append(("platform", f"memory-mb:{req.memory_mb_min}", None))
    if req.storage_gb_min is not None:
        rows.append(("storage", f"storage-gb:{req.storage_gb_min}", None))
    if req.gpu_required:
        rows.append(("platform", "gpu-required", None))
    if req.gpu_memory_gb_min is not None:
        rows.append(("platform", f"gpu-memory-gb:{req.gpu_memory_gb_min}", None))
    for values, prefix in (
        (req.capability_ids, "capability"),
        (req.architectures, "architecture"),
        (req.operating_systems, "operating-system"),
        (req.runtimes, "runtime"),
        (req.devices, "device"),
    ):
        rows.extend(("platform", f"{prefix}:{value}", None) for value in values)
    for p in req.ports:
        rows.append(
            (
                "network",
                f"port:{p.port}:{p.protocol}:{p.direction}:{str(p.required).lower()}",
                None,
            )
        )
    if req.requires_internet:
        rows.append(("network", "internet-required", None))
    if req.requires_lan:
        rows.append(("network", "lan-required", None))
    for rel in catalog.relationships:
        if rel.required and rel.kind in {
            "depends_on",
            "requires",
            "runs_on",
            "deployed_by",
        }:
            rows.append(("application", "relationship", rel))
    index = {r.entry.item.id: r.entry for r in snapshot.records}
    public = []
    decisions = []
    provenance = []
    for kind, key, rel in rows:
        descriptor = PrerequisiteDescriptorInputV1(
            kind=kind, requirement_key=key, relationship=rel
        )
        pid = compound_hash("atlas:prerequisite-id:v1", descriptor)
        state = "unknown"
        if kind == "application":
            target = index.get(rel.item_id)
            if target is None or target.item.status.value != "active":
                state = "missing"
            else:
                version = _release(target)
                if version is None and (
                    rel.minimum_version or rel.maximum_version
                ):
                    state = "unknown"
                elif (
                    rel.minimum_version
                    and version_components(version)
                    < version_components(rel.minimum_version)
                ) or (
                    rel.maximum_version
                    and version_components(version)
                    > version_components(rel.maximum_version)
                ):
                    state = "missing"
                else:
                    state = "satisfied"
        if rel:
            desc = f"Requires application relationship {rel.kind} with item {rel.item_id}; minimum version {rel.minimum_version or 'none'}; maximum version {rel.maximum_version or 'none'}."
        elif key.startswith("cpu:"):
            desc = f"Requires at least {key[4:]} CPU cores."
        elif key.startswith("memory-mb:"):
            desc = f"Requires at least {key[10:]} MB memory."
        elif key.startswith("storage-gb:"):
            desc = f"Requires at least {key[11:]} GB storage."
        elif key == "gpu-required":
            desc = "Requires a GPU."
        elif key.startswith("gpu-memory-gb:"):
            desc = f"Requires at least {key[14:]} GB GPU memory."
        elif key.startswith("port:"):
            _, port, protocol, direction, required = key.split(":")
            desc = f"Requires port {port}/{protocol} in the {direction} direction (required: {required})."
        elif key == "internet-required":
            desc = "Requires internet access."
        elif key == "lan-required":
            desc = "Requires LAN access."
        else:
            prefix, value = key.split(":", 1)
            labels = {
                "capability": "capability",
                "architecture": "architecture",
                "operating-system": "operating system",
                "runtime": "runtime",
                "device": "device",
            }
            desc = f"Requires {labels[prefix]} {value}."
        decision = PrerequisiteDecisionInputV1(
            prerequisite_id=pid, kind=kind, state=state, descriptor=descriptor
        )
        identity = compound_hash(
            "atlas:prerequisite:v1",
            PrerequisiteIdentityInputV1(
                descriptor=descriptor, prerequisite=decision,
                catalog_identity=catalog_identity,
            ),
        )
        public.append(
            Prerequisite(prerequisite_id=pid, kind=kind, state=state, description=desc)
        )
        decisions.append(decision)
        provenance.append(
            Provenance(
                claim="prerequisite",
                source_class="prerequisite_source",
                source_id="prerequisite-projector",
                immutable_identity=identity,
                observed_at=None,
                attested_at=None,
            )
        )
    order = sorted(
        range(len(public)),
        key=lambda i: (public[i].prerequisite_id, public[i].kind, public[i].state),
    )
    return (
        [public[i] for i in order],
        [decisions[i] for i in order],
        [provenance[i] for i in order],
    )


class InstallationPlanAssembler:
    def assemble(
        self,
        *,
        catalog: CatalogSnapshot,
        artifact_observation: ArtifactObservation,
        evidence_observations: Iterable[RawEvidenceObservation],
        evaluation_instant: datetime | str,
        compatibility_observation: CompatibilityAdapterInput | None = None,
    ) -> InstallationPlan:
        instant = _utc(evaluation_instant)
        catalog_model, catalog_identity, catalog_source_identity = _catalog(catalog)
        entry = catalog.selected.entry
        item = catalog_model.item_id
        release = catalog_model.release_version
        policy_identity = compound_hash(
            "atlas:image-evidence-freshness-policy:v1",
            FreshnessPolicyIdentityInputV1(),
        )
        binding_value = catalog_model.deployment_binding
        if binding_value is None:
            binding = BindingDecisionInputV1(
                state="absent", repository_path=None, service=None,
                identity=compound_hash(
                    "atlas:binding-absent:v1",
                    BindingAbsentIdentityInputV1(
                        catalog_entry_id=catalog_model.catalog_entry_id
                    ),
                ),
            )
        else:
            binding = BindingDecisionInputV1(
                state="present", repository_path=binding_value.repository_path,
                service=binding_value.service, identity=compound_hash(
                    "atlas:binding:v1",
                    BindingIdentityInputV1(
                        catalog_entry_id=catalog_model.catalog_entry_id,
                        binding=binding_value,
                    ),
                ),
            )
        obs = artifact_observation
        if binding.state == "absent":
            artifact = ArtifactDecisionInputV1(
                state="unknown", repository_path=None, service=None,
                content_digest=None, reason_code="observation_unknown",
                identity=compound_hash(
                    "atlas:artifact-unbound:v1",
                    ArtifactUnboundIdentityInputV1(
                        catalog_entry_id=catalog_model.catalog_entry_id
                    ),
                ),
            )
        else:
            if obs.state == "present":
                domain = "atlas:artifact-content:v1"
                identity_input = ArtifactContentIdentityInputV1(
                    repository_path=obs.repository_path,
                    service=obs.service,
                    content_digest=obs.content_digest,
                )
            elif obs.state == "missing":
                domain = "atlas:artifact-absent:v1"
                identity_input = ArtifactAbsentIdentityInputV1(
                    repository_path=obs.repository_path,
                    service=obs.service,
                )
            else:
                domain = "atlas:artifact-rejected:v1"
                identity_input = ArtifactRejectedIdentityInputV1(
                    repository_path=obs.repository_path, service=obs.service,
                    state=obs.state, reason_code=obs.reason_code,
                )
            artifact = ArtifactDecisionInputV1(
                state=obs.state, repository_path=obs.repository_path,
                service=obs.service, content_digest=obs.content_digest,
                reason_code=obs.reason_code,
                identity=compound_hash(domain, identity_input),
            )
        provenance = [
            Provenance(
                claim="catalog_entry",
                source_class="curated_catalog",
                source_id=catalog_model.provenance_source_id,
                immutable_identity=catalog_source_identity,
                observed_at=None,
                attested_at=catalog_model.release_claim.published_at
                if catalog_model.release_claim
                else None,
            ),
            Provenance(
                claim="deployment_binding",
                source_class="deployment_binding",
                source_id="deployment-binding",
                immutable_identity=binding.identity,
                observed_at=None,
                attested_at=None,
            ),
            Provenance(
                claim="deployment_artifact",
                source_class="repository_observation",
                source_id="repository-observer",
                immutable_identity=artifact.identity,
                observed_at=None,
                attested_at=None,
            ),
        ]
        evidence_decisions = []
        accepted = []
        freshness = []
        conflicts = []
        absence = []
        unavailable = []

        def add_absence(kind: str, subject: str, source_id: str) -> None:
            identity_input = AbsenceIdentityInputV1(
                kind=kind, subject=subject, source_id=source_id
            )
            absence.append(AbsenceFactInputV1(
                kind=identity_input.kind, subject=subject, source_id=source_id,
                identity=compound_hash("atlas:absence-fact:v1", identity_input),
                )
            )

        if binding.state == "absent":
            add_absence(
                "deployment_binding",
                catalog_model.catalog_entry_id,
                "deployment-binding",
            )
        if artifact.state == "missing":
            add_absence(
                "deployment_artifact", artifact.service, "repository-observer"
            )
        raw_by_identity = {
            canonical_json(row): row for row in evidence_observations
        }
        raw = [raw_by_identity[key] for key in sorted(raw_by_identity)]
        if len(raw) > 128:
            raise ValueError("evidence cardinality")
        derived: dict[bytes, tuple[EvidenceImmutableIdentityInputV1, str, str]] = {}
        identities: dict[str, set[bytes]] = {}
        for row in raw:
            source_class = row.source_class
            if (
                source_class in _WINDOWS
                and all(
                    value is not None
                    for value in (
                        row.subject, row.release_version, row.image_reference,
                        row.image_digest, row.released_source_id, row.attested_at,
                    )
                )
            ):
                identity_input = EvidenceImmutableIdentityInputV1(
                    catalog_item_id=row.subject, release_version=row.release_version,
                    image_reference=row.image_reference, image_digest=row.image_digest,
                    source_class=source_class, source_id=row.released_source_id,
                    attested_at=row.attested_at,
                )
                immutable = _evidence_immutable_identity(identity_input)
                evidence_id = compound_hash(
                    "atlas:image-evidence-id:v1",
                    EvidenceIdInputV1(source_class=source_class,
                        source_id=row.released_source_id,
                        immutable_identity=immutable),
                )
                key = canonical_json(row)
                derived[key] = (identity_input, immutable, evidence_id)
                identities.setdefault(immutable, set()).add(canonical_json(identity_input))
        collision_identities = {
            identity for identity, inputs in identities.items() if len(inputs) > 1
        }
        present = []
        for row in raw:
            source_class = row.source_class or "unknown"
            window = _WINDOWS.get(source_class)
            immutable = eid = None
            derived_row = derived.get(canonical_json(row))
            if derived_row is not None:
                _, immutable, eid = derived_row
            mapping = {
                "absent": ("missing", "record_missing"),
                "parse_failure": ("malformed", "record_malformed"),
                "schema_failure": ("malformed", "record_malformed"),
                "missing_required_field": ("malformed", "record_malformed"),
                "unsupported_source_class": ("unsupported", "source_class_unsupported"),
                "malformed_timestamp": ("malformed", "timestamp_malformed"),
                "malformed_identity": ("malformed", "digest_or_identity_malformed"),
                "malformed_digest": ("malformed", "digest_or_identity_malformed"),
                "source_unavailable": ("unavailable", "source_unavailable"),
            }
            future_invalid = False
            if row.observation_kind != "present":
                disposition, reason = mapping[row.observation_kind]
                if row.observation_kind == "absent":
                    add_absence("evidence_record", item, row.expected_source_id)
                elif row.observation_kind == "source_unavailable":
                    unavailable_input = SourceUnavailableIdentityInputV1(
                        subject=item, expected_source_id=row.expected_source_id
                    )
                    unavailable.append(SourceUnavailableFactInputV1(
                            subject=item,
                            expected_source_id=row.expected_source_id,
                            identity=compound_hash(
                                "atlas:optional-source-unavailable:v1",
                                unavailable_input,
                            ),
                        ))
            elif row.attested_at is not None and _seconds(instant) - _seconds(row.attested_at) < -300:
                disposition, reason = "malformed", "timestamp_malformed"
                future_invalid = True
            elif immutable in collision_identities:
                disposition, reason = "conflicted", "immutable_identity_conflict"
            elif source_class == "upstream_signed":
                disposition, reason = "untrusted", "source_class_untrusted"
            elif (
                row.subject != item
                or row.release_version != release
                or (obs.image_reference and row.image_reference != obs.image_reference)
                or (obs.image_digest and row.image_digest != obs.image_digest)
            ):
                disposition, reason = "mismatched", "release_identity_mismatch"
            else:
                disposition = reason = "pending"
                present.append((row, immutable, eid, window))
            if disposition != "pending":
                decision = EvidenceDecisionInput(
                    expected_source_id=row.expected_source_id,
                    source_class=source_class,
                    subject=row.subject,
                    release_version=row.release_version,
                    image_reference=row.image_reference,
                    image_digest=row.image_digest,
                    source_id=row.released_source_id,
                    immutable_identity=immutable,
                    evidence_id=eid,
                    attested_at=row.attested_at,
                    freshness_window_seconds=(window if row.attested_at else None),
                    disposition=disposition,
                    eligibility="ineligible",
                    reason_code=reason,
                )
                evidence_decisions.append(decision)
                if (
                    row.observation_kind == "present"
                    and immutable is not None
                    and window is not None
                    and row.attested_at is not None
                    and not future_invalid
                ):
                    age = max(0, _seconds(instant) - _seconds(row.attested_at))
                    freshness.append(FreshnessDecisionInputV1(
                        evidence_identity=immutable, effective_time=row.attested_at,
                        window_seconds=window, age_seconds=age,
                        result="fresh" if age <= window else "stale",
                    ))
                provenance.append(
                    Provenance(
                        claim="immutable_image_release",
                        source_class="image_release_evidence",
                        source_id=row.released_source_id or row.expected_source_id,
                        immutable_identity=compound_hash(
                            "atlas:evidence-decision:v1", decision
                        ),
                        observed_at=None,
                        attested_at=row.attested_at,
                    )
                )
        collision_decisions = [
            decision for decision in evidence_decisions
            if decision.reason_code == "immutable_identity_conflict"
        ]
        for left, right in combinations(collision_decisions, 2):
            if left.immutable_identity == right.immutable_identity and canonical_json(left) != canonical_json(right):
                sides = sorted((
                    compound_hash("atlas:evidence-decision:v1", left),
                    compound_hash("atlas:evidence-decision:v1", right),
                ))
                conflicts.append(ConflictFactInputV1(
                    kind="immutable_identity", subject=left.subject,
                    left_identity=sides[0], right_identity=sides[1],
                ))
        conflicting: set[str] = set()
        for left, right in combinations(present, 2):
            if (
                left[0].subject == right[0].subject
                and left[0].release_version == right[0].release_version
                and (left[0].image_reference, left[0].image_digest)
                != (right[0].image_reference, right[0].image_digest)
            ):
                conflicting.update((left[1], right[1]))
                sides = sorted((left[1], right[1]))
                conflicts.append(ConflictFactInputV1(
                    kind="image_claim", subject=left[0].subject,
                    left_identity=sides[0], right_identity=sides[1],
                ))
        for data in present:
            row, immutable, eid, window = data
            delta = _seconds(instant) - _seconds(row.attested_at)
            if delta < -300:
                disposition, eligibility, reason = (
                    "malformed",
                    "ineligible",
                    "timestamp_malformed",
                )
                age = None
            else:
                age = max(0, delta)
                result = "fresh" if age <= window else "stale"
                freshness.append(FreshnessDecisionInputV1(
                    evidence_identity=immutable, effective_time=row.attested_at,
                    window_seconds=window, age_seconds=age, result=result,
                ))
                if immutable in conflicting:
                    disposition, eligibility, reason = (
                        "conflicted",
                        "ineligible",
                        "accepted_claim_conflict",
                    )
                elif result == "stale":
                    disposition, eligibility, reason = (
                        "accepted",
                        "ineligible",
                        "accepted_stale",
                    )
                else:
                    disposition, eligibility, reason = (
                        "accepted",
                        "eligible",
                        "accepted_fresh",
                    )
            decision = EvidenceDecisionInput(
                expected_source_id=row.expected_source_id,
                source_class=row.source_class,
                subject=row.subject,
                release_version=row.release_version,
                image_reference=row.image_reference,
                image_digest=row.image_digest,
                source_id=row.released_source_id,
                immutable_identity=immutable,
                evidence_id=eid,
                attested_at=row.attested_at,
                freshness_window_seconds=window,
                disposition=disposition,
                eligibility=eligibility,
                reason_code=reason,
            )
            evidence_decisions.append(decision)
            if disposition == "accepted":
                accepted.append(
                    Evidence(
                        evidence_id=eid,
                        source_class=row.source_class,
                        source_id=row.released_source_id,
                        subject=row.subject,
                        claim="immutable_image_release",
                        immutable_identity=immutable,
                        attested_at=row.attested_at,
                        freshness_window_seconds=window,
                    )
                )
            identity = (
                immutable
                if disposition == "accepted"
                else compound_hash("atlas:evidence-decision:v1", decision)
            )
            provenance.append(
                Provenance(
                    claim="immutable_image_release",
                    source_class="image_release_evidence",
                    source_id=row.released_source_id or row.expected_source_id,
                    immutable_identity=identity,
                    observed_at=None,
                    attested_at=row.attested_at,
                )
            )
        freshness = list({canonical_json(row): row for row in freshness}.values())
        for fresh in freshness:
            freshness_identity = compound_hash(
                "atlas:freshness:v1",
                FreshnessIdentityInputV1(
                    policy_identity=policy_identity, evaluation_instant=instant,
                    evidence_identity=fresh.evidence_identity,
                    effective_time=fresh.effective_time,
                    window_seconds=fresh.window_seconds,
                    age_seconds=fresh.age_seconds, result=fresh.result,
                ),
            )
            provenance.append(Provenance(
                claim="freshness", source_class="policy_evaluation",
                source_id="freshness-policy",
                immutable_identity=freshness_identity,
                observed_at=instant, attested_at=None,
            ))
        evidence_provenance = [p for p in provenance if p.source_class == "image_release_evidence"]
        for left, right in combinations(evidence_provenance, 2):
            if (
                (left.claim, left.source_class, left.source_id)
                == (right.claim, right.source_class, right.source_id)
                and left.immutable_identity != right.immutable_identity
            ):
                sides = sorted((left.immutable_identity, right.immutable_identity))
                conflicts.append(ConflictFactInputV1(
                    kind="provenance_identity", subject=left.claim,
                    left_identity=sides[0], right_identity=sides[1],
                ))
        compat_observation = compatibility_observation or CompatibilityAdapterInput(
            source_kind="absent", item_id=item, target_type_present=False,
            status="not_available", findings=(), unknown_fact_codes=(),
        )
        if compat_observation.item_id != item:
            raise ValueError("compatibility item mismatch")
        evaluator_identity = compound_hash(
            "atlas:compatibility-evaluator:v1",
            CompatibilityEvaluatorIdentityInputV1(catalog_identity=catalog_identity),
        )
        if compat_observation.source_kind == "absent":
            input_identity = compound_hash(
                "atlas:compatibility-absent-input:v1",
                CompatibilityAbsentInputV1(item_id=item),
            )
        else:
            input_identity = compound_hash(
                "atlas:compatibility-released-input:v1",
                CompatibilityReleasedInputV1(
                    item_id=item,
                    target_type_present=compat_observation.target_type_present,
                    status=compat_observation.status,
                    findings=compat_observation.findings,
                    unknown_fact_codes=compat_observation.unknown_fact_codes,
                ),
            )
        if compat_observation.target_type_present:
            projected_result, projected_reason = "unknown", "target_required"
        elif compat_observation.source_kind == "malformed_optional":
            projected_result, projected_reason = "unknown", "compatibility_fact_malformed"
        elif compat_observation.status == "compatible" and not compat_observation.unknown_fact_codes:
            projected_result, projected_reason = "compatible", "target_free_catalog_compatible"
        elif compat_observation.status == "compatible_with_warnings" and not compat_observation.unknown_fact_codes:
            projected_result, projected_reason = "compatible_with_warnings", "target_free_catalog_warning"
        elif compat_observation.status == "incompatible" and not compat_observation.unknown_fact_codes:
            projected_result, projected_reason = "incompatible", "target_free_catalog_incompatible"
        else:
            projected_result, projected_reason = "unknown", "compatibility_fact_missing"
        compat_decision_model = CompatibilityDecisionInputV1(
            contract="installation-plan-compatibility-input-v1",
            item_id=item, evaluator_identity=evaluator_identity,
            input_identity=input_identity,
            source_target_type_present=compat_observation.target_type_present,
            source_result=compat_observation.status,
            projected_result=projected_result, projected_reason=projected_reason,
            findings=compat_observation.findings,
            unknown_fact_codes=compat_observation.unknown_fact_codes,
            warning_projection=projected_result == "compatible_with_warnings",
            target_required_projection=projected_reason == "target_required",
        )
        compatibility = Compatibility(
            result=compat_decision_model.projected_result,
            reason_code=compat_decision_model.projected_reason,
        )
        compat_identity = compound_hash(
            "atlas:compatibility-decision:v1", compat_decision_model
        )
        provenance.append(
            Provenance(
                claim="compatibility",
                source_class="compatibility_evaluation",
                source_id="compatibility-projector",
                immutable_identity=compat_identity,
                observed_at=None,
                attested_at=None,
            )
        )
        if compatibility.reason_code in {
            "target_required",
            "compatibility_fact_missing",
        }:
            add_absence("compatibility_fact", item, "compatibility-projector")
        prereqs, prereq_decisions, prereq_prov = _prerequisites(
            catalog_model, catalog, catalog_identity
        )
        provenance.extend(prereq_prov)
        blockers = []
        missing = []

        def consequence(
            code: str, subject: str, missing_code: str | None = None
        ) -> None:
            blockers.append(Blocker(code=code, subject=subject))
            if missing_code:
                missing.append(MissingFact(code=missing_code, subject=subject))

        if binding.state == "absent":
            consequence(
                "missing_deployment_binding",
                catalog_model.catalog_entry_id,
                "deployment_binding",
            )
        artifact_map = {
            "missing": ("missing_deployment_artifact", "deployment_artifact"),
            "invalid": ("invalid_deployment_artifact", "source_fact"),
            "unsafe": ("unsafe_deployment_artifact", "source_fact"),
            "unknown": ("unknown_deployment_artifact", "deployment_artifact"),
        }
        if artifact.state in artifact_map:
            artifact_blocker, artifact_missing = artifact_map[artifact.state]
            consequence(
                artifact_blocker,
                artifact.service or catalog_model.catalog_entry_id,
                artifact_missing,
            )
        for d in evidence_decisions:
            emap = {
                "record_missing": ("missing_accepted_evidence", "accepted_evidence"),
                "source_class_untrusted": ("untrusted_evidence", "accepted_evidence"),
                "source_class_unsupported": ("untrusted_evidence", "accepted_evidence"),
                "record_malformed": ("malformed_evidence", "source_fact"),
                "timestamp_malformed": ("malformed_evidence", "source_fact"),
                "digest_or_identity_malformed": ("malformed_evidence", "source_fact"),
                "accepted_claim_conflict": ("image_conflict", "source_fact"),
                "immutable_identity_conflict": ("provenance_conflict", "source_fact"),
                "release_identity_mismatch": ("image_mismatch", "accepted_evidence"),
                "source_unavailable": ("missing_accepted_evidence", "source_fact"),
                "accepted_stale": ("stale_evidence", None),
            }
            if d.reason_code in emap:
                consequence(
                    emap[d.reason_code][0], d.subject or item, emap[d.reason_code][1]
                )
        if any(fact.kind in {"provenance_identity", "immutable_identity"} for fact in conflicts):
            consequence("provenance_conflict", "immutable_image_release", "source_fact")
        if compatibility.result == "unknown":
            consequence("unknown_compatibility", item, "compatibility_fact")
        elif compatibility.result == "incompatible":
            consequence("incompatible_application_environment", item)
        if compatibility.reason_code == "compatibility_fact_malformed":
            consequence("malformed_source_fact", item, "source_fact")
        if compatibility.reason_code == "target_required":
            consequence("missing_target_identity", item, "target_identity")
        assumptions = []
        assumption_decisions = []
        confirmations = []
        risks = []
        if compatibility.result == "compatible_with_warnings":
            risks.append(
                Risk(code="compatibility_warning", severity="medium", subject=item)
            )
            aid = compound_hash(
                "atlas:assumption-id:v1",
                AssumptionIdentityInputV1(
                    kind="catalog", source_fact_kind="compatibility_warning",
                    subject=item,
                ),
            )
            assumptions.append(
                Assumption(
                    assumption_id=aid,
                    kind="catalog",
                    statement=f"Catalog compatibility warning {item} requires review.",
                )
            )
            assumption_decisions.append(AssumptionDecisionInputV1(
                assumption_id=aid, kind="catalog",
                source_fact_kind="compatibility_warning", subject=item,
            ))
            confirmations.extend(
                (
                    Confirmation(
                        code="confirm_risk",
                        subject=item,
                        prompt=f"Review the informational risk {item}; this does not approve or authorize any action.",
                    ),
                    Confirmation(
                        code="accept_assumption",
                        subject=aid,
                        prompt=f"Review the informational assumption {aid}; this does not approve or authorize any action.",
                    ),
                )
            )
        for p in prereqs:
            if p.state == "missing":
                consequence("missing_prerequisite", p.prerequisite_id)
            elif p.state == "unknown":
                consequence(
                    "missing_prerequisite_fact", p.prerequisite_id, "prerequisite_fact"
                )
                add_absence(
                    "prerequisite_fact", p.prerequisite_id, "prerequisite-projector"
                )
                aid = compound_hash(
                    "atlas:assumption-id:v1",
                    AssumptionIdentityInputV1(
                        kind="environment", source_fact_kind="prerequisite_unknown",
                        subject=p.prerequisite_id,
                    ),
                )
                assumptions.append(
                    Assumption(
                        assumption_id=aid,
                        kind="environment",
                        statement=f"Target environment must be checked for prerequisite {p.prerequisite_id}.",
                    )
                )
                assumption_decisions.append(AssumptionDecisionInputV1(
                    assumption_id=aid, kind="environment",
                    source_fact_kind="prerequisite_unknown",
                    subject=p.prerequisite_id,
                ))
                confirmations.append(
                    Confirmation(
                        code="confirm_prerequisite",
                        subject=p.prerequisite_id,
                        prompt=f"Review the informational prerequisite {p.prerequisite_id}; this does not approve or authorize any action.",
                    )
                )
                confirmations.append(
                    Confirmation(
                        code="accept_assumption",
                        subject=aid,
                        prompt=f"Review the informational assumption {aid}; this does not approve or authorize any action.",
                    )
                )
        for confirmation in confirmations:
            consequence("required_operator_confirmation", confirmation.subject)
        if any(fact.kind == "image_claim" for fact in conflicts):
            image_state = "conflicted"
        elif any(
            d.reason_code == "release_identity_mismatch" for d in evidence_decisions
        ):
            image_state = "mismatched"
        elif obs.image_mutable:
            image_state = "mutable"
            consequence("mutable_image_reference", item, "immutable_image_identity")
        elif obs.state == "missing" or (
            obs.state == "present"
            and (obs.image_reference is None or obs.image_digest is None)
        ):
            image_state = "missing"
            consequence(
                "missing_immutable_image_identity", item, "immutable_image_identity"
            )
        elif (
            obs.state == "present"
            and obs.image_reference is not None
            and obs.image_digest is not None
            and any(
                d.reason_code in {"source_class_untrusted", "source_class_unsupported"}
                and d.subject == item
                and d.release_version == release
                and d.image_reference == obs.image_reference
                and d.image_digest == obs.image_digest
                for d in evidence_decisions
            )
            and not any(d.reason_code in {"accepted_fresh", "accepted_stale"} for d in evidence_decisions)
        ):
            image_state = "untrusted"
        elif (
            artifact.state in {"invalid", "unsafe", "unknown"}
            or binding.state == "absent"
            or release is None
            or not any(d.eligibility == "eligible" for d in evidence_decisions)
        ):
            image_state = "unknown"
            consequence("unknown_image_state", item, "immutable_image_identity")
        else:
            image_state = "grounded"
        image_ref = (
            obs.image_reference
            if image_state
            in {"grounded", "mutable", "missing", "untrusted", "mismatched", "unknown"}
            else None
        )
        image_digest = (
            obs.image_digest
            if image_state in {"grounded", "untrusted", "mismatched", "unknown"}
            else None
        )
        image_decision = ImageDecisionInputV1(
            state=image_state, reference=image_ref, digest=image_digest,
            release_version=release,
        )
        for d in evidence_decisions:
            if d.reason_code == "accepted_fresh":
                f = next(
                    x
                    for x in freshness
                    if x.evidence_identity == d.immutable_identity
                )
                if f.window_seconds - f.age_seconds <= f.window_seconds // 10:
                    risks.append(
                        Risk(
                            code="evidence_approaching_expiry",
                            severity="low",
                            subject=d.subject,
                        )
                    )
        blockers = sorted(
            {(b.code, b.subject): b for b in blockers}.values(),
            key=lambda b: (_BLOCKER_ORDER.index(b.code), b.subject),
        )
        missing = sorted(
            {(m.code, m.subject): m for m in missing}.values(),
            key=lambda m: (_MISSING_FACT_ORDER.index(m.code), m.subject),
        )
        confirmations = sorted(
            {(c.code, c.subject): c for c in confirmations}.values(),
            key=lambda c: (c.code, c.subject),
        )
        assumptions = sorted(assumptions, key=lambda a: (a.assumption_id, a.kind))
        risks = sorted(
            risks,
            key=lambda r: (
                {"critical": 0, "high": 1, "medium": 2, "low": 3}[r.severity],
                _RISK_ORDER.index(r.code),
                r.subject,
            ),
        )
        accepted = sorted(
            accepted,
            key=lambda e: (
                e.subject,
                e.claim,
                e.source_class,
                e.source_id,
                e.immutable_identity,
                e.evidence_id,
                e.attested_at,
            ),
        )
        provenance = sorted(
            provenance,
            key=lambda p: (
                p.claim,
                _PROVENANCE_SOURCE_ORDER.index(p.source_class),
                p.source_id,
                p.immutable_identity,
                p.observed_at or "",
                p.attested_at or "",
            ),
        )
        evidence_decisions = sorted(
            evidence_decisions,
            key=lambda d: (
                d.expected_source_id,
                {"curated": 0, "registry_attested": 1, "upstream_signed": 2, "unknown": 3}[d.source_class],
                d.subject or "",
                d.claim,
                d.release_version or "",
                d.image_reference or "",
                d.image_digest or "",
                d.source_id or "",
                d.immutable_identity or "",
                d.evidence_id or "",
                _EVIDENCE_DISPOSITION_ORDER.index(d.disposition),
                d.eligibility,
                _EVIDENCE_REASON_ORDER.index(d.reason_code),
                d.attested_at or "",
                -1 if d.freshness_window_seconds is None else d.freshness_window_seconds,
            ),
        )
        absence = sorted(absence, key=lambda x: (
            _ABSENCE_ORDER.index(x.kind), x.subject, x.source_id, x.identity
        ))
        unavailable = sorted(unavailable, key=lambda x: (x.kind, x.subject, x.expected_source_id, x.reason_code, x.identity))
        freshness = sorted(freshness, key=lambda x: (
            x.evidence_identity, x.effective_time, x.window_seconds,
            x.age_seconds, x.result,
        ))
        codes = {b.code for b in blockers}
        status = _plan_status(codes)
        fp = FingerprintInputV1(
            evaluation_instant=instant,
            freshness_policy_identity=policy_identity,
            application=ApplicationDecisionInputV1(
                item_id=item, catalog_entry_id=catalog_model.catalog_entry_id,
                release_version=release,
            ),
            catalog=CatalogDecisionFingerprintInputV1(
                catalog_identity=catalog_identity,
                catalog_source_identity=catalog_source_identity,
                decision=catalog_model,
            ),
            binding=binding,
            artifact=artifact,
            image=image_decision,
            evidence_decisions=tuple(evidence_decisions),
            provenance_decisions=tuple(
                ProvenanceDecisionInputV1(**p.model_dump(mode="python"))
                for p in provenance
            ),
            compatibility_decisions=(compat_decision_model,),
            prerequisites=tuple(prereq_decisions),
            relationships=catalog_model.relationships,
            assumptions=tuple(
                sorted(assumption_decisions, key=lambda a: (a.assumption_id, a.kind))
            ),
            blockers=tuple(BlockerDecisionInputV1(code=b.code, subject=b.subject) for b in blockers),
            risks=tuple(RiskDecisionInputV1(code=r.code, severity=r.severity, subject=r.subject) for r in risks),
            missing_facts=tuple(MissingFactDecisionInputV1(code=m.code, subject=m.subject) for m in missing),
            confirmations=tuple(
                ConfirmationDecisionInputV1(
                    code=c.code, subject=c.subject,
                    prompt_template_id={
                        "accept_assumption": "atlas:prompt:accept-assumption:v1",
                        "confirm_prerequisite": "atlas:prompt:confirm-prerequisite:v1",
                        "confirm_risk": "atlas:prompt:confirm-risk:v1",
                    }[c.code],
                )
                for c in confirmations
            ),
            absence_facts=tuple(absence),
            conflict_facts=tuple(
                sorted(
                    conflicts,
                    key=lambda x: (
                        _CONFLICT_ORDER.index(x.kind), x.subject,
                        x.left_identity, x.right_identity,
                    ),
                )
            ),
            source_unavailable_facts=tuple(unavailable),
            freshness_decisions=tuple(freshness),
        )
        return InstallationPlan(
            fingerprint=fingerprint(fp),
            application=Application(
                item_id=item,
                catalog_entry_id=catalog_model.catalog_entry_id,
                display_name=entry.item.name,
                release_version=release,
            ),
            status=status,
            deployment_artifact=DeploymentArtifact(
                state=artifact.state, repository_path=artifact.repository_path,
                service=artifact.service, content_digest=artifact.content_digest,
            ),
            image=Image(**image_decision.model_dump(mode="python")),
            accepted_evidence=tuple(accepted),
            provenance=tuple(provenance),
            compatibility=(compatibility,),
            prerequisites=tuple(prereqs),
            relationships=tuple(
                Relationship(**r.model_dump(mode="python"))
                for r in catalog_model.relationships
            ),
            assumptions=tuple(assumptions),
            blockers=tuple(blockers),
            risks=tuple(risks),
            missing_facts=tuple(missing),
            required_operator_confirmations=tuple(confirmations),
        )
