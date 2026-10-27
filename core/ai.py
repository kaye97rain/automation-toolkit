"""Claude AI helpers shared by all projects: fill a Pydantic schema from text, PDFs or images.

Needs ANTHROPIC_API_KEY in .env (create one at console.anthropic.com -> API Keys).
"""

import base64
from pathlib import Path
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from core import config

MODEL = "claude-opus-5-5"
PRICES = {"claude-opus-5-5": (4.00, 20.00)}  # $ per 1M input / output tokens
T = TypeVar("T", bound=BaseModel)

usage = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
_client: anthropic.Anthropic | None = None


class AIError(RuntimeError):
    """Claude couldn't give a usable answer (API error, refusal or cut-off response)."""


def available() -> bool:
    return bool(config.get("ANTHROPIC_API_KEY"))


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.get("ANTHROPIC_API_KEY", required=True))
    return _client


def pdf_block(path: Path) -> dict:
    """A PDF as message content. Claude reads both the text and the page images (so scans work too)."""
    data = base64.standard_b64encode(path.read_bytes()).decode()
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}}


def extract(schema: type[T], instructions: str, content: str = "",
            documents: list[dict] | None = None, effort: str = "low") -> T:
    """Ask Claude to fill `schema` from the given text and/or documents. Raises AIError on failure."""
    blocks = [*(documents or []), {"type": "text", "text": f"{instructions}\n\n{content}".strip()}]
    try:
        response = client().beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            # If a request is ever declined, the API retries it on a fallback model automatically
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": effort},  # low = fast and cheap; enough for extraction/classification
            output_format=schema,
            messages=[{"role": "user", "content": blocks}],
        )
    except anthropic.AuthenticationError as e:
        raise AIError("ANTHROPIC_API_KEY is invalid") from e
    except anthropic.RateLimitError as e:
        raise AIError("Rate limited by the Claude API - try again shortly") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"Claude API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise AIError(f"Can't reach the Claude API: {e}") from e

    usage["requests"] += 1
    usage["input_tokens"] += response.usage.input_tokens
    usage["output_tokens"] += response.usage.output_tokens

    if response.stop_reason == "refusal":
        raise AIError("Claude declined this request")
    if response.parsed_output is None:
        raise AIError(f"No usable answer (stop reason: {response.stop_reason})")
    return response.parsed_output


def usage_summary() -> str:
    """Tokens used so far in this run and the approximate cost."""
    price_in, price_out = PRICES[MODEL]
    cost = usage["input_tokens"] / 1e6 * price_in + usage["output_tokens"] / 1e6 * price_out
    return (f"{usage['requests']} AI request(s), {usage['input_tokens']:,} input + "
            f"{usage['output_tokens']:,} output tokens, about ${cost:.3f}")
