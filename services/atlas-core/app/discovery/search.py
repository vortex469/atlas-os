from __future__ import annotations

import re
from collections.abc import Iterable
from typing import TYPE_CHECKING

from pydantic import Field, field_validator

from app.discovery.models import (
    CapabilityReference,
    CatalogEntry,
    DiscoveryCenterModel,
    DiscoveryItem,
    DiscoveryItemStatus,
    DiscoveryItemType,
    DiscoveryRelationshipType,
)

if TYPE_CHECKING:
    from app.discovery.repository import DiscoveryRepository

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class SearchWeights(DiscoveryCenterModel):
    """Named deterministic search ranking weights."""

    exact_item_id: int = 1000
    exact_name: int = 900
    exact_alias: int = 850
    item_id_prefix: int = 700
    name_prefix: int = 650
    exact_capability: int = 600
    exact_tag: int = 550
    name_token: int = 400
    description_token: int = 200
    alias_tag_capability_token: int = 150


DEFAULT_SEARCH_WEIGHTS = SearchWeights()


class DiscoverySearchQuery(DiscoveryCenterModel):
    """Deterministic Discovery Center search and filter query."""

    text: str = ""
    item_types: tuple[DiscoveryItemType, ...] = ()
    statuses: tuple[DiscoveryItemStatus, ...] = ()
    tags: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    relationship_types: tuple[DiscoveryRelationshipType, ...] = ()
    relationship_targets: tuple[str, ...] = ()
    limit: int | None = Field(default=None, ge=1)

    @field_validator("text", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("tags", "capabilities", "relationship_targets", mode="before")
    @classmethod
    def normalize_string_filters(cls, value: object) -> tuple[str, ...] | object:
        return normalize_unique_values(value)


class DiscoverySearchEvidence(DiscoveryCenterModel):
    """Explanation for one deterministic search ranking contribution."""

    field: str = Field(min_length=1)
    value: str = Field(min_length=1)
    matched_text: str = Field(min_length=1)
    match_type: str = Field(min_length=1)
    score: int = Field(ge=0)


class DiscoverySearchResult(DiscoveryCenterModel):
    """One deterministic Discovery Center search result."""

    item: DiscoveryItem
    entry: CatalogEntry
    score: int = Field(ge=0)
    evidence: tuple[DiscoverySearchEvidence, ...] = ()


class SearchDocument(DiscoveryCenterModel):
    """Private pre-normalized searchable projection for a catalog entry."""

    item_id: str
    name: str
    aliases: tuple[str, ...]
    tags: tuple[str, ...]
    capabilities: tuple[str, ...]
    description_tokens: tuple[str, ...]
    name_tokens: tuple[str, ...]
    alias_tokens: tuple[str, ...]
    tag_tokens: tuple[str, ...]
    capability_tokens: tuple[str, ...]


def build_search_document(entry: CatalogEntry) -> SearchDocument:
    """Build a normalized immutable search projection for one entry."""

    item = entry.item
    aliases = tuple(normalize_text(alias) for alias in item.aliases)
    tags = tuple(normalize_text(tag) for tag in item.tags)
    capabilities = tuple(_capability_id(capability) for capability in item.capabilities)
    return SearchDocument(
        item_id=normalize_text(item.id),
        name=normalize_text(item.name),
        aliases=aliases,
        tags=tags,
        capabilities=capabilities,
        description_tokens=tokenize(item.description),
        name_tokens=tokenize(item.name),
        alias_tokens=_tokens_for_values(aliases),
        tag_tokens=_tokens_for_values(tags),
        capability_tokens=_tokens_for_values(capabilities),
    )


def search_repository(
    repository: DiscoveryRepository,
    query: DiscoverySearchQuery,
    *,
    weights: SearchWeights = DEFAULT_SEARCH_WEIGHTS,
) -> tuple[DiscoverySearchResult, ...]:
    """Run deterministic local search over a Discovery repository."""

    results: list[DiscoverySearchResult] = []
    query_tokens = tokenize(query.text)

    for entry in repository.filter(query):
        document = repository.search_document(entry.item.id)
        score, evidence = score_document(document, entry, query_tokens, weights=weights)
        if query_tokens and not evidence:
            continue
        results.append(
            DiscoverySearchResult(
                item=entry.item,
                entry=entry,
                score=score,
                evidence=evidence,
            ),
        )

    results.sort(key=lambda result: (-result.score, result.entry.item.id))
    if query.limit is not None:
        results = results[: query.limit]
    return tuple(results)


def score_document(
    document: SearchDocument,
    entry: CatalogEntry,
    query_tokens: tuple[str, ...],
    *,
    weights: SearchWeights = DEFAULT_SEARCH_WEIGHTS,
) -> tuple[int, tuple[DiscoverySearchEvidence, ...]]:
    """Score one normalized document for a tokenized text query."""

    if not query_tokens:
        return 0, ()

    evidence: list[DiscoverySearchEvidence] = []
    for token in query_tokens:
        token_evidence = _best_evidence_for_token(document, entry, token, weights)
        if token_evidence is None:
            return 0, ()
        evidence.append(token_evidence)

    exact_phrase = normalize_text(" ".join(query_tokens))
    phrase_evidence = _phrase_evidence(document, entry, exact_phrase, weights)
    if phrase_evidence is not None:
        evidence.insert(0, phrase_evidence)

    total_score = sum(item.score for item in evidence)
    return total_score, tuple(evidence)


def normalize_text(value: str) -> str:
    """Normalize searchable text consistently."""

    return value.strip().lower()


def tokenize(value: str) -> tuple[str, ...]:
    """Tokenize normalized search text."""

    return tuple(_TOKEN_PATTERN.findall(normalize_text(value)))


def normalize_unique_values(value: object) -> tuple[str, ...] | object:
    """Normalize query string filters and reject duplicates."""

    if value is None:
        return ()
    if isinstance(value, str):
        values = (value,)
    else:
        try:
            values = tuple(value)  # type: ignore[arg-type]
        except TypeError:
            return value

    normalized: list[str] = []
    for candidate in values:
        if not isinstance(candidate, str):
            raise TypeError("filter values must be strings.")
        normalized_value = normalize_text(candidate)
        if not normalized_value:
            raise ValueError("filter values must not be empty.")
        normalized.append(normalized_value)

    if len(normalized) != len(set(normalized)):
        raise ValueError("filter values must be unique.")
    return tuple(normalized)


def _best_evidence_for_token(
    document: SearchDocument,
    entry: CatalogEntry,
    token: str,
    weights: SearchWeights,
) -> DiscoverySearchEvidence | None:
    candidates: list[DiscoverySearchEvidence] = []
    item = entry.item

    if token == document.item_id:
        candidates.append(
            _evidence("item.id", item.id, token, "exact", weights.exact_item_id),
        )
    if token == document.name:
        candidates.append(_evidence("name", item.name, token, "exact", weights.exact_name))
    for alias, normalized_alias in zip(item.aliases, document.aliases, strict=True):
        if token == normalized_alias:
            candidates.append(_evidence("alias", alias, token, "exact", weights.exact_alias))
    if document.item_id.startswith(token) and token != document.item_id:
        candidates.append(
            _evidence("item.id", item.id, token, "prefix", weights.item_id_prefix),
        )
    if document.name.startswith(token) and token != document.name:
        candidates.append(_evidence("name", item.name, token, "prefix", weights.name_prefix))
    for capability in item.capabilities:
        capability_id = _capability_id(capability)
        if token == capability_id:
            candidates.append(
                _evidence("capability", capability.id, token, "exact", weights.exact_capability),
            )
    for tag, normalized_tag in zip(item.tags, document.tags, strict=True):
        if token == normalized_tag:
            candidates.append(_evidence("tag", tag, token, "exact", weights.exact_tag))
    if token in document.name_tokens:
        candidates.append(_evidence("name", item.name, token, "token", weights.name_token))
    if token in document.description_tokens:
        candidates.append(
            _evidence("description", item.description, token, "token", weights.description_token),
        )
    if token in document.alias_tokens:
        candidates.append(_evidence("alias", ", ".join(item.aliases), token, "token", weights.alias_tag_capability_token))
    if token in document.tag_tokens:
        candidates.append(_evidence("tag", ", ".join(item.tags), token, "token", weights.alias_tag_capability_token))
    if token in document.capability_tokens:
        candidates.append(
            _evidence(
                "capability",
                ", ".join(capability.id for capability in item.capabilities),
                token,
                "token",
                weights.alias_tag_capability_token,
            ),
        )

    if not candidates:
        return None
    return max(candidates, key=lambda candidate: (candidate.score, candidate.field))


def _phrase_evidence(
    document: SearchDocument,
    entry: CatalogEntry,
    exact_phrase: str,
    weights: SearchWeights,
) -> DiscoverySearchEvidence | None:
    item = entry.item
    if exact_phrase == document.item_id:
        return _evidence("item.id", item.id, exact_phrase, "exact", weights.exact_item_id)
    if exact_phrase == document.name:
        return _evidence("name", item.name, exact_phrase, "exact", weights.exact_name)
    for alias, normalized_alias in zip(item.aliases, document.aliases, strict=True):
        if exact_phrase == normalized_alias:
            return _evidence("alias", alias, exact_phrase, "exact", weights.exact_alias)
    if document.item_id.startswith(exact_phrase) and exact_phrase != document.item_id:
        return _evidence("item.id", item.id, exact_phrase, "prefix", weights.item_id_prefix)
    if document.name.startswith(exact_phrase) and exact_phrase != document.name:
        return _evidence("name", item.name, exact_phrase, "prefix", weights.name_prefix)
    return None


def _evidence(
    field: str,
    value: str,
    matched_text: str,
    match_type: str,
    score: int,
) -> DiscoverySearchEvidence:
    return DiscoverySearchEvidence(
        field=field,
        value=value,
        matched_text=matched_text,
        match_type=match_type,
        score=score,
    )


def _capability_id(capability: CapabilityReference) -> str:
    return normalize_text(capability.id)


def _tokens_for_values(values: Iterable[str]) -> tuple[str, ...]:
    tokens: list[str] = []
    for value in values:
        tokens.extend(tokenize(value))
    return tuple(sorted(set(tokens)))
