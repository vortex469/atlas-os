from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError
from pydantic import ValidationError

from app.operator_auth.models import OperatorCredential, OperatorCredentialFile


class OperatorCredentialError(RuntimeError):
    """Private verifier configuration is unsafe or invalid."""


class OperatorCredentialVerifier:
    def __init__(self, verifier_path: str | Path) -> None:
        self._path = Path(verifier_path)
        self._hasher = PasswordHasher()
        self._operators = self._load()
        self._dummy_hash = self._hasher.hash(os.urandom(32))

    def _load(self) -> dict[str, OperatorCredential]:
        try:
            file_stat = self._path.lstat()
        except OSError as error:
            raise OperatorCredentialError("operator credential verifier is unavailable") from error
        if stat.S_ISLNK(file_stat.st_mode) or not stat.S_ISREG(file_stat.st_mode):
            raise OperatorCredentialError("operator credential verifier must be a regular non-symlink file")
        if stat.S_IMODE(file_stat.st_mode) != 0o400:
            raise OperatorCredentialError("operator credential verifier must have mode 0400")
        if file_stat.st_uid != os.geteuid():
            raise OperatorCredentialError("operator credential verifier must be owned by the runtime user")
        try:
            decoded = json.loads(self._path.read_text(encoding="utf-8"))
            verifier = OperatorCredentialFile.model_validate(decoded)
            for operator in verifier.operators:
                parameters = extract_parameters(operator.password_hash)
                if parameters.type is not Type.ID:
                    raise OperatorCredentialError("operator password verifier must use Argon2id")
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError, InvalidHashError) as error:
            if isinstance(error, OperatorCredentialError):
                raise
            raise OperatorCredentialError("operator credential verifier is invalid") from error
        return {operator.operator_id: operator for operator in verifier.operators}

    def authenticate(self, operator_id: str, password: str) -> OperatorCredential | None:
        operator = self._operators.get(operator_id)
        stored_hash = operator.password_hash if operator is not None else self._dummy_hash
        try:
            verified = self._hasher.verify(stored_hash, password)
        except VerificationError:
            verified = False
        if not verified or operator is None or not operator.enabled:
            return None
        return operator
