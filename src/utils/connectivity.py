import os
from typing import Tuple

import httpx


DEFAULT_TIMEOUT = 5.0
DEEPGRAM_PING_URL = "https://api.deepgram.com/v1/projects"
OPENAI_MODEL_URL = "https://api.openai.com/v1/models/{model}"


def check_deepgram_connectivity(timeout: float = DEFAULT_TIMEOUT) -> Tuple[bool, str | None]:
    """Perform a lightweight Deepgram API call to confirm credentials and availability."""
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        return False, "DEEPGRAM_API_KEY missing"

    headers = {
        "Authorization": f"Token {api_key}",
    }
    try:
        response = httpx.get(DEEPGRAM_PING_URL, headers=headers, timeout=timeout)
        if response.status_code == 200:
            return True, None
        return False, f"status {response.status_code}"
    except httpx.HTTPError as exc:
        return False, str(exc)


def check_openai_connectivity(model: str, timeout: float = DEFAULT_TIMEOUT) -> Tuple[bool, str | None]:
    """Ping OpenAI's models endpoint to verify API availability."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False, "OPENAI_API_KEY missing"

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    url = OPENAI_MODEL_URL.format(model=model)
    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            return True, None
        return False, f"status {response.status_code}"
    except httpx.HTTPError as exc:
        return False, str(exc)

