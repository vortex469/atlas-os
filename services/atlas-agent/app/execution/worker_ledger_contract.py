"""Pure validation shared by live worker state and private diagnostic exports."""
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.execution.worker_contracts import WorkerExecutionResult
from app.execution.worker_json import decode_worker_json

LEDGER_COLUMNS = frozenset({'execution_request_id','request_digest','schema_version','state','created_at','updated_at','attempt','execution_started_at','workspace_token','result_json'})
STATES = frozenset({'claimed','executing','completed','failed_terminal','unknown_outcome'})
TERMINAL = frozenset({'completed','failed_terminal','unknown_outcome'})


def _timestamp(value: Any) -> None:
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError('invalid ledger timestamp')
    if datetime.fromisoformat(value).tzinfo is None:
        raise ValueError('ambiguous ledger timestamp')


def validate_worker_ledger_row(row: Mapping[str, Any]) -> WorkerExecutionResult | None:
    if set(row) != LEDGER_COLUMNS:
        raise ValueError('unsupported worker ledger fields')
    identity = row['execution_request_id']
    digest = row['request_digest']
    if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,255}', identity):
        raise ValueError('invalid worker ledger identity')
    if not isinstance(digest, str) or not re.fullmatch(r'execution-request-digest-v1:[0-9a-f]{64}', digest):
        raise ValueError('invalid worker ledger digest')
    if type(row['schema_version']) is not int or row['schema_version'] != 1 or type(row['attempt']) is not int or row['attempt'] != 1:
        raise ValueError('unsupported worker ledger version or attempt')
    state = row['state']
    if not isinstance(state, str) or state not in STATES:
        raise ValueError('invalid worker ledger state')
    _timestamp(row['created_at'])
    _timestamp(row['updated_at'])
    started = row['execution_started_at']
    if started is not None:
        _timestamp(started)
    if (state == 'claimed' and started is not None) or (state in {'executing','unknown_outcome'} and started is None):
        raise ValueError('worker start marker mismatch')
    token = row['workspace_token']
    if token is not None and (not isinstance(token, str) or not token or len(token) > 1024 or '\x00' in token):
        raise ValueError('invalid worker workspace reference')
    raw = row['result_json']
    if state not in TERMINAL:
        if raw is not None:
            raise ValueError('nonterminal worker row has a result')
        return None
    if not isinstance(raw, str) or len(raw) > 24 * 1024 * 1024:
        raise ValueError('terminal worker row has no bounded result')
    result = WorkerExecutionResult.from_dict(decode_worker_json(raw))
    if result.execution_request_id != identity:
        raise ValueError('worker result identity mismatch')
    expected = 'completed' if result.status.value == 'succeeded' else 'unknown_outcome' if result.status.value == 'unknown' else 'failed_terminal'
    if state != expected:
        raise ValueError('worker result and ledger state mismatch')
    return result
