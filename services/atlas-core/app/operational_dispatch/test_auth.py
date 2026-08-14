from unittest.mock import patch

from app.operational_dispatch.auth import OperationalDispatchAuthenticator


def test_authentication_uses_constant_time_comparison(tmp_path) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("expected-token\n", encoding="ascii")
    authenticator = OperationalDispatchAuthenticator(token_file)
    with patch(
        "app.operational_dispatch.auth.secrets.compare_digest",
        return_value=True,
    ) as compare:
        assert authenticator.authenticate("Bearer supplied-token") is True
    compare.assert_called_once_with("supplied-token", "expected-token")
