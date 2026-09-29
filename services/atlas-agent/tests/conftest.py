"""Agent test-harness compatibility adaptations."""

from asgi_test_client import ASGITestClient
from fastapi import testclient

testclient.TestClient = ASGITestClient
