"""Unit tests for no-cache Embassy HTTP probing."""

from __future__ import annotations

import json
from unittest import TestCase
from unittest.mock import patch
from urllib.error import URLError

from embassy import probe


class _FakeResponse:
    def __init__(self, status_code, body=b""):
        self.status_code = status_code
        self.body = body
        self.closed = False

    def getcode(self):
        return self.status_code

    def read(self, _size=-1):
        return self.body

    def close(self):
        self.closed = True


class _FakeOpener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.request = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        if self.error is not None:
            raise self.error
        return self.response


class EmbassyProbeTests(TestCase):
    def test_readiness_probe_uses_bearer_and_no_cache_headers(self):
        response = _FakeResponse(
            200,
            json.dumps({"ready": True}).encode(),
        )
        opener = _FakeOpener(response=response)
        with patch.object(probe, "build_opener", return_value=opener):
            result = probe.probe_readiness(
                "http://100.82.252.18:8069/filantropia/embassy/readiness",
                token="test-only-token",
                timeout_seconds=4,
            )

        self.assertTrue(result.reachable)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.payload, {"ready": True})
        self.assertEqual(
            opener.request.get_header("Authorization"),
            "Bearer test-only-token",
        )
        self.assertEqual(
            opener.request.get_header("Cache-control"),
            "no-cache, no-store, max-age=0",
        )
        self.assertIn("_embassy_probe=", opener.request.full_url)
        self.assertTrue(response.closed)

    def test_non_success_http_response_is_reachable_but_not_a_valid_ready_check(self):
        response = _FakeResponse(503, b'{"ready": false}')
        opener = _FakeOpener(response=response)
        with patch.object(probe, "build_opener", return_value=opener):
            result = probe.probe_readiness(
                "https://trl5.example.test/filantropia/embassy/readiness",
                token="test-only-token",
                timeout_seconds=4,
            )

        self.assertTrue(result.reachable)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.payload, {"ready": False})

    def test_network_failure_is_not_logged_as_a_reachable_http_response(self):
        opener = _FakeOpener(error=URLError("network unreachable"))
        with patch.object(probe, "build_opener", return_value=opener):
            result = probe.probe_readiness(
                "https://trl5.example.test/filantropia/embassy/readiness",
                token="test-only-token",
                timeout_seconds=4,
            )

        self.assertFalse(result.reachable)
        self.assertIsNone(result.status_code)
        self.assertEqual(result.error_kind, "str")
        self.assertNotIn("test-only-token", repr(result))

    def test_public_route_probe_accepts_http_200(self):
        response = _FakeResponse(200)
        opener = _FakeOpener(response=response)
        with patch.object(probe, "build_opener", return_value=opener):
            result = probe.probe_public_route(
                "https://filantropiasolar.pt/contacto",
                timeout_seconds=4,
            )

        self.assertTrue(result.reachable)
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(result.payload)

    def test_plain_http_to_a_public_host_is_rejected(self):
        with self.assertRaises(ValueError):
            probe.probe_public_route(
                "http://example.test/health",
                timeout_seconds=4,
            )

    def test_url_credentials_and_queries_are_rejected(self):
        for url in (
            "https://user:password@trl5.example.test/ready",
            "https://trl5.example.test/ready?token=secret",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                probe.probe_readiness(
                    url,
                    token="test-only-token",
                    timeout_seconds=4,
                )


if __name__ == "__main__":
    import unittest

    unittest.main()
