"""Vapi assistant management via the official Vapi Python SDK.

Uses `vapi_server_sdk` (https://github.com/VapiAI/server-sdk-python) to:
  - create / update / list / get assistants

CLI usage:
    python -m app.voice.assistant create-assistant
    python -m app.voice.assistant update-assistant <assistant_id>
    python -m app.voice.assistant list-assistants
    python -m app.voice.assistant get-assistant <assistant_id>

Note: Phone numbers are provisioned via the Vapi dashboard.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.voice.prompt import SYSTEM_PROMPT
from app.voice.tools import TOOLS

log = get_logger(__name__)


# --- Vapi client factory -----------------------------------------------------


def _client():
    """Build the Vapi SDK client from env config."""
    from vapi import Vapi

    settings = get_settings()
    if not settings.vapi_api_key:
        raise ValueError("VAPI_API_KEY must be set in the environment")
    return Vapi(token=settings.vapi_api_key)


# --- Assistant config (typed SDK objects) ------------------------------------


def _build_assistant_kwargs(server_url: str) -> dict[str, Any]:
    """Build the kwargs for client.assistants.create() / .update().

    Uses the SDK's typed Pydantic models so the fern-generated SDK
    accepts them cleanly.
    """
    from vapi.types import (
        DeepgramTranscriber,
        GroqModel,
        Server,
    )

    settings = get_settings()

    transcriber = DeepgramTranscriber(
        provider="deepgram",
        model="nova-2",
        language="en-US",
        smart_format=True,
        keywords=[
            "male", "female", "Male", "Female",
            "insurance", "Medicare", "Medicaid",
            "emergency", "contact",
            "address", "street", "avenue", "boulevard",
        ],
    )

    model = GroqModel(
        provider="groq",
        model=settings.groq_model,  # llama-3.3-70b-versatile
        messages=[{"role": "system", "content": SYSTEM_PROMPT}],
        tools=TOOLS,
        max_tokens=250,       # keep responses short for voice
        temperature=0.4,      # consistent but not robotic
    )

    server = Server(
        url=server_url,
        timeout_seconds=30,
    )

    return {
        "name": "Patient Registration Agent",
        "transcriber": transcriber,
        "model": model,
        "server": server,
        "background_sound": "office",
        "max_duration_seconds": 600,  # 10 min max call
        "end_call_message": "Thank you for calling. Goodbye.",
        "voicemail_message": (
            "Hi, you've reached the patient registration line. "
            "Please leave a message and we'll call you back."
        ),
    }


# --- Assistant operations ----------------------------------------------------


def create_assistant(server_url: str | None = None) -> dict[str, Any]:
    """Create a new Vapi assistant and return the response (includes id)."""
    settings = get_settings()
    url = server_url or settings.vapi_server_url
    if not url:
        raise ValueError("VAPI_SERVER_URL must be set (or pass --server-url)")

    client = _client()
    kwargs = _build_assistant_kwargs(url)
    log.info("Creating Vapi assistant (server_url=%s)", url)
    assistant = client.assistants.create(**kwargs)
    data = _to_dict(assistant)
    log.info("Created assistant id=%s", data.get("id"))
    print(json.dumps(data, indent=2, default=str))
    return data


def update_assistant(assistant_id: str, server_url: str | None = None) -> dict[str, Any]:
    """Update an existing Vapi assistant's config."""
    settings = get_settings()
    url = server_url or settings.vapi_server_url
    kwargs = _build_assistant_kwargs(url)
    client = _client()
    log.info("Updating Vapi assistant id=%s", assistant_id)
    assistant = client.assistants.update(id=assistant_id, **kwargs)
    data = _to_dict(assistant)
    log.info("Updated assistant id=%s", assistant_id)
    print(json.dumps(data, indent=2, default=str))
    return data


def list_assistants() -> list[dict[str, Any]]:
    client = _client()
    assistants = client.assistants.list()
    data = [_to_dict(a) for a in assistants]
    print(json.dumps(data, indent=2, default=str))
    return data


def get_assistant(assistant_id: str) -> dict[str, Any]:
    client = _client()
    assistant = client.assistants.get(id=assistant_id)
    data = _to_dict(assistant)
    print(json.dumps(data, indent=2, default=str))
    return data


# --- helpers -----------------------------------------------------------------


def _to_dict(obj: Any) -> dict[str, Any]:
    """Coerce a SDK response object to a plain dict for logging/JSON output."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, dict):
        return obj
    return {"value": str(obj)}


# --- CLI ---------------------------------------------------------------------


HELP = """\
Vapi management CLI (uses official vapi_server_sdk)

Usage:
  python -m app.voice.assistant <command> [args]

Commands:
  create-assistant              Create the patient-registration assistant
  update-assistant <id>         Update an existing assistant's config
  get-assistant <id>            Show one assistant
  list-assistants               List all assistants

Note: Phone numbers are provisioned via the Vapi dashboard.
"""


def _cli() -> int:
    setup_logging()
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(HELP)
        return 0

    cmd = args[0]
    try:
        if cmd == "create-assistant":
            create_assistant()
        elif cmd == "update-assistant":
            if len(args) < 2:
                print("update-assistant requires an assistant id")
                return 1
            update_assistant(args[1])
        elif cmd == "get-assistant":
            if len(args) < 2:
                print("get-assistant requires an assistant id")
                return 1
            get_assistant(args[1])
        elif cmd == "list-assistants":
            list_assistants()
        else:
            print(f"Unknown command: {cmd}\n")
            print(HELP)
            return 1
    except Exception as exc:
        log.exception("CLI command failed: %s", cmd)
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
