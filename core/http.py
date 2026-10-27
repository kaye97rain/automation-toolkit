"""HTTP session with automatic retries for flaky APIs and rate limits."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def make_session(retries: int = 3, backoff: float = 1.0, headers: dict | None = None) -> requests.Session:
    """Session that retries on connection errors, 429 and 5xx responses."""
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=None,  # retry every method, including POST
        respect_retry_after_header=True,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    if headers:
        session.headers.update(headers)
    return session


def get_all_pages(session: requests.Session, url: str, params: dict | None = None,
                  page_param: str = "page", items_key: str | None = None) -> list:
    """Fetch every page from a simple page-numbered API until a page comes back empty."""
    params = dict(params or {})
    page, results = 1, []
    while True:
        params[page_param] = page
        resp = session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        items = data[items_key] if items_key else data
        if not items:
            return results
        results.extend(items)
        page += 1
