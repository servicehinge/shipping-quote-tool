"""Shared HTTP session with automatic retry/backoff for external APIs.

External carriers (FedEx, Shippo) and helper lookups occasionally return
transient failures — dropped connections, read timeouts, 429 rate limits,
or 5xx errors. A single one-shot request surfaces these to the user as a
hard "query failed". This shared session retries such transient errors a
few times with exponential backoff, so brief network blips recover
automatically instead of failing the whole quote.

Only connection-level errors and the retryable status codes below are
retried; real errors (401, 400, 404, ...) are returned immediately so the
existing error handling still runs. POST is included because our POST
calls are read-only rate lookups, which are safe to repeat.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_RETRY = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=0.5,  # waits ~0.5s, 1s, 2s between attempts
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset({"GET", "POST"}),
    raise_on_status=False,
)


def _build_session() -> requests.Session:
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=_RETRY)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# Module-level shared session: connection pooling + retry for all API calls.
SESSION = _build_session()
