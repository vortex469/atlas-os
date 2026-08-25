# InstallationPlan v1 contract and threat model

Status: **v0.16 P0 decision-complete; implementation pending**. This
normative P1–P5 contract adds no runtime behavior or authority.

## Authority and lifetime

`InstallationPlan` is an immutable, deterministic, provenance-linked,
item-scoped informational read model assembled for one GET and discarded. It
is ephemeral, non-authorizing, non-persistent and non-executable. It is not a
candidate, intent, proposal, workflow, approval, action request, dispatch,
deployment specification or recipe. No status or fingerprint authorizes
install, configure, update, restart, remove, deploy, remediate, roll back,
repository mutation, worker execution or release publication. Discovery,
Provider Intent, operational dispatch, repository execution, worker,
backup/restore, collector and no-replay contracts are unchanged.

`plan_ready_for_review` means only that item-scoped facts have no blocker; it
never means approved, executable or deployable. Plans have no database, file,
event, queue, approval, idempotency or replay identity. A bounded HTTP/UI cache
may hold presentation bytes only; it is never evaluator input, freshness
evidence or mutation authority.

V1 has no target field. Any caller-supplied target selector is rejected before
assembly with sanitized 422. Target-dependent released compatibility is never
projected as target-free compatibility. Target support requires v2 and another
authority review.

## Wire schema

The schema label is exactly `installation-plan-v1`. Every object is frozen and
closed (`additionalProperties: false`); every listed field is required,
including arrays and explicit nulls. Unknown fields/enums, duplicates after
normalization, wrong types, non-finite numbers and invalid UTF-8 fail.

### Canonical primitive types

These definitions are self-contained and apply before bounds written at a use
site. A string is nullable only where its enclosing field says `|null`.

`Array<T,a..b>` is a JSON array containing `a..b` values of exact type `T`.
The shorter `T[a..b]` notation denotes an array only when `T` is a closed
object/enum type without parameterized scalar bounds; nested forms such as
`Id[1..64][0..64]` mean an array of zero through 64 bounded IDs.

* `Bool` is the JSON literal `true` or `false`; strings and numbers do not
  coerce. Its canonical serialization is the corresponding lowercase literal.
* `Int[a..b]` is a JSON integer in the inclusive written range, with no
  fractional part, exponent, negative zero or coercion. The contract never
  uses a magnitude above `9007199254740991`. JCS's shortest decimal JSON number
  is its canonical serialization.
* `Id[m..n]` is `m..n` ASCII bytes matching
  `[a-z0-9][a-z0-9._:-]*`. It is already lowercase, has no whitespace or
  controls, and serializes as that unchanged JSON string.
* `SafeSourceId[m..n]` is exactly `Id[m..n]`, with permitted bounds
  `1..256`; every v1 use is `SafeSourceId[1..256]`. It is named separately to
  mark a source-owned or code-owned provenance identity, not a path or URL.
* `SafeFactCode` is exactly `Id[1..128]`; unknown/free-form fact codes are
  invalid. Arrays use `Array<SafeFactCode,0..128>` so scalar byte bounds cannot
  be confused with array cardinality.
* `Version` is ASCII `0|[1-9][0-9]*` in each of exactly three dot-separated
  components (`X.Y.Z`), each 0..2147483647. No sign, prefix, suffix, whitespace
  or leading zero is allowed. Canonical serialization uses the three shortest
  decimal components unchanged.
* `DecimalString` is an ASCII JSON string matching `0|[1-9][0-9]*` or
  `(0|[1-9][0-9]*)\.[0-9]*[1-9]`, 1..32 bytes, and represents a non-negative
  finite decimal. Signs, exponent, leading zero, trailing fractional zero,
  bare decimal point and `-0` are invalid. Its canonical serialization is the
  unchanged string.
* `Sha256Digest` is an ASCII JSON string exactly matching
  `sha256:[0-9a-f]{64}`. Uppercase and every other algorithm/spelling fail;
  canonical serialization is unchanged.
* `UtcSecond` is an ASCII JSON string exactly matching
  `YYYY-MM-DDTHH:MM:SSZ`: four-digit years `0001..9999`, valid month and day
  in the proleptic Gregorian calendar (including its leap-year rule), hours `00..23`, minutes
  `00..59`, and seconds `00..59`. UTC `Z` is mandatory; offsets, lowercase
  `z`, fractions, leap seconds and `24:00:00` fail. Parse strictly to a UTC
  calendar instant and reserialize with zero-padded fields to that identical
  grammar; non-round-tripping input fails.
* `PlainText[m..n]` is a JSON string of `m..n` UTF-8 bytes under Unicode 15.1
  NFC. Input must already equal its NFC form and may not begin or end with a
  Unicode 15.1 `White_Space` property code point; it is not silently changed.
  CR, LF, every C0/C1 control, DEL, Unicode
  line/paragraph separators, bidi controls U+061C/U+200E/U+200F/U+202A..U+202E
  and U+2066..U+2069, unpaired surrogates and noncharacters are forbidden.
  Other internal Unicode whitespace is preserved. Canonical serialization is
  the JCS JSON string of the unchanged NFC scalar sequence.
* `RepoPath` is an ASCII JSON string of 1..512 bytes: a relative POSIX path of
  1..32 nonempty `/`-separated segments, each matching
  `[A-Za-z0-9][A-Za-z0-9._-]*`, whose final segment ends in lowercase `.yaml`
  or `.yml`. `.` and `..` segments, empty segments, backslash, colon, percent,
  NUL/control/whitespace, a leading `/`, `~`, drive form and any encoded
  alternative are invalid. Case is preserved. Canonical serialization is the
  unchanged string; containment and symlink checks are additional artifact
  rules, not normalization.
* `OciRepository` is an ASCII JSON string of 1..512 bytes in the canonical
  repository form produced by the complete OCI normalization algorithm below.
  It contains a lowercase registry (and optional explicit decimal port) plus
  lowercase repository components, no tag or digest. It is already normalized
  and serializes unchanged.
* `lowerhex[64]` is an ASCII JSON string matching `[0-9a-f]{64}` and serializes
  unchanged.

There is no generic unnamed string or number in a closed contract type.

| Top-level field | Exact type/bound |
|---|---|
| `schema_version` | literal `installation-plan-v1` |
| `fingerprint` | `{algorithm:"sha256",canonicalization:"atlas-jcs-nfc-v1",value:lowerhex[64]}` |
| `application` | `Application` |
| `status` | `conflicted|missing_deployment_artifact|incompatible|stale_evidence|insufficient_information|plan_ready_for_review` |
| `deployment_artifact` | `DeploymentArtifact` |
| `image` | `Image` |
| `accepted_evidence` | `Evidence[0..32]` |
| `provenance` | `Provenance[1..256]` |
| `compatibility` | `Compatibility[1]` |
| `prerequisites` | `Prerequisite[0..64]` |
| `relationships` | `Relationship[0..64]` |
| `assumptions` | `Assumption[0..32]` |
| `blockers` | `Blocker[0..64]` |
| `risks` | `Risk[0..32]` |
| `missing_facts` | `MissingFact[0..64]` |
| `required_operator_confirmations` | `Confirmation[0..32]` |

All fields in these closed nested types are required:

* `Application={item_id:Id[1..64],catalog_entry_id:Id[1..64],
  display_name:PlainText[1..128],release_version:Version|null}`.
* `DeploymentArtifact={state:present|missing|invalid|unsafe|unknown,
  kind:"docker-compose",repository_path:RepoPath|null,
  service:Id[1..255]|null,content_digest:Sha256Digest|null}`. The digest is
  non-null only for a safely read regular file. `RepoPath` is relative POSIX,
  1..512 bytes and <=32 nonempty segments, lowercase `.yaml`/`.yml`, with no
  `.`, `..`, backslash, leading `/`/`~`, drive form or encoded alternative.
  Resolution rejects symlinks and remains within the injected repository root; absolute
  paths never enter output.
* `Image={state:grounded|missing|mutable|untrusted|conflicted|mismatched|
  unknown,reference:OciRepository|null,digest:Sha256Digest|null,
  release_version:Version|null}`. Grounded requires all non-null and a fresh,
  eligible accepted row matching all values.
* `Evidence={evidence_id:lowerhex[64],source_class:curated|
  registry_attested|upstream_signed,source_id:SafeSourceId[1..256],
  subject:Id[1..128],claim:Id[1..128],immutable_identity:lowerhex[64],
  observed_at:null,attested_at:UtcSecond,
  freshness_window_seconds:Int[60..31536000],trust:"accepted"}`.
* `Provenance={claim:Id[1..128],source_class:curated_catalog|
  deployment_binding|repository_observation|image_release_evidence|
  compatibility_evaluation|prerequisite_source|policy_evaluation,
  source_id:SafeSourceId[1..256],immutable_identity:lowerhex[64],
  observed_at:UtcSecond|null,attested_at:UtcSecond|null}`.
* `Compatibility={environment:"item-scoped",result:compatible|
  compatible_with_warnings|incompatible|unknown,reason_code:
  target_free_catalog_compatible|target_free_catalog_warning|
  target_free_catalog_incompatible|target_required|
  compatibility_fact_missing|compatibility_fact_malformed}`.
* `Prerequisite={prerequisite_id:Id[1..64],kind:storage|network|platform|
  application|operator,state:satisfied|missing|unknown,
  description:PlainText[1..256]}`.
* `Relationship={kind:depends_on|provides|consumes|requires|integrates_with|
  conflicts_with|runs_on|deployed_by|compatible_with|incompatible_with,
  item_id:Id[1..64],required:Bool,minimum_version:Version|null,
  maximum_version:Version|null}`.
* `Assumption={assumption_id:Id[1..64],kind:catalog|environment|operator,
  statement:PlainText[1..256]}`; it cannot assert approval, target,
  compatibility, artifact presence, image identity or prerequisite success.
* `Blocker={code:BlockerCode,subject:Id[1..128]}`.
* `Risk={code:artifact_content_change|evidence_approaching_expiry|
  environment_variance|compatibility_warning,severity:low|medium|high|
  critical,subject:Id[1..128]}`.
* `MissingFact={code:deployment_binding|deployment_artifact|
  immutable_image_identity|accepted_evidence|prerequisite_fact|
  target_identity|compatibility_fact|source_fact,subject:Id[1..128]}`.
* `Confirmation={code:accept_assumption|confirm_prerequisite|confirm_risk,
  subject:Id[1..128],prompt:PlainText[1..256]}`; it is a question, never an
  approval or response.

Null is allowed only above. Server-owned presentation text is escaped at every
sink and excluded from decisions/fingerprinting; its typed ID/code is included.

## Released evidence adaptation and trust

Released `ImageReleaseEvidence` has exactly `catalog_item_id`,
`release_version`, `image_reference`, `image_digest`, `source_class`,
`source_id`, and `attested_at`. V1 derives no authority field absent there.
A reviewed code-owned policy, not evidence data, supplies seconds:
   `curated=31536000`, `registry_attested=2592000`,
   `upstream_signed=604800`. The closed object is
   `FreshnessPolicyInputV1={curated:31536000,registry_attested:2592000,
   upstream_signed:604800}`; its identity uses domain
   `atlas:image-evidence-freshness-policy:v1` and the compound framing below.

### Raw adapter boundary

`RawEvidenceObservation` is adapter-owned, internal, never emitted and never
fingerprinted directly. It is a closed object with every field required:

```
RawEvidenceObservation={
 observation_kind:present|absent|parse_failure|schema_failure|
   unsupported_source_class|missing_required_field|malformed_timestamp|
   malformed_identity|malformed_digest|source_unavailable,
 expected_source_id:SafeSourceId[1..256],
 source_class:curated|registry_attested|upstream_signed|unknown|null,
 subject:Id[1..128]|null, release_version:Version|null,
 image_reference:OciRepository|null, image_digest:Sha256Digest|null,
 released_source_id:SafeSourceId[1..256]|null,
 attested_at:UtcSecond|null,
 adapter_reason:record_absent|record_parse_failure|record_schema_failure|
   source_class_unsupported|required_field_missing|timestamp_malformed|
   identity_malformed|digest_malformed|source_read_unavailable|null
}
```

The reader owns only bounded bytes; the adapter owns this classification.
`expected_source_id` is the configured logical source being read, never parsed
from the failing payload. The following table is the complete cross-field
relation. “Released fields” means `source_class`, `subject`, `release_version`,
`image_reference`, `image_digest`, `released_source_id`, and `attested_at`.
Every non-null released field has independently passed its named primitive and
released-field validation; null never means an invalid value was retained.

| `observation_kind` | Exact required/null relation | `adapter_reason` |
|---|---|---|
| `present` | `source_class` is one of the three known classes; every other released field is non-null | null |
| `absent` | all released fields null | `record_absent` |
| `parse_failure` | all released fields null | `record_parse_failure` |
| `schema_failure` | any independently validated released fields may remain; at least one field has a structural type/unknown-field/container-schema defect not classified below | `record_schema_failure` |
| `unsupported_source_class` | `source_class=unknown`; `released_source_id` may remain only when independently valid; all other released fields null | `source_class_unsupported` |
| `missing_required_field` | at least one released field null; every non-null released field independently valid | `required_field_missing` |
| `malformed_timestamp` | `attested_at` null; every other released field independently valid and non-null | `timestamp_malformed` |
| `malformed_identity` | `released_source_id` null; every other released field independently valid and non-null | `identity_malformed` |
| `malformed_digest` | `image_digest` null; every other released field independently valid and non-null | `digest_malformed` |
| `source_unavailable` | all released fields null | `source_read_unavailable` |

An adapter validates the bounded record completely, then chooses exactly one
kind by this first-match precedence: source read unavailable; absent record;
byte/UTF-8/YAML/JSON parse failure; unsupported source class; structural schema
failure; missing required field; malformed timestamp; malformed source
identity; malformed digest; otherwise present. Thus a structural schema defect
wins over missing/malformed scalar defects, and timestamp wins over identity,
which wins over digest. A defect in subject, release version or image reference
is a structural schema failure. The kind/reason relation and table null rules
are validated again when constructing this object; a nonconforming combination
is an adapter contract failure and returns 503/no plan.

`adapter_reason` is therefore null exactly for `present`; otherwise it is the
one table reason. `source_unavailable` is allowed only for a
successfully bounded optional source whose absence is a stable source fact;
unavailable required reads, partial reads, overflow, or uncertain
classification return 503/no plan. At most 128 observations are accepted.
No raw string, provider payload, exception, URL, secret, command, executable
content, or invalid value enters this type. Consequently every representable
object has exactly one row below; no observation is silently dropped.

The raw-to-decision classification is exact: `present` continues through
policy/match/freshness evaluation; `absent` -> `missing/record_missing`;
`unsupported_source_class` -> `unsupported/source_class_unsupported`;
`malformed_timestamp` -> `malformed/timestamp_malformed`;
`malformed_identity` or `malformed_digest` ->
`malformed/digest_or_identity_malformed`; `parse_failure`, `schema_failure`, or
`missing_required_field` -> `malformed/record_malformed`; and
`source_unavailable` -> `unavailable/source_unavailable`. Every mapping is
ineligible. A present row maps to one of the remaining policy, match,
freshness, or conflict rows in the total table below.
For every non-present observation, normalized `source_class` copies a known or
`unknown` raw value and becomes the sanitized enum `unknown` when raw is null;
the other released fields copy their independently valid value or remain null.
The table fixes disposition/reason, eligibility is ineligible, and derived
identities/window follow their explicit null rules. This is the only
raw-to-normalized construction.

### Normalized evidence decisions

The adapter maps each observation to this closed, valid-only object; every
field is required and null has exactly the meaning “not safely known/not
applicable”:

```
EvidenceDecisionInput={
 record_type:"image_release_evidence_decision_v1",
 expected_source_id:SafeSourceId[1..256],
 source_class:curated|registry_attested|upstream_signed|unknown,
 subject:Id[1..128]|null, claim:"immutable_image_release",
 release_version:Version|null, image_reference:OciRepository|null,
 image_digest:Sha256Digest|null, source_id:SafeSourceId[1..256]|null,
 immutable_identity:lowerhex[64]|null, evidence_id:lowerhex[64]|null,
 attested_at:UtcSecond|null,
 freshness_window_seconds:Int[60..31536000]|null,
 disposition:accepted|missing|untrusted|unsupported|malformed|
   unavailable|conflicted|mismatched,
 eligibility:eligible|ineligible,
 reason_code:accepted_fresh|accepted_stale|record_missing|
   source_class_untrusted|source_class_unsupported|record_malformed|
   timestamp_malformed|digest_or_identity_malformed|accepted_claim_conflict|
   immutable_identity_conflict|release_identity_mismatch|source_unavailable
}
```

`expected_source_id` and `claim` are adapter/policy identities, not invented
evidence values. All other nullable fields are copied only when independently
valid. `freshness_window_seconds` is non-null only for a known released source
class to which policy applies; `attested_at` is non-null only when valid.
`immutable_identity` and `evidence_id` are both null unless every input to their
derivation below is safely known. Thus malformed input never requires an
invented evidence ID, digest, timestamp, subject, source ID, or identity.
Accepted rows require `source_class`, subject, release version, image reference,
digest, source ID, both identities, timestamp, and window to be non-null/known.
Untrusted rows may retain independently valid values but both derived
identities are non-null only when the entire identity input is valid. Missing,
unsupported, unavailable, and malformed rows never emit and may use null for
every released field not independently safe. Conflicted/mismatched rows require
the independently valid comparison fields that caused their classification;
they do not manufacture a missing field.

The following table is the entire allowed
`(disposition,eligibility,reason_code)` relation. All other triples are contract
failures and emit no plan. “FP” means the sanitized decision enters
`FingerprintInputV1`; every row is FP=yes. “Conflict” means participation in
claim conflict analysis.

| disposition / eligibility / reason | emitted in `accepted_evidence` | blocker | missing fact | conflict | trust and freshness |
|---|---|---|---|---|---|
| accepted / eligible / `accepted_fresh` | yes | none | none | yes | policy-accepted; valid time, age <= window |
| accepted / ineligible / `accepted_stale` | yes | `stale_evidence` | none | yes | policy-accepted, not grounding-eligible; valid time, age > window |
| missing / ineligible / `record_missing` | no | `missing_accepted_evidence` | `accepted_evidence` | no | no trust; freshness not evaluated |
| untrusted / ineligible / `source_class_untrusted` | no | `untrusted_evidence` | `accepted_evidence` | no | class preserved; no trust promotion; freshness not evaluated |
| unsupported / ineligible / `source_class_unsupported` | no | `untrusted_evidence` | `accepted_evidence` | no | unknown/unsupported, never trusted; freshness not evaluated |
| malformed / ineligible / `record_malformed` | no | `malformed_evidence` | `source_fact` | no | no trust; freshness not evaluated |
| malformed / ineligible / `timestamp_malformed` | no | `malformed_evidence` | `source_fact` | no | source policy may recognize class, but record is not trusted; freshness malformed |
| malformed / ineligible / `digest_or_identity_malformed` | no | `malformed_evidence` | `source_fact` | no | no trust; freshness not evaluated |
| conflicted / ineligible / `accepted_claim_conflict` | no | `image_conflict` | `source_fact` | yes | each candidate passed source policy, but conflict removes eligibility; freshness is evaluated per valid candidate |
| conflicted / ineligible / `immutable_identity_conflict` | no | `provenance_conflict` | `source_fact` | duplicate identity only | complete typed identity inputs disagree despite equal derived identity; freshness may be evaluated but cannot authorize |
| mismatched / ineligible / `release_identity_mismatch` | no | `image_mismatch` | `accepted_evidence` | duplicate identity only | source-policy acceptance does not cure item/version/reference/digest mismatch; freshness evaluated when timestamp valid |
| unavailable / ineligible / `source_unavailable` | no | `missing_accepted_evidence` | `source_fact` | no | only optional stable source fact; no trust or freshness |

`upstream_signed` maps to `untrusted/ineligible/source_class_untrusted`; its
released class remains visible but grants neither eligibility nor trust.
There is no additional released source-policy rejection condition: the only
released class policy outcome outside accepted classes is the untrusted row,
and unknown classes use unsupported. No extra disposition or reason is
reserved for an unreachable policy outcome.
Every `present` normalized row receives exactly one primary decision by the
following first-match precedence. All predicates are evaluated from sanitized,
independently valid fields; a predicate whose inputs are unavailable is false.

| Stage | Entry condition | Exclusion condition | Primary disposition / eligibility / reason | Required consequence | Secondary typed facts and later predicates |
|---|---|---|---|---|---|
| 1 normalization validity | any required released field, timestamp relation, or identity derivation input is invalid/missing | none | the exact raw malformed row / ineligible / its exact malformed reason | `malformed_evidence`; `source_fact`; no conflict participation; null identities unless their complete inputs are valid; decision is fingerprinted | no later decision predicate is evaluated; no inferred secondary condition |
| 2 duplicate immutable-identity disagreement | a complete derived `immutable_identity` equals another row's identity but their complete `EvidenceImmutableIdentityInputV1` objects differ | stage 1 | `conflicted` / ineligible / `immutable_identity_conflict` | `provenance_conflict`; `source_fact`; one `immutable_identity` conflict fact per unordered pair; fingerprint both decisions and fact | no claim-conflict participation and no later primary predicate; independently valid freshness is emitted as a freshness decision, but never authorizes |
| 3 source policy | source class is `upstream_signed` or another known but policy-untrusted future class | stages 1–2 | `untrusted` / ineligible / `source_class_untrusted` | `untrusted_evidence`; `accepted_evidence`; fingerprint decision | no claim-conflict participation; independently provable mismatch and freshness are retained only in the normalized fields/freshness decision, not as extra blockers or conflict facts |
| 4 expected release/image match | subject or release version differs from the selected catalog release, or the row's repository/digest differs from the exact immutable repository observation when one exists | stages 1–3 | `mismatched` / ineligible / `release_identity_mismatch` | `image_mismatch`; `accepted_evidence`; participates only in duplicate-identity analysis; fingerprint decision | no accepted-claim conflict participation; independently valid freshness is emitted; mismatch fields themselves are the typed fact, with no second blocker |
| 5 accepted-claim conflict | at least two remaining policy-accepted rows in the same `(subject,claim,release_version)` group have unequal `(image_reference,image_digest)` | stages 1–4 | `conflicted` / ineligible / `accepted_claim_conflict` for every row in each conflicting group | `image_conflict`; `source_fact`; every unordered unequal pair emits `image_claim`; fingerprint all | conflict participation yes; independently valid freshness is emitted; stale does not suppress conflict and adds no stale primary blocker |
| 6 freshness stale | valid effective time produces `age_seconds > freshness_window_seconds` | stages 1–5 | `accepted` / ineligible / `accepted_stale` | `stale_evidence`; no missing fact; fingerprint decision and freshness | conflict participation was already considered; no later predicate |
| 7 accepted fresh | valid effective time produces `age_seconds <= freshness_window_seconds` | stages 1–6 | `accepted` / eligible / `accepted_fresh` | no blocker/missing fact; fingerprint decision and freshness; emit public accepted evidence | conflict participation was already considered; terminal |

Raw non-present rows are classified before this table by the raw mapping and
cannot reach a present stage. Unsupported class therefore remains
`unsupported/source_class_unsupported`; it is ordered with stage 1 boundary
validation and before any comparison, conflict, or freshness predicate.
Exact duplicate complete identity inputs collapse to one normalized decision
before stage 2. Stage 2 describes only equal derived identities over unequal
typed inputs; because that indicates a hash collision or violated derivation
boundary, it is fail-closed and never eligible. The reason-code enum therefore
also contains `immutable_identity_conflict`, allowed only with
`conflicted/ineligible`. A record yields exactly one primary table row. Later
conditions are surfaced only where this table explicitly requires a typed
freshness decision or conflict fact; implementations may not add secondary
blockers, missing facts, or classifications.

### Evidence identities

For a fully valid released row define the exact closed object
`EvidenceImmutableIdentityInputV1={catalog_item_id:Id[1..64],
release_version:Version,image_reference:OciRepository,
image_digest:Sha256Digest,source_class:curated|registry_attested|
upstream_signed,source_id:SafeSourceId[1..256],attested_at:UtcSecond}`.
Normalize its fields as specified above, apply RFC 8785 JCS, and derive
`immutable_identity=SHA-256(UTF8("atlas:image-evidence-row:v1") || 0x00 ||
UTF8(JCS(object)))` as lowercase hex. Define
`EvidenceIdInputV1={source_class:curated|registry_attested|upstream_signed,
source_id:SafeSourceId[1..256],immutable_identity:lowerhex[64]}` and derive
`evidence_id` identically with domain `atlas:image-evidence-id:v1`.
Derivation occurs for every row whose complete identity input is independently
valid, including untrusted, mismatched, conflicted, stale and fresh rows.
Both values are emitted in wire `accepted_evidence` only for accepted rows;
they remain non-null in every normalized rejected decision with a complete
valid identity input and are fingerprinted there. Missing, malformed, or
unsupported rows have null identities unless every derivation input is
independently valid; there is no fallback identity. Identity never implies
trust, eligibility, acceptance, or grounding. These comparison identities confer
no approval, persistence, replay, or execution authority.

## Closed catalog input and provenance construction

The catalog adapter produces exactly one closed `CatalogDecisionInputV1`:

```
CatalogDecisionInputV1={
 schema_version:1, catalog_entry_id:Id[1..64], item_id:Id[1..64],
 item_type:application|service|container_image|ai_model|integration|
   hardware_device|deployment_method,
 item_status:active|deprecated|experimental|unknown,
 item_version:Version|null,
 release_claim:CatalogReleaseClaimDecisionInputV1|null,
 release_version:Version|null,
 provenance_source_type:curated|private|community|dynamic,
 provenance_source_id:SafeSourceId[1..256],
 provenance_entry_id:Id[1..64]|null, provenance_version:PlainText[1..64]|null,
 provenance_trust_level:curated|verified|community|private|dynamic,
 deployment_binding:DeploymentBindingDecisionInputV1|null,
 requirements:RequirementDecisionInputV1,
 relationships:RelationshipDecisionInputV1[0..64],
 reviewed_content_digest:Sha256Digest
}
CatalogReleaseClaimDecisionInputV1={version:Version,published_at:UtcSecond}
DeploymentBindingDecisionInputV1={kind:"docker-compose",
 repository_path:RepoPath,service:Id[1..255]}
RequirementDecisionInputV1={capability_ids:Id[1..64][0..64],cpu_cores_min:
 DecimalString|null,memory_mb_min:Int[0..2147483647]|null,
 storage_gb_min:DecimalString|null,gpu_required:Bool,
 gpu_memory_gb_min:DecimalString|null,architectures:Id[1..64][0..32],
 operating_systems:Id[1..64][0..32],runtimes:Id[1..64][0..32],
 devices:Id[1..64][0..32],
 ports:{port:Int[1..65535],protocol:tcp|udp,direction:inbound|outbound,
 required:Bool}[0..64],requires_internet:Bool,requires_lan:Bool}
RelationshipDecisionInputV1={kind:depends_on|provides|consumes|requires|
 integrates_with|conflicts_with|runs_on|deployed_by|compatible_with|
 incompatible_with,item_id:Id[1..64],required:Bool,
 minimum_version:Version|null,maximum_version:Version|null}
```

`DecimalString` has the canonical primitive definition above. Presentation fields,
URLs, aliases, tags, descriptions, notes, and arbitrary metadata are excluded.
`reviewed_content_digest` is the lowercase `sha256:` digest of the exact
validated UTF-8 catalog source bytes before YAML decoding; it is not a path or
mutable loader label. Arrays are normalized and sorted: capability/architecture/
OS/runtime/device IDs lexically; ports `(port,protocol,direction,required)`;
relationships `(kind,item_id,required,minimum_version,maximum_version)`, null
before text and false before true. Duplicate tuples fail adaptation.

`item_version` is the normalized released `CatalogEntry.item.version` and
`release_claim` is the normalized released `CatalogEntry.release_claim`; no
other field may supply an application release. Selection is exact: when a
valid curated `release_claim` exists, `release_version` equals its `version`;
if `item_version` is also non-null it MUST equal that version exactly after
`Version` normalization or catalog adaptation fails closed with sanitized
`installation_plan_contract_failure`/503 and no plan. When no release claim
exists, a valid non-null `item_version` is selected. When both are null,
`release_version=null`; image state is `unknown`, with
`unknown_image_state`, missing fact `immutable_image_identity`, and no evidence
row may be release-matched or grounding-eligible. An invalid version or
release-claim timestamp is a required catalog adaptation failure, never null.
The selected value is copied to `Application.release_version`,
`ApplicationDecisionInputV1.release_version`, and image comparison input.
Both source fields, the complete release claim (including `published_at`), and
the selected value are included in `CatalogDecisionInputV1`, catalog identity,
and the plan fingerprint. Catalog provenance has `observed_at=null` and
`attested_at=release_claim.published_at` when a claim exists, otherwise null;
its immutable identity remains `catalog_source_identity`. Thus the released Home Assistant
`item.version=null`, `release_claim.version="2026.8.3"` deterministically
selects `release_version="2026.8.3"` without fallback or invention.

`catalog_source_id` is the released safe provenance source ID (never a file
path); `CatalogSourceIdentityInputV1={catalog_entry_id,item_id,
provenance_source_type,provenance_source_id,provenance_entry_id,
provenance_version,reviewed_content_digest}` is hashed with domain
`atlas:catalog-source:v1`. The full `CatalogDecisionInputV1` is hashed with
domain `atlas:catalog-decision:v1` to produce `catalog_identity`. Both use the
compound framing defined below and both enter the fingerprint; the former is
the catalog provenance `immutable_identity`. Invalid required catalog fields
or unavailable source bytes return 503/no plan, so there is no nullable or
invented catalog identity.
`catalog_entry_id` is the normalized non-null released provenance `entry_id`;
v1 does not fall back to `item_id`, a path, or a synthesized value. A released
entry without it cannot satisfy this required plan input and returns 503.
V1 emits catalog provenance only when `provenance_source_type=curated` and
`provenance_trust_level=curated`; every other released combination is a
required-source policy failure and returns sanitized 503/no plan rather than
being mislabeled `curated_catalog`.

`source_id` is a validated released source-owned ID or one of these truthful
adapter IDs: `catalog-loader`, `deployment-binding`, `repository-observer`,
`compatibility-projector`, `prerequisite-projector`, `freshness-policy`. Every
identity below is lowercase SHA-256 of UTF-8 domain, NUL, then JCS of the stated
sanitized object:

| Fact | class / ID | Domain; exact typed object |
|---|---|---|
| catalog | `curated_catalog` / `catalog_source_id` | `atlas:catalog-source:v1`; `CatalogSourceIdentityInputV1` |
| binding | `deployment_binding` / `deployment-binding` | `atlas:binding:v1`; `BindingIdentityInputV1={catalog_entry_id:Id[1..64],binding:DeploymentBindingDecisionInputV1}` |
| binding absent | `deployment_binding` / `deployment-binding` | `atlas:binding-absent:v1`; `BindingAbsentIdentityInputV1={catalog_entry_id:Id[1..64],state:"absent"}` |
| artifact present | `repository_observation` / `repository-observer` | `atlas:artifact-present:v1`; `ArtifactContentIdentityInputV1` defined below |
| artifact absent | same | `atlas:artifact-absent:v1`; `ArtifactAbsentIdentityInputV1={repository_path:RepoPath,service:Id[1..255],state:"missing"}` |
| artifact rejection | same | `atlas:artifact-rejected:v1`; `ArtifactRejectedIdentityInputV1={repository_path:RepoPath|null,service:Id[1..255]|null,state:invalid|unsafe|unknown,reason_code:ArtifactReasonCode}` |
| accepted evidence | `image_release_evidence` / released source ID | evidence identity above |
| rejected/untrusted evidence | `image_release_evidence` / decision `source_id`, else `expected_source_id` | `atlas:evidence-decision:v1`; `EvidenceDecisionInput` |
| compatibility | `compatibility_evaluation` / `compatibility-projector` | `atlas:compatibility-decision:v1`; `CompatibilityDecisionInputV1` |
| prerequisite | `prerequisite_source` / `prerequisite-projector` | `atlas:prerequisite:v1`; the complete `PrerequisiteIdentityInputV1` defined below |
| freshness | `policy_evaluation` / `freshness-policy` | `atlas:freshness:v1`; `FreshnessIdentityInputV1={policy_identity:lowerhex[64],evaluation_instant:UtcSecond,evidence_identity:lowerhex[64],effective_time:UtcSecond,window_seconds:Int[60..31536000],age_seconds:Int[0..315537897599],result:fresh|stale}` |

Artifact rejection `reason_code` is exactly one of `content_size`, `non_utf8`,
`invalid_yaml`, `ambiguous_service`, `containment_escape`, `symlink`,
`non_regular`, or `observation_unknown`.
This closed enum is `ArtifactReasonCode`.

The artifact state/reason relation is one-to-one and exhaustive:

| State | Only allowed reason | Required fields | Blocker / missing fact / status rank |
|---|---|---|---|
| `present` | null | path, service and digest non-null | none |
| `missing` | null | path/service non-null; digest null | `missing_deployment_artifact` / `deployment_artifact` / rank 2 |
| `invalid` | `content_size`, `non_utf8`, `invalid_yaml`, or `ambiguous_service` | digest null; path/service retain the valid catalog binding values | `invalid_deployment_artifact` / `source_fact` / rank 5 |
| `unsafe` | `containment_escape`, `symlink`, or `non_regular` | digest null; path/service retain the valid catalog binding values | `unsafe_deployment_artifact` / `source_fact` / rank 5 |
| `unknown` | `observation_unknown` | digest null; path/service retain only independently valid binding values | `unknown_deployment_artifact` / `deployment_artifact` / rank 5 |

Here and below status rank means the numbered status precedence. A missing
binding produces `artifact.state=unknown`, null path/service/digest,
`observation_unknown`, and the `atlas:artifact-unbound:v1` identity; it does not
invent a repository observation. No reason is accepted by two states and no
state accepts another reason. Present provenance uses content identity, missing
uses absent identity, and invalid/unsafe/unknown uses rejected identity. Every
artifact decision and its provenance identity enter the fingerprint.
An invalid binding path/schema is a catalog adaptation failure and emits no
plan, so lexical path-schema and traversal reasons are deliberately absent from
`ArtifactReasonCode`. `observation_unknown` is emitted only when the bounded
repository observer itself returns its released, valid unknown result; I/O,
partial-read, overflow or unrecognized observer results emit no plan.
Fingerprint binding/artifact identities use the exact named domains and typed
objects in this table;
an absent binding uses `atlas:binding-absent:v1`, and an artifact with no
binding uses `atlas:artifact-unbound:v1` over
`ArtifactUnboundIdentityInputV1={catalog_entry_id:Id[1..64],state:"unknown"}`.

Absence/rejection therefore has adapter identity, not a fake upstream ID.
Clock, contract and internal failures emit no plan and need no provenance.

### Prerequisite projection

Projection consumes only the normalized `requirements`, normalized
`relationships`, and immutable reviewed catalog index used by the catalog
loader; it performs no target, provider, network or host observation. An absent
catalog fact creates no prerequisite. Item-scoped v1 has no environmental
capacity observation, so every environmental row is `unknown`, never
`satisfied` or `missing`.

| Released fact (one prerequisite per normalized fact) | Kind / exact descriptor key | State |
|---|---|---|
| non-null CPU minimum | `platform` / `cpu:<DecimalString>` | `unknown` |
| non-null memory minimum | `platform` / `memory-mb:<Int>` | `unknown` |
| non-null storage minimum | `storage` / `storage-gb:<DecimalString>` | `unknown` |
| `gpu_required=true` | `platform` / `gpu-required` | `unknown` |
| non-null GPU-memory minimum | `platform` / `gpu-memory-gb:<DecimalString>` | `unknown`; false `gpu_required` does not suppress it |
| each capability ID | `platform` / `capability:<Id>` | `unknown` |
| each architecture ID | `platform` / `architecture:<Id>` | `unknown` |
| each operating-system ID | `platform` / `operating-system:<Id>` | `unknown` |
| each runtime ID | `platform` / `runtime:<Id>` | `unknown` |
| each device ID | `platform` / `device:<Id>` | `unknown` |
| each port tuple | `network` / `port:<port>:<protocol>:<direction>:<required>` | `unknown`, including declared `required=false` ports |
| `requires_internet=true` | `network` / `internet-required` | `unknown` |
| `requires_lan=true` | `network` / `lan-required` | `unknown` |
| each `required=true` `depends_on`, `requires`, `runs_on`, or `deployed_by` relationship | `application` / exact relationship tuple | rule below |

An application prerequisite is `satisfied` only when the complete reviewed
catalog index proves exactly one active target whose selected release version
satisfies both inclusive bounds. It is `missing` only when that complete index
proves no target, a non-active target, or a selected version outside a bound.
It is `unknown` when the target exists but a bound cannot be evaluated because
its selected release version is null. Failure to load the complete index is
503/no plan, never a state. All other relationships create no prerequisite but
remain emitted. False GPU/internet/LAN flags, null minima, and empty arrays
create no row. V1 has no operator prerequisite; `operator` MUST NOT be emitted.

For each prerequisite form
`PrerequisiteDescriptorInputV1={kind:storage|network|platform|application,
requirement_key:PlainText[1..192],relationship:RelationshipDecisionInputV1|null}`.
Environmental rows use the exact table key and null relationship; application
uses `requirement_key="relationship"` and the exact relationship.
`prerequisite_id` is the first 64 lowercase hex characters (the whole digest)
of the compound hash under `atlas:prerequisite-id:v1`. Description is fixed
code-owned `PlainText` selected by descriptor kind and excluded from decisions.
`PrerequisiteIdentityInputV1={descriptor:PrerequisiteDescriptorInputV1,
prerequisite:PrerequisiteDecisionInputV1,catalog_identity:lowerhex[64]}`
produces provenance under `atlas:prerequisite:v1`; source, descriptor and state
therefore enter the fingerprint. Sort by `(prerequisite_id,kind,state)`.
More than 64 projected rows is 503/no plan, never truncation. `satisfied` has
no blocker/fact; `missing` creates
`missing_prerequisite` and no missing fact; `unknown` creates
`missing_prerequisite_fact`, missing fact `prerequisite_fact`, and the mandatory
absence fact defined below.

### Assumption and confirmation projection

Assumptions have exactly two allowed typed producers: each environmental
prerequisite in `unknown` state produces kind `environment` and fixed statement
`Target environment must be checked for prerequisite {prerequisite_id}.`;
each `compatibility_warning` risk produces kind `catalog` and fixed statement
`Catalog compatibility warning {subject} requires review.` No prose, metadata,
caller input, missing evidence, or adapter judgment may produce one; `operator`
is unreachable. `AssumptionDescriptorInputV1={kind:catalog|environment,
source_fact_kind:prerequisite_unknown|compatibility_warning,
subject:Id[1..128]}` is compound-hashed under `atlas:assumption-id:v1`; its
64-hex result is `assumption_id`. The descriptor, ID, kind, producing fact and
relations enter the fingerprint; fixed presentation text does not. Assumptions
are server-owned, declarative, non-authorizing and non-executable, and never
synthesize approval, compatibility, target identity, artifact presence, image
identity, or prerequisite satisfaction. With no producer, `assumptions=[]`.

| Confirmation | Exact producer / subject | Fixed prompt-template identity | Relation |
|---|---|---|---|
| `accept_assumption` | every assumption / its `assumption_id` | `atlas:prompt:accept-assumption:v1` | always required |
| `confirm_prerequisite` | every unknown prerequisite / its `prerequisite_id` | `atlas:prompt:confirm-prerequisite:v1` | always required |
| `confirm_risk` | every high/critical risk and every compatibility-warning risk / risk subject | `atlas:prompt:confirm-risk:v1` | always required |

The prompt is fixed code-owned text selected only by template identity and
subject. `(code,subject)` is fingerprinted; prompt text is not. Duplicate pairs
collapse. Other low/medium risks are informational. Every confirmation adds
exactly one same-subject `required_operator_confirmation` blocker and therefore
prevents `plan_ready_for_review`. V1 has no confirmation response or approval
state. With no producer, `required_operator_confirmations=[]`.

## OCI repository normalization

Input is an OCI/Docker name, <=512 ASCII bytes before/after normalization.
Reject surrounding/internal whitespace, controls, schemes, userinfo, query,
fragment, percent encoding and empty components. Split a digest suffix and
accept only lowercase `sha256:` plus 64 lowercase hex. A tag on the last path
component is syntactically accepted, removed from repository identity and
recorded as mutable; it never yields a digest.

The first slash component is a registry exactly when it contains `.` or `:`,
or equals `localhost`; otherwise prepend `docker.io`. Lowercase the hostname;
preserve an explicit decimal port 1..65535, including 80/443. For `docker.io`
with one repository component, prepend `library/`. Repository components are
not case-folded: uppercase is rejected; each matches
`[a-z0-9]+(?:[._-][a-z0-9]+)*`. Registry labels follow lowercase DNS rules or
`localhost`; IPv6 literals are unsupported. Join with `/`. Do no DNS/network,
alias or tag resolution. Released
`ghcr.io/home-assistant/home-assistant` remains exact.

## Image decision projection

Projection consumes only selected catalog `release_version`, normalized
binding, one bounded repository observation, and normalized evidence decisions.
Apply this first-match table; every row excludes all earlier rows.

| State | Exact entry condition | Required consequence |
|---|---|---|
| `conflicted` | an accepted-claim `image_claim` conflict fact exists | `image_conflict` + `source_fact`; reference/digest null; selected release retained |
| `mismatched` | no conflict and an otherwise policy-accepted complete row disagrees with selected item/release or exact observed repository/digest | `image_mismatch` + `accepted_evidence`; retain independently valid observation values |
| `mutable` | no prior state and observation has a valid tag/reference but no immutable digest | `mutable_image_reference` + `immutable_image_identity`; repository may remain, digest null |
| `missing` | no prior state and the observation or evidence proves a required image reference or digest absent | `missing_immutable_image_identity` + `immutable_image_identity`; retain only valid values |
| `untrusted` | no prior state, exact immutable observation exists, matching complete rows exist, every matching row is untrusted/unsupported, and no policy-accepted match exists | `untrusted_evidence` + `accepted_evidence`; retain observation values/release |
| `unknown` | no prior state and exactly one bounded condition holds: selected release null; binding absent; released observer returned `observation_unknown`; or all structurally matching accepted rows are stale so no grounding-eligible fresh row exists | `unknown_image_state` + `immutable_image_identity`; retain only independently valid values |
| `grounded` | selected release, binding, exact immutable observation, and an eligible `accepted_fresh` row all exist and match item/release/repository/digest exactly, with no conflict, mismatch, mutable, missing, untrusted, unknown, stale matching row, or provenance conflict | no image blocker/missing fact; emit exact repository, digest and release |

An unsupported observer result, I/O uncertainty, partial read, overflow, or
combination not represented above is 503/no plan, never `unknown`. No state is
a fallback. State and all retained fields enter the fingerprint.

## Total state, blocker and status mapping

The closed `BlockerCode` enum is:

`missing_deployment_binding`, `missing_deployment_artifact`,
`invalid_deployment_artifact`, `unsafe_deployment_artifact`,
`unknown_deployment_artifact`, `missing_immutable_image_identity`,
`mutable_image_reference`, `untrusted_evidence`, `image_conflict`,
`image_mismatch`, `unknown_image_state`, `missing_accepted_evidence`,
`stale_evidence`, `malformed_evidence`, `provenance_conflict`,
`incompatible_application_environment`, `unknown_compatibility`,
`missing_prerequisite`, `missing_prerequisite_fact`,
`missing_target_identity`,
`required_operator_confirmation`, `malformed_source_fact`.

Image mismatch/conflict never overload provenance conflict. Compatibility
warning is a risk. `unavailable_read_dependency`, `clock_unavailable`,
`schema_mismatch`, and `unsupported_target_context` are not blockers because
those conditions emit no plan.

| State/condition | Exact blocker/result | Missing fact |
|---|---|---|
| artifact present | none | none |
| artifact missing | `missing_deployment_artifact` | `deployment_artifact` |
| artifact invalid | `invalid_deployment_artifact` | `source_fact` |
| artifact unsafe | `unsafe_deployment_artifact` | `source_fact` |
| artifact unknown | `unknown_deployment_artifact` | `deployment_artifact` |
| binding absent | `missing_deployment_binding` | `deployment_binding` |
| image grounded | none | none |
| image missing | `missing_immutable_image_identity` | `immutable_image_identity` |
| image mutable | `mutable_image_reference` | `immutable_image_identity` |
| image untrusted | `untrusted_evidence` | `accepted_evidence` |
| image conflicted | `image_conflict` | `source_fact` |
| image mismatched | `image_mismatch` | `accepted_evidence` |
| image unknown | `unknown_image_state` | `immutable_image_identity` |
| compatibility compatible | none | none |
| compatible with warnings | medium `compatibility_warning` risk + `confirm_risk`, hence confirmation blocker | none |
| compatibility incompatible | `incompatible_application_environment` | none |
| compatibility unknown | `unknown_compatibility` | `compatibility_fact`; also `target_identity` for `target_required` |
| evidence accepted/fresh | none | none |
| evidence accepted/stale | `stale_evidence` | none |
| evidence missing | `missing_accepted_evidence` | `accepted_evidence` |
| evidence untrusted | `untrusted_evidence` | `accepted_evidence` |
| evidence conflicting | provenance disagreement: `provenance_conflict`; image claim disagreement: `image_conflict` | `source_fact` |
| evidence malformed | `malformed_evidence` | `source_fact` |
| optional evidence source unavailable and fully classified | `missing_accepted_evidence` | `source_fact` |
| prerequisite satisfied | none | none |
| prerequisite missing | `missing_prerequisite` | none |
| prerequisite unknown | `missing_prerequisite_fact` | `prerequisite_fact` |
| required target identity unavailable | `missing_target_identity` | `target_identity` |
| caller target selector | **NO PLAN 422** `installation_plan_invalid_request` | n/a |
| classifiable malformed optional fact | `malformed_source_fact` | `source_fact` |
| required read unavailable | **NO PLAN 503** `installation_plan_unavailable` | n/a |
| clock unavailable/invalid | **NO PLAN 503** `installation_plan_clock_unavailable` | n/a |
| schema mismatch/unknown internal enum | **NO PLAN 503** `installation_plan_contract_failure` | n/a |
| timeout/internal exception | **NO PLAN 503** `installation_plan_unavailable` | n/a |

The only typed unavailable fact in v1 is `SourceUnavailableFactInputV1` for a
fully classified optional evidence source. An optional malformed record may
yield a plan only when completely classified into its sanitized decision.
Failure to bound/classify all records or any required loader failure emits no
plan.

Collect every blocker, then derive status: (1) `conflicted` for
`provenance_conflict` or `image_conflict`; (2)
`missing_deployment_artifact`; (3) `incompatible`; (4) `stale_evidence`; (5)
`insufficient_information` for any remaining blocker; (6)
`plan_ready_for_review` for none. Higher status retains all blockers.
`required_operator_confirmation` is added for every confirmation. Grounding
never removes an artifact blocker.

## Raw adaptation and no-plan boundary

Readers return bounded raw bytes or validated released models to narrow
adapters; only adapters construct sanitized facts. Raw malformed values never
enter a plan. Classifiable lexical artifact defects and one optional malformed
evidence record can yield the blockers above. Malformed catalog identity,
binding schema, required compatibility/prerequisite document, cardinality
overflow, partial read, loader I/O failure or adapter schema mismatch prevents
a complete fact set and returns 503/no plan. Unknown valid item returns 404.

A plan is emitted only after every required reader returns a complete bounded
result and every raw value becomes one valid wire fact or fixed sanitized
marker. Timeout/internal exception always returns sanitized 503 with only a
correlation ID. No failure triggers refresh, fallback, legacy planning,
alternate artifact, write or side effect.

## Relationships and compatibility

All ten released relationship kinds are projected losslessly. Consume released
`type`, normalized `target`, `required`, `minimum_version`, and
`maximum_version`; description/metadata never affect readiness. Invalid target
identity makes the required catalog adaptation 503/no plan. Relationships
affect readiness only through an explicit prerequisite or compatibility result.

The compatibility adapter produces exactly one closed
`CompatibilityDecisionInputV1`:

```
CompatibilityDecisionInputV1={
 contract:"installation-plan-compatibility-input-v1",
 item_id:Id[1..64], evaluator_identity:lowerhex[64],
 input_identity:lowerhex[64], source_target_type_present:Bool,
 source_result:compatible|compatible_with_warnings|insufficient_information|
   incompatible|not_available,
 projected_result:compatible|compatible_with_warnings|incompatible|unknown,
 projected_reason:target_free_catalog_compatible|
   target_free_catalog_warning|target_free_catalog_incompatible|
   target_required|compatibility_fact_missing|compatibility_fact_malformed,
 findings:CompatibilityFindingInputV1[0..128],
 unknown_fact_codes:Array<SafeFactCode,0..128>,
 warning_projection:Bool,target_required_projection:Bool
}
CompatibilityFindingInputV1={id:Id[1..128],check_type:capability|resource|
 platform|network|relationship|catalog|version,severity:blocker|warning|info|
 unknown,status:compatible|compatible_with_warnings|insufficient_information|
 incompatible,subject:Id[1..128],evidence_ids:Id[1..64][0..32]}
```

Each compatibility `evidence_ids` value is an array of zero through 32
elements. Each element is an `Id[1..64]`: ASCII lowercase, 1..64 bytes,
matching `[a-z0-9][a-z0-9._:-]*`, with no trimming or case folding. Elements
sort by ascending UTF-8 bytes before hashing or projection; duplicate
normalized elements are a malformed compatibility input and fail according to
the required/optional compatibility boundary. No unbounded evidence-ID array
or free-form evidence value enters v1.
Findings sort by `(id,check_type,severity,status,subject,evidence_ids)`, where
each `evidence_ids` array sorts lexically and participates as its JSON array;
array comparison is element-by-element with the shorter array first when it is
an equal prefix. Unknown fact codes sort lexically. Duplicates fail.
Finding/evidence messages,
requirements, observed values, observed fact values, source prose,
`target_id`, and `checked_at` are excluded: none can affect the item-scoped v1
projection. `source_target_type_present` records only whether a released
target type existed; its value is never copied and never grants authority.

`CompatibilityReleasedInputV1={item_id:Id[1..64],target_type_present:Bool,
status:compatible|compatible_with_warnings|insufficient_information|
incompatible,findings:CompatibilityFindingInputV1[0..128],
unknown_fact_codes:Array<SafeFactCode,0..128>}` is the only released target-scoped
object hashed. `input_identity` is its compound hash under
`atlas:compatibility-released-input:v1`. It intentionally excludes the target
selector and target identity. If the optional compatibility source is known
absent, hash `CompatibilityAbsentInputV1={item_id:Id[1..64],
state:"not_available"}` under `atlas:compatibility-absent-input:v1` instead;
this is the only derivation allowed for `source_result=not_available`.
`CompatibilityEvaluatorIdentityInputV1={contract:
"installation-plan-compatibility-v1",catalog_identity:lowerhex[64],
ruleset_version:1}` is hashed under `atlas:compatibility-evaluator:v1`.
Finally the whole `CompatibilityDecisionInputV1` is hashed under
`atlas:compatibility-decision:v1`; that hash is compatibility provenance's
`immutable_identity`. All three are lowercase hex, use the framing below, and
enter the fingerprint. Missing required inputs produce the typed
`not_available/unknown/compatibility_fact_missing` projection only when a
complete optional absence is known; malformed required input is 503/no plan.

Because every currently released assessment is target-scoped and v1 has no
target, it projects `unknown` / `target_required`, sets
`target_required_projection=true`, `warning_projection=false`, and adds
`unknown_compatibility`, `compatibility_fact`, and `target_identity`. It copies
no target selector, target ID, finding prose, evidence prose, or observed fact.

Only a pure, versioned `installation-plan-compatibility-v1` catalog evaluator
that consumes no target observation may produce a target-free result. This is
the entire projection relation; all other combinations emit no plan:

| source condition | projected result / reason | flags | exact consequence |
|---|---|---|---|
| released assessment has `source_target_type_present=true`, regardless of released status/findings | `unknown` / `target_required` | warning=false, target-required=true | `unknown_compatibility`; missing `compatibility_fact` and `target_identity` |
| pure evaluator `compatible`, no warnings or unknown codes | `compatible` / `target_free_catalog_compatible` | false, false | no blocker/missing fact |
| pure evaluator `compatible_with_warnings`, at least one warning finding, no unknown code | `compatible_with_warnings` / `target_free_catalog_warning` | true, false | medium `compatibility_warning`, `confirm_risk`, and `required_operator_confirmation` |
| pure evaluator `incompatible`, at least one blocker finding, no unknown code | `incompatible` / `target_free_catalog_incompatible` | false, false | `incompatible_application_environment` |
| pure evaluator `insufficient_information` or any nonempty unknown codes | `unknown` / `compatibility_fact_missing` | false, false | `unknown_compatibility`; missing `compatibility_fact` |
| optional compatibility source known absent (`not_available`) | `unknown` / `compatibility_fact_missing` | false, false | `unknown_compatibility`; missing `compatibility_fact` |
| pure evaluator successfully classifies one bounded malformed optional catalog compatibility fact | `unknown` / `compatibility_fact_malformed` | false, false | `unknown_compatibility`; missing `compatibility_fact`; `malformed_source_fact` |

For the final row `source_result=insufficient_information`, findings is empty,
and `unknown_fact_codes=["malformed_optional_compatibility_fact"]`; no malformed
value is retained. A malformed required compatibility document, inconsistent
finding/status cardinality, or any classification uncertainty remains 503/no
plan. Current target-scoped results are never reused by the pure evaluator.

## Freshness

Use one injected server UTC `evaluation_instant` at whole-second precision for
the request and fingerprint it exactly; there is no bucket. Released evidence
uses `attested_at`; `observed_at` is null. For a future shape with both, both
must be valid UTC seconds and `attested_at >= observed_at`; attested takes
precedence. One present timestamp is effective; both null or reversed is
malformed.

Let delta be evaluation minus effective time in integer seconds. Delta 0 has
age 0. Delta -300..-1 is allowed skew and age 0; less than -300 is malformed.
Otherwise age=delta. Fresh iff age <= window: age 0 and exact boundary are
fresh; boundary+1 is stale. Null/malformed produces `malformed_evidence`;
unavailable clock is 503/no plan. Fresh evidence with remaining seconds <=
`floor(window/10)` adds approaching-expiry risk. Evaluation/effective times,
window, age and result are fingerprinted, preventing equal fingerprints across
different freshness decisions.

The maximum nonnegative difference between two valid `UtcSecond` values is
315537897599, so the `age_seconds` bound represents every valid computation.
Subtraction uses exact mathematical integers; overflow, wrap, truncation or
saturation is forbidden. An implementation unable to represent the exact
value returns `installation_plan_contract_failure`/503 and emits no plan.

## Fingerprint input and exact ordering

The complete closed synthetic internal type is below. Every displayed field is
required; only an explicit `|null` permits null. Bounds are inclusive. Every
string uses the wire normalization/bounds of its named type.

```
FingerprintInputV1={
 fingerprint_contract:"installation-plan-fingerprint-v1",
 schema_version:"installation-plan-v1",evaluation_instant:UtcSecond,
 freshness_policy_identity:lowerhex[64],
 application:ApplicationDecisionInputV1,
 catalog:CatalogDecisionFingerprintInputV1,
 binding:BindingDecisionInputV1,artifact:ArtifactDecisionInputV1,
 image:ImageDecisionInputV1,
 evidence_decisions:EvidenceDecisionInput[0..128],
 provenance_decisions:ProvenanceDecisionInputV1[1..256],
 compatibility_decisions:CompatibilityDecisionInputV1[1],
 prerequisites:PrerequisiteDecisionInputV1[0..64],
 relationships:RelationshipDecisionInputV1[0..64],
 assumptions:AssumptionDecisionInputV1[0..32],
 blockers:BlockerDecisionInputV1[0..64],risks:RiskDecisionInputV1[0..32],
 missing_facts:MissingFactDecisionInputV1[0..64],
 confirmations:ConfirmationDecisionInputV1[0..32],
 absence_facts:AbsenceFactInputV1[0..128],
 conflict_facts:ConflictFactInputV1[0..128],
 source_unavailable_facts:SourceUnavailableFactInputV1[0..32],
 freshness_decisions:FreshnessDecisionInputV1[0..128]
}
ApplicationDecisionInputV1={item_id:Id[1..64],catalog_entry_id:Id[1..64],
 release_version:Version|null}
CatalogDecisionFingerprintInputV1={catalog_identity:lowerhex[64],
 catalog_source_identity:lowerhex[64],decision:CatalogDecisionInputV1}
BindingDecisionInputV1={state:present|absent,
 repository_path:RepoPath|null,service:Id[1..255]|null,
 identity:lowerhex[64]}
ArtifactDecisionInputV1={state:present|missing|invalid|unsafe|unknown,
 repository_path:RepoPath|null,service:Id[1..255]|null,
 content_digest:Sha256Digest|null,reason_code:content_size|non_utf8|
 invalid_yaml|ambiguous_service|containment_escape|symlink|non_regular|
 observation_unknown|null,identity:lowerhex[64]}
ImageDecisionInputV1={state:grounded|missing|mutable|untrusted|conflicted|
 mismatched|unknown,reference:OciRepository|null,digest:Sha256Digest|null,
 release_version:Version|null}
ProvenanceDecisionInputV1={claim:Id[1..128],source_class:curated_catalog|
 deployment_binding|repository_observation|image_release_evidence|
 compatibility_evaluation|prerequisite_source|policy_evaluation,
 source_id:SafeSourceId[1..256],immutable_identity:lowerhex[64],
 observed_at:UtcSecond|null,attested_at:UtcSecond|null}
PrerequisiteDecisionInputV1={prerequisite_id:Id[1..64],kind:storage|network|
 platform|application|operator,state:satisfied|missing|unknown,
 descriptor:PrerequisiteDescriptorInputV1}
AssumptionDecisionInputV1={assumption_id:Id[1..64],kind:catalog|environment|
 operator,source_fact_kind:prerequisite_unknown|compatibility_warning,
 subject:Id[1..128]}
BlockerDecisionInputV1={code:BlockerCode,subject:Id[1..128]}
RiskDecisionInputV1={code:artifact_content_change|evidence_approaching_expiry|
 environment_variance|compatibility_warning,severity:low|medium|high|critical,
 subject:Id[1..128]}
MissingFactDecisionInputV1={code:deployment_binding|deployment_artifact|
 immutable_image_identity|accepted_evidence|prerequisite_fact|target_identity|
 compatibility_fact|source_fact,subject:Id[1..128]}
ConfirmationDecisionInputV1={code:accept_assumption|confirm_prerequisite|
 confirm_risk,subject:Id[1..128],prompt_template_id:SafeSourceId[1..64]}
AbsenceFactInputV1={kind:deployment_binding|deployment_artifact|
 evidence_record|compatibility_fact|prerequisite_fact,subject:Id[1..128],
 source_id:SafeSourceId[1..256],identity:lowerhex[64]}
ConflictFactInputV1={kind:image_claim|provenance_identity|immutable_identity,
 subject:Id[1..128],left_identity:lowerhex[64],right_identity:lowerhex[64]}
SourceUnavailableFactInputV1={kind:optional_evidence_source,
 subject:Id[1..128],expected_source_id:SafeSourceId[1..256],
 reason_code:"source_read_unavailable",identity:lowerhex[64]}
FreshnessDecisionInputV1={evidence_identity:lowerhex[64],
 effective_time:UtcSecond,window_seconds:Int[60..31536000],
 age_seconds:Int[0..315537897599],result:fresh|stale}
```

Binding null combinations are exact: present requires both path/service;
absent requires both null. Invalid binding schema is a required catalog
adaptation failure and returns 503/no plan, so it has no fingerprint state.
Artifact present requires path/service/digest and null reason; missing requires
path/service, null digest/reason; invalid/unsafe/unknown requires null digest
and non-null reason. `AbsenceIdentityInputV1={kind:deployment_binding|
deployment_artifact|evidence_record|compatibility_fact|prerequisite_fact,
subject:Id[1..128],source_id:SafeSourceId[1..256]}` produces an absence fact's
`identity` under `atlas:absence-fact:v1`.
`SourceUnavailableIdentityInputV1={kind:"optional_evidence_source",
subject:Id[1..128],expected_source_id:SafeSourceId[1..256],
reason_code:"source_read_unavailable"}` produces its `identity` under
`atlas:optional-source-unavailable:v1`.

Absence facts are mandatory, never optional implementation choices:

| Condition | Kind / subject / source ID | Blocker and missing-fact relation |
|---|---|---|
| catalog `deployment_binding=null` | `deployment_binding` / catalog entry ID / `deployment-binding` | exactly the binding blocker and `deployment_binding` missing fact |
| bound repository observation is `missing` | `deployment_artifact` / binding service / `repository-observer` | exactly the artifact blocker and `deployment_artifact` missing fact |
| an expected evidence observation is `absent` | `evidence_record` / catalog item ID / observation `expected_source_id` | exactly `missing_accepted_evidence` and `accepted_evidence` for that decision |
| compatibility projects `compatibility_fact_missing`, including target-required or known-absent optional input | `compatibility_fact` / catalog item ID / `compatibility-projector` | exactly `unknown_compatibility` and `compatibility_fact` |
| a prerequisite state is `unknown` | `prerequisite_fact` / prerequisite ID / `prerequisite-projector` | exactly `missing_prerequisite_fact` and `prerequisite_fact` |

No absence fact is emitted for malformed, unsafe, conflicted, stale, untrusted
or unavailable-source conditions. Each row constructs the exact
`AbsenceIdentityInputV1` and its domain hash; it is included in the fingerprint
and sorted by the declared absence tuple. If a row condition holds, omission or
duplication is a contract failure and emits no plan.

Conflict facts are likewise mandatory and exhaustive:

| Condition | Kind / subject | Left and right identity source | Blocker/status |
|---|---|---|---|
| two otherwise policy-accepted, independently valid rows in one `(subject,claim,release_version)` group have unequal `(image_reference,image_digest)` | `image_claim` / evidence subject | their distinct `immutable_identity` values | `image_conflict`; conflicted |
| two `image_release_evidence` provenance decisions share `(claim,source_class,source_id)` but have different immutable identities | `provenance_identity` / shared claim | the two provenance immutable identities | `provenance_conflict`; conflicted |
| two unequal complete evidence identity-input objects derive the same `immutable_identity` | `immutable_identity` / shared subject | distinct hashes of the two complete `EvidenceDecisionInput` objects under `atlas:evidence-decision:v1`, ordered lexically | `provenance_conflict`; conflicted |

Exact duplicate complete identity inputs collapse before conflict construction. For every unordered
conflicting pair, require one fact, order its two distinct identities so
`left_identity < right_identity`, then sort facts by the declared conflict
tuple. Each fact and both side identities enter the fingerprint. Conflict facts
have no separate synthetic identity. A conflict blocker without all required
pair facts, or a fact without its blocker, is a contract failure/no plan.
There is no server-derived target in v1, so target ambiguity cannot be produced;
caller target selectors are prevented at the route boundary and never become a
plan fact or blocker.

Required-source unavailability and all other no-plan failures have no fact and
no fingerprint.

Every compound identity in this contract uses exactly
`SHA-256(UTF8(domain_label) || 0x00 || UTF8(RFC8785-JCS(typed_object)))`, where
the domain label is ASCII without NUL, the object is its named closed type,
strings are NFC before JCS, and the result is lowercase hex. This rule applies
to catalog source/decision, binding, repository artifact, evidence,
compatibility evaluator/input/decision, prerequisite, freshness, absence,
and optional-unavailability identities. Delimiter concatenation is
never used. Repository artifact content identity uses
`ArtifactContentIdentityInputV1={repository_path:RepoPath,
service:Id[1..255],content_digest:Sha256Digest}` under
`atlas:artifact-content:v1`; missing/rejected identities use the exact typed
objects already listed in the provenance table. No secrets/raw payloads,
absolute paths, exceptions, commands, executable content, or presentation text
appear.

Arrays sort ascending by these exact tuples; null precedes non-null, false
precedes true, strings compare by UTF-8 bytes, and enum fields use the written
declaration order above: emitted accepted evidence `(subject,claim,
source_class,source_id,immutable_identity,evidence_id,attested_at)`; emitted
provenance `(claim,source_class,source_id,immutable_identity,observed_at,
attested_at)`; emitted compatibility `(environment,result,reason_code)`;
emitted prerequisites `(prerequisite_id,kind,state)`;
relationships `(kind,item_id,required,minimum_version,maximum_version)`;
assumptions `(assumption_id,kind)`; blockers `(code,subject)`, with `code`
ranked by its exact `BlockerCode` declaration order; risks `(severity,code,
subject)`, with severity ranks critical=0, high=1, medium=2, low=3 and code in
its declaration order; missing facts `(code,subject)`;
confirmations `(code,subject)`; evidence decisions `(expected_source_id,
source_class,subject,claim,release_version,image_reference,image_digest,
source_id,immutable_identity,evidence_id,disposition,eligibility,reason_code,
attested_at,freshness_window_seconds)`; provenance decisions `(claim,
source_class,source_id,immutable_identity,observed_at,attested_at)`;
compatibility decisions `(item_id,evaluator_identity,input_identity,
projected_result,projected_reason)`; compatibility findings use their tuple
defined above; absence facts `(kind,subject,source_id,identity)`; conflict facts
`(kind,subject,left_identity,right_identity)` after requiring
`left_identity < right_identity`; source-unavailable facts
`(kind,subject,expected_source_id,reason_code,identity)`; freshness decisions
`(evidence_identity,effective_time,window_seconds,age_seconds,result)`.
Catalog requirement subarrays use the catalog tuples above. Every array in the
wire schema and fingerprint is covered by this paragraph or its named type;
duplicate total tuples are rejected.

Apply RFC 8785 JCS after NFC, strict validation, duplicate rejection and these
sorts. SHA-256 hashes UTF-8 canonical bytes to lowercase hex. Exclude the
fingerprint object, derived status, display text, transport/correlation data.
Equality is only a comparison hint, never authority or persistence/replay key.

## HTTP, dependency and legacy isolation

P3 adds exactly `GET /api/v1/discovery/items/{item_id}/installation-plan`.
Allowed query parameters are empty. A route guard examines the raw query
multi-dict before dependencies and rejects any parameter—including duplicate,
empty and encoded aliases—with sanitized 422. It bounded-reads the request
stream before assembly; any body byte or declared nonzero/invalid transfer body
is 422. No caller evidence/artifact/source fact is accepted. `item_id` matches
`[a-z0-9]+(?:-[a-z0-9]+)*`, length 1..64: malformed=422; unknown valid=404
`installation_plan_item_not_found`. Framework defaults are not proof. Other
methods are 405; there is no mutation sibling.

Required isolated stack:

`app.installation_plan.contract` (pure models/canonicalization) ->
`app.installation_plan.evaluator` (pure evaluator/assembler) ->
`app.installation_plan.adapters` (narrow reads) ->
`app.routes.installation_plan` (isolated GET).

Adapters may wrap `app.discovery.models`, `app.discovery.loader`,
`app.discovery.repository`, `app.discovery.repository_compose_observation`,
`app.discovery.image_release_evidence_loader`, and pure compatibility types/
functions. The broad `app.routes.discovery` is not imported. FastAPI,
Pydantic, standard hash/time/path, logging/sanitization, basic configuration and
read-only dependency wiring/shared factory are allowed only when resolving a
named adapter.

Structural tests start at all four exact modules, resolve the transitive static
graph and reject dynamic imports. The exact forbidden import-prefix set is:
`app.actions`, `app.deploy`, `app.planning`, `app.application`,
`app.execution_candidates`, `app.provider_intents`,
`app.operational_dispatch`, `app.routes.analysis`,
`app.routes.execution_candidate_intake`, `app.routes.execution_candidates`,
`app.routes.internal_operational_actions`,
`app.routes.provider_intent_mutation`, `app.services.execution_candidate_intake`,
`app.services.execution_candidates`, `app.core.restore_interlock`,
`app.discovery.image_release_collector`,
`app.discovery.image_release_collector_transport`,
`app.discovery.home_assistant_ghcr_acquisition`, and
`app.discovery.home_assistant_sigstore_verifier`. Cross-service resolution also
rejects the Atlas Agent roots `app.approval`, `app.repository`, and
`app.workflow`, and the execution worker root `atlas_execution_worker` (which
contains relay, runner, workspace and durable-ledger surfaces). Operational
dispatch auth and sandbox/staging remain covered by `app.operational_dispatch`.
Provider backup/restore paths are already covered by `app.provider_intents`;
legacy deployment/application planning is covered by `app.deploy`,
`app.planning`, and `app.application`. This list uses the released plural
package names; nonexistent singular aliases are not substitutes. Tests also
spy on mutation/network/queue/worker/repository-write/legacy planner entry
points. Allowed adapters cannot import a forbidden prefix. Safe framework
primitives remain allowed as described above.

Repository evidence mounts legacy `POST /analysis/deployments` and
`POST /api/v1/analysis/deployments`. Both remain isolated. InstallationPlan
shares no deployment documents, proposal models, generated steps,
`approval_required`, deploy/planning services or legacy UI semantics. Harmless
FastAPI/Pydantic/logging/sanitization/config primitives may be shared. Neither
legacy route is expanded, called or translated.

## Payload, security and validation

The schema is the allowlist. Arbitrary maps, raw provider data, URLs,
credentials/secrets/cookies/keys/auth, commands, argv, scripts, hooks,
environment values, executable paths, interpolation and opaque payloads are
forbidden. Classification occurs before model/fingerprint/log/UI. Errors/logs
contain fixed codes, sanitized IDs and correlation ID only. UI uses escaped
text nodes, no HTML/Markdown/link/action controls.

P1–P5 tests must cover every total-mapping row and blocker/status precedence;
schema/bounds/null/order; derivation golden vectors; all source classes/no trust
promotion; raw/no-plan boundary; provenance domains; every relationship;
target-scoped compatibility refusal and all target-free results; freshness age
0/boundary/+1/future 0..300/>300/null/malformed/both timestamps; fingerprint
goldens/permutations; OCI host/path/port/default/tag/digest/rejections; exact
HTTP query/body/item behavior; transitive dependency and both legacy mounts;
no persistence/network/mutation; escaped read-only UI; authority regressions.

For released Home Assistant, item `home-assistant`, catalog entry
`d5-home-assistant`, binding `compose/home-assistant.yaml`, and service
`home-assistant` remain exact. The artifact is absent; required current status
is `missing_deployment_artifact` with that blocker regardless of grounding. An
absent file is not parsed, substituted or synthesized.

P0 completion freezes decisions only. P1–P5 implementation remains pending.
