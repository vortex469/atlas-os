from unittest.mock import Mock

import pytest
from app.execution.worker_contracts import WorkerAttestation
from asgi_test_client import ASGITestClient
from atlas_execution_worker.api import create_app
from atlas_execution_worker.durable_ledger import DurableRequestLedger
from atlas_execution_worker.isolation import IsolationUnavailable, from_observations
from atlas_execution_worker.runner import WorkspaceExecutionRunner
from test_worker import make_request


def observations(**changes):
    values = {'uid':10001,'gid':10001,'readonly':True,'status':'NoNewPrivs:\t1\nCapEff:\t0000000000000000\n'}
    values.update(changes)
    return values


def test_safe_observations_are_reported_without_inventing_runtime():
    result = from_observations(**observations())
    result.validate()
    assert result.runtime_uid == 10001
    assert result.effective_capabilities == '0000000000000000'
    assert result.sandbox_profile == 'atlas-workspace-observed'
    assert 'runsc' not in result.sandbox_profile


@pytest.mark.parametrize('changes', [{'uid':0},{'gid':0},{'readonly':False},{'status':'NoNewPrivs: 0\nCapEff: 0\n'},{'status':'NoNewPrivs: 1\nCapEff: 1\n'},{'status':''},{'status':'NoNewPrivs: 1\nNoNewPrivs: 1\nCapEff: 0\n'}])
def test_unsafe_or_missing_observations_are_refused(changes):
    with pytest.raises(IsolationUnavailable):
        from_observations(**observations(**changes))


def test_unsafe_runtime_refused_before_claim_or_workspace(tmp_path):
    manager = Mock()
    def unsafe():
        raise IsolationUnavailable('not proven')
    runner = WorkspaceExecutionRunner(manager, enabled=True, attestation_provider=unsafe)
    ledger = DurableRequestLedger(tmp_path/'ledger.sqlite3')
    client = ASGITestClient(create_app(durable_ledger=ledger,execution_enabled=True,runners={'repository-token-1':runner}))
    response = client.post('/v1/executions', json=make_request().to_dict())
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'sandbox_unavailable'
    assert len(ledger) == 0
    manager.prepare.assert_not_called()


def test_result_contract_refuses_nonzero_capabilities():
    with pytest.raises(ValueError, match='must be zero'):
        WorkerAttestation(10001,True,True,'0000000000000001','confined').validate()


def test_isolation_loss_after_claim_remains_unexecuted_and_not_replayed(tmp_path):
    manager = Mock()
    calls = []
    def observe():
        calls.append(1)
        if len(calls) > 1:
            raise IsolationUnavailable('isolation changed')
        return from_observations(**observations())
    runner = WorkspaceExecutionRunner(manager, enabled=True, attestation_provider=observe)
    ledger = DurableRequestLedger(tmp_path/'ledger.sqlite3')
    client = ASGITestClient(create_app(durable_ledger=ledger,execution_enabled=True,runners={'repository-token-1':runner}))
    request = make_request()
    assert client.post('/v1/executions', json=request.to_dict()).status_code == 503
    assert len(ledger) == 1
    assert ledger.get(request.execution_request_id).state == 'executing'
    assert client.post('/v1/executions', json=request.to_dict()).status_code == 503
    assert ledger.get(request.execution_request_id).attempt == 1
    manager.prepare.assert_not_called()


def test_kernel_query_can_substantiate_omitted_proc_field():
    result = from_observations(**observations(status='CapEff: 0000000000000000\n'), no_new_privileges=True)
    assert result.no_new_privileges is True


@pytest.mark.parametrize('kernel', [None, False])
def test_omitted_proc_field_without_safe_kernel_query_is_refused(kernel):
    with pytest.raises(IsolationUnavailable):
        from_observations(**observations(status='CapEff: 0000000000000000\n'), no_new_privileges=kernel)


def test_conflicting_kernel_and_proc_privilege_observations_are_refused():
    with pytest.raises(IsolationUnavailable):
        from_observations(**observations(), no_new_privileges=False)


@pytest.mark.parametrize('safe', [False, True])
def test_health_observation_does_not_claim_execute_or_cache(tmp_path, safe):
    manager = Mock()
    def observe():
        if not safe:
            raise IsolationUnavailable('not proven')
        return from_observations(**observations())
    runner = WorkspaceExecutionRunner(manager, enabled=True, attestation_provider=observe)
    ledger = DurableRequestLedger(tmp_path/'ledger.sqlite3')
    client = ASGITestClient(create_app(durable_ledger=ledger,execution_enabled=True,runners={'repository-token-1':runner}))
    report = client.get('/health').json()
    assert report['execution_enabled'] is True
    assert report['execution_readiness']['isolation_observed_safe'] is safe
    assert report['execution_readiness']['full_readiness_proven'] is False
    assert report['execution_readiness']['activation_authorized'] is False
    assert runner._attestation is None
    assert len(ledger) == 0
    manager.prepare.assert_not_called()
