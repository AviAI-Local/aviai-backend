import time

import httpx


def post_with_retry(
    client: httpx.Client,
    url: str,
    *,
    json: dict,
    headers: dict,
    label: str = "OpenRouter",
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
) -> httpx.Response:
    """POST with retry on transient 429/5xx responses from OpenRouter or its upstream provider."""
    last_response = None

    for attempt in range(max_retries + 1):
        r = client.post(url, json=json, headers=headers)

        if not r.is_error:
            return r

        last_response = r
        if r.status_code != 429 and r.status_code < 500:
            break

        if attempt < max_retries:
            retry_after = r.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else backoff_seconds * (2 ** attempt)
            time.sleep(delay)

    raise httpx.HTTPStatusError(
        f"{last_response.status_code} error from {label} after {max_retries + 1} attempts: {last_response.text}",
        request=last_response.request,
        response=last_response,
    )
