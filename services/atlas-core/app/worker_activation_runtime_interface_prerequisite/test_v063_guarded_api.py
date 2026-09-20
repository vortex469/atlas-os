"""v0.63 retains the guarded API without enabling its production composition."""

import pytest

from . import contract as c
from . import test_contract as p1
from .service import create_worker_activation_runtime_interface_prerequisite_service
from .store import WorkerActivationRuntimeInterfacePrerequisiteStore
from .test_service_store import (
    Clock,
    Reader,
    admission_facts,  # noqa: F401
    counts,
    create,
    plan_facts,  # noqa: F401
    prior_facts,  # noqa: F401
    review_facts,  # noqa: F401
)


@pytest.fixture(scope="module")
def facts(request):
    return p1.facts.__wrapped__(request)


def test_v063_factory_is_default_off_and_side_effect_free(tmp_path, facts):
    journal = WorkerActivationRuntimeInterfacePrerequisiteStore(
        tmp_path / "v057.sqlite"
    )
    reader = Reader(facts)
    service = create_worker_activation_runtime_interface_prerequisite_service(
        prerequisite_reader=reader,
        store=journal,
        clock=Clock(facts),
    )

    result = create(service, facts)

    assert isinstance(
        result, c.WorkerActivationRuntimeInterfacePrerequisiteRedactedErrorV1
    )
    assert result.error_code == "installation_capability_unsupported"
    assert result.retryable is False
    assert reader.calls == 0
    assert counts(journal) == (0, 0, 0)
