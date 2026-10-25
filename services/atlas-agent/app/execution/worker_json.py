"""Strict, dependency-free JSON decoding shared by worker protocol peers."""
import json
from typing import Any


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate worker JSON field')
        result[key] = value
    return result


def _nonfinite(value: str):
    raise ValueError('non-finite worker JSON number')


def decode_worker_json(raw: bytes | bytearray | str) -> dict[str, Any]:
    text = raw if isinstance(raw, str) else raw.decode('utf-8')
    result = json.loads(text, object_pairs_hook=_object, parse_constant=_nonfinite)
    if not isinstance(result, dict):
        raise TypeError('worker JSON payload must be an object')
    return result
