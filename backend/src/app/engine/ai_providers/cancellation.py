"""Best-effort cancellation for an in-flight provider HTTP call.

httpx's sync Client has no first-class "cancel this specific request" API,
but closing the Client's underlying connection pool from another thread
interrupts a blocked socket read on most platforms - that's what this
registry is for. Used when the user discards a staging batch while its
background AI categorization call is still in flight (see
routers/statements.py::discard_staging_batch), so an expensive cloud call
doesn't keep running to completion for nothing (or for cost) after its
result would just be thrown away anyway.

Best-effort, not a correctness requirement: if closing the connection
doesn't interrupt the blocked read on a given platform, the request simply
runs to completion - its result is still guaranteed to be discarded by the
batch-id guard already in _run_ai_categorization. Cancellation here is a
resource-saving optimization layered on top of that existing guard, not a
replacement for it.
"""

import threading

import httpx

_clients: dict[str, httpx.Client] = {}
_lock = threading.Lock()


def register(key: str, client: httpx.Client) -> None:
    with _lock:
        _clients[key] = client


def unregister(key: str) -> None:
    with _lock:
        _clients.pop(key, None)


def cancel(key: str) -> None:
    with _lock:
        client = _clients.pop(key, None)
    if client is not None:
        client.close()
