import json as json_lib
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


def post_stream_with_retry(
    client: httpx.Client,
    url: str,
    *,
    json: dict,
    headers: dict,
    label: str = "OpenRouter",
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
):
    """POST an SSE streaming request, retrying on transient 429/5xx before any data has streamed.

    Yields parsed JSON objects from each `data: ...` line until `[DONE]`.
    """
    last_response = None

    for attempt in range(max_retries + 1):
        with client.stream("POST", url, json=json, headers=headers) as r:
            if r.is_error:
                r.read()
                last_response = r
                if r.status_code != 429 and r.status_code < 500:
                    break
                if attempt < max_retries:
                    retry_after = r.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else backoff_seconds * (2 ** attempt)
                    time.sleep(delay)
                continue

            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                chunk = line[len("data:"):].strip()
                if chunk == "[DONE]":
                    return
                yield json_lib.loads(chunk)
            return

    raise httpx.HTTPStatusError(
        f"{last_response.status_code} error from {label} after {max_retries + 1} attempts: {last_response.text}",
        request=last_response.request,
        response=last_response,
    )
