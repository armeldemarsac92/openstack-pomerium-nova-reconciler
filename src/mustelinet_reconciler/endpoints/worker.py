from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from mustelinet_reconciler.application.services.reconciliation_service import ReconciliationService
from mustelinet_reconciler.domain.models.reconciliation_plan import ReconciliationPlan

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RuntimeState:
    ready: bool = False
    last_error: str | None = None
    latest_plan: ReconciliationPlan | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record_success(self, plan: ReconciliationPlan) -> None:
        with self.lock:
            self.ready = True
            self.last_error = None
            self.latest_plan = plan

    def record_error(self, error: Exception) -> None:
        with self.lock:
            self.ready = False
            self.last_error = str(error)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            plan = self.latest_plan
            return {
                "ready": self.ready,
                "last_error": self.last_error,
                "latest": _plan_counts(plan) if plan is not None else None,
            }


def run_worker(
    *,
    service: ReconciliationService,
    poll_interval_seconds: int,
    dry_run: bool,
    state: RuntimeState | None = None,
) -> None:
    state = state or RuntimeState()
    while True:
        try:
            plan = service.reconcile(dry_run=dry_run)
            state.record_success(plan)
            LOGGER.info(
                "reconciliation_pass_complete actions=%s skipped=%s dry_run=%s",
                len(plan.actions),
                len(plan.skipped),
                dry_run,
            )
        except Exception as exc:
            state.record_error(exc)
            LOGGER.exception("reconciliation_pass_failed")
        time.sleep(poll_interval_seconds)


def start_http_server(addr: str, state: RuntimeState) -> ThreadingHTTPServer:
    host, port_text = addr.rsplit(":", 1)
    server = ThreadingHTTPServer((host, int(port_text)), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _handler(state: RuntimeState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            snapshot = state.snapshot()
            if self.path == "/healthz":
                self._write_json({"ok": True})
            elif self.path == "/readyz":
                status = 200 if snapshot["ready"] else 503
                self._write_json(snapshot, status=status)
            elif self.path == "/reconciliations/latest":
                self._write_json(snapshot)
            elif self.path == "/metrics":
                self._write_text(_metrics(snapshot), content_type="text/plain; version=0.0.4")
            else:
                self._write_json({"error": "not found"}, status=404)

        def log_message(self, format: str, *args: object) -> None:
            LOGGER.debug("http_status " + format, *args)

        def _write_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _write_text(self, body: str, content_type: str, status: int = 200) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return Handler


def _plan_counts(plan: ReconciliationPlan | None) -> dict[str, int]:
    if plan is None:
        return {
            "actions": 0,
            "upserts": 0,
            "deletes": 0,
            "skipped": 0,
        }
    return {
        "actions": len(plan.actions),
        "upserts": len(plan.upserts),
        "deletes": len(plan.deletes),
        "skipped": len(plan.skipped),
    }


def _metrics(snapshot: dict[str, Any]) -> str:
    latest = snapshot.get("latest") or _plan_counts(None)
    ready = 1 if snapshot.get("ready") else 0
    return "\n".join(
        [
            "# HELP mustelinet_reconciler_ready Reconciler readiness state.",
            "# TYPE mustelinet_reconciler_ready gauge",
            f"mustelinet_reconciler_ready {ready}",
            (
                "# HELP mustelinet_reconciler_latest_actions "
                "Actions planned in the latest reconciliation."
            ),
            "# TYPE mustelinet_reconciler_latest_actions gauge",
            f"mustelinet_reconciler_latest_actions {latest['actions']}",
            f"mustelinet_reconciler_latest_upserts {latest['upserts']}",
            f"mustelinet_reconciler_latest_deletes {latest['deletes']}",
            f"mustelinet_reconciler_latest_skipped {latest['skipped']}",
            "",
        ]
    )
