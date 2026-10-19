#!/usr/bin/env python3
"""Loopback HTTP lease authority for isolated lab/rehearsal only."""

from __future__ import annotations

from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys

EMBASSY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EMBASSY_ROOT))

from lease import InMemoryLeaseAuthority, LeasePolicy

TOKEN = os.environ.get("LEASE_API_TOKEN", "lab-only-token")
_TTL = float(os.environ.get("LEASE_TTL_SECONDS", "30"))
_DRAIN = float(os.environ.get("LEASE_DRAIN_SECONDS", "1"))
_GRACE = float(os.environ.get("LEASE_GRACE_SECONDS", "1"))
# renew_before must fit inside the TTL (LeasePolicy invariant).
_RENEW_BEFORE = min(10.0, max(1.0, _TTL / 3.0))
AUTHORITY = InMemoryLeaseAuthority(
    LeasePolicy(
        lease_ttl_seconds=_TTL,
        renew_before_seconds=_RENEW_BEFORE,
        in_flight_drain_seconds=_DRAIN,
        self_fence_grace_seconds=_GRACE,
        source_name="lab-inmemory-lease",
    )
)


class Handler(BaseHTTPRequestHandler):
    def _unauthorized(self) -> None:
        self.send_response(401)
        self.end_headers()

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _auth(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {TOKEN}"

    def _respond(self, decision) -> None:
        payload = {
            "ok": decision.ok,
            "state": decision.state.to_dict(),
            "phase": decision.phase.value,
            "reason": decision.reason,
            "fencing_proof": decision.fencing_proof,
            "request_permit": decision.request_permit,
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200 if decision.ok else 409)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._auth():
            self._unauthorized()
            return
        if self.path.startswith("/lease/status"):
            self._respond(AUTHORITY.status(now=datetime.now(UTC)))
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        if not self._auth():
            self._unauthorized()
            return
        body = self._read_json()
        now = datetime.now(UTC)
        path = self.path.split("?", 1)[0]
        if path == "/lease/bootstrap":
            decision = AUTHORITY.bootstrap(
                node_id=str(body.get("node_id", "")),
                generation=str(body.get("generation", "")),
                now=now,
            )
        elif path == "/lease/renew":
            decision = AUTHORITY.renew(
                node_id=str(body.get("node_id", "")),
                epoch=int(body.get("epoch", -1)),
                generation=str(body.get("generation", "")),
                readiness_ok=bool(body.get("readiness_ok")),
                now=now,
            )
        elif path == "/lease/request-takeover":
            decision = AUTHORITY.request_takeover(
                requester_node_id=str(body.get("requester_node_id", "")),
                target_node_id=str(body.get("target_node_id", "")),
                target_generation=str(body.get("target_generation", "")),
                now=now,
                reason=str(body.get("reason", "dual_probe_failure")),
            )
        elif path == "/lease/acquire":
            decision = AUTHORITY.acquire(
                node_id=str(body.get("node_id", "")),
                generation=str(body.get("generation", "")),
                previous_epoch=int(body.get("previous_epoch", -1)),
                now=now,
            )
        else:
            self.send_response(404)
            self.end_headers()
            return
        self._respond(decision)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")


def main() -> int:
    server = ThreadingHTTPServer(("0.0.0.0", 8787), Handler)
    print("lab lease authority on :8787", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
