"""Vapi webhook handler.

Vapi sends us two kinds of messages over the course of a call:
  - `assistant-request`  — at call start, we can dynamically return config.
  - `tool-call`          — the LLM wants to invoke one of our tools.
  - `end-of-call-report` — call ended; includes transcript (bonus).

We respond to `tool-call` messages by executing the tool server-side and
returning a `tool-result` so the LLM can continue. All tool execution goes
through the same `db` layer the REST API uses — single source of truth for
validation and persistence.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.db import repo
from app.db.schema import PatientCreate, PatientUpdate

log = get_logger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])


# --- helpers -----------------------------------------------------------------


def _tool_result(tool_call_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Shape a Vapi-compatible tool-result response."""
    return {
        "results": [
            {
                "toolCallId": tool_call_id,
                "result": result,
            }
        ]
    }


def _safe_str(d: dict[str, Any], key: str) -> str | None:
    v = d.get(key)
    return v if isinstance(v, str) and v.strip() else None


# --- tool implementations ----------------------------------------------------


def _lookup_patient_by_phone(args: dict[str, Any]) -> dict[str, Any]:
    phone = args.get("phone_number", "")
    row = repo.get_patient_by_phone(phone)
    if not row:
        return {"found": False, "message": "No existing patient with this phone number."}
    return {
        "found": True,
        "patient_id": row.patient_id,
        "first_name": row.first_name,
        "last_name": row.last_name,
        "message": (
            f"An existing patient record was found for {row.first_name} "
            f"{row.last_name} (patient_id={row.patient_id}). Ask the caller "
            "if they'd like to update their information instead of creating a new record."
        ),
    }


def _save_patient(args: dict[str, Any]) -> dict[str, Any]:
    cleaned = {k: v for k, v in args.items() if v not in (None, "")}
    try:
        payload = PatientCreate(**cleaned)
    except Exception as exc:
        log.warning("save_patient validation failed: %s", exc)
        return {
            "success": False,
            "error": "validation_failed",
            "details": str(exc),
            "instruction": (
                "The patient data failed validation. Re-prompt the caller for the "
                "specific field(s) mentioned in the details. Do NOT read the raw "
                "error to the caller — translate it into a friendly question."
            ),
        }

    existing = repo.get_patient_by_phone(payload.phone_number)
    if existing:
        return {
            "success": False,
            "error": "duplicate",
            "instruction": (
                f"A patient with this phone number already exists "
                f"({existing.first_name} {existing.last_name}, patient_id="
                f"{existing.patient_id}). Ask the caller if they'd like to update "
                "instead. If yes, use update_patient with that patient_id."
            ),
        }

    try:
        data = payload.model_dump(mode="json")
        row = repo.create_patient(data)
        log.info(
            "Voice agent saved patient %s (%s %s) from call",
            row.patient_id, row.first_name, row.last_name,
        )
        return {
            "success": True,
            "patient_id": row.patient_id,
            "message": "Patient record saved successfully.",
        }
    except Exception as exc:
        log.exception("save_patient DB write failed")
        return {
            "success": False,
            "error": "database_error",
            "instruction": (
                "A technical error occurred while saving. Apologize to the caller and "
                "ask them to call back in a few minutes. Do not retry automatically."
            ),
        }


def _update_patient(args: dict[str, Any]) -> dict[str, Any]:
    patient_id = args.get("patient_id")
    if not patient_id:
        return {"success": False, "error": "missing_patient_id"}

    existing = repo.get_patient(str(patient_id))
    if not existing:
        return {"success": False, "error": "not_found"}

    update_fields = {
        k: v for k, v in args.items()
        if k != "patient_id" and v not in (None, "")
    }
    if not update_fields:
        return {"success": False, "error": "no_fields_to_update"}

    try:
        payload = PatientUpdate(**update_fields)
    except Exception as exc:
        log.warning("update_patient validation failed: %s", exc)
        return {
            "success": False,
            "error": "validation_failed",
            "details": str(exc),
            "instruction": "Re-prompt the caller for the specific invalid field.",
        }

    update_data = {k: v for k, v in payload.model_dump(mode="json").items() if v is not None}
    try:
        row = repo.update_patient(str(patient_id), update_data)
        log.info("Voice agent updated patient %s", patient_id)
        return {"success": True, "patient_id": patient_id, "message": "Patient record updated."}
    except Exception as exc:
        log.exception("update_patient DB write failed")
        return {"success": False, "error": "database_error", "instruction": "Apologize and ask the caller to call back."}


def _execute_tool(tool_name: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Execute a single tool by name and return its result dict."""
    log.info(
        "Tool call: %s | params=%s",
        tool_name, json.dumps(parameters, default=str),
    )
    try:
        if tool_name == "lookup_patient_by_phone":
            return _lookup_patient_by_phone(parameters)
        elif tool_name == "save_patient":
            return _save_patient(parameters)
        elif tool_name == "update_patient":
            return _update_patient(parameters)
        else:
            return {
                "success": False,
                "error": f"unknown_tool:{tool_name}",
                "instruction": "Tell the caller there was a technical issue.",
            }
    except Exception as exc:
        log.exception("Tool execution failed: %s", tool_name)
        return {
            "success": False,
            "error": "server_error",
            "instruction": "Apologize and ask the caller to call back later.",
        }


# --- webhook endpoint --------------------------------------------------------


@router.post("/webhook", response_model=None)
async def vapi_webhook(request: Request):
    """Single webhook endpoint Vapi calls for assistant-request + tool-calls.

    Vapi posts a JSON body with a `message` object describing the event type.
    See: https://docs.vapi.ai/server-url
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "invalid_json"},
        )

    message = body.get("message", {})
    msg_type = message.get("type")
    log.info("Vapi webhook: type=%s", msg_type)

    # --- assistant-request: optionally return dynamic config at call start ---
    if msg_type == "assistant-request":
        # We could override the assistant here per-call. For now, just ack.
        return JSONResponse(status_code=200, content={})

    # --- tool-call / tool-calls: execute the requested tool(s) and return result(s) ---
    # Vapi sends "tool-calls" (plural) with a toolCallList array.
    # Older format used "tool-call" (singular) with flat fields.
    if msg_type in ("tool-call", "tool-calls"):
        # Debug: log the raw message keys to understand the format
        log.info("Tool message keys: %s", list(message.keys()))
        log.info("Tool message body: %s", json.dumps(message, default=str)[:2000])

        # Handle plural format (current Vapi API)
        # Vapi docs show toolCallList AND toolWithToolCallList
        tool_call_list = message.get("toolCallList", [])
        tool_with_list = message.get("toolWithToolCallList", [])

        if tool_with_list:
            # Format from Vapi docs: toolWithToolCallList contains tool + toolCall
            results = []
            for item in tool_with_list:
                tool_call = item.get("toolCall", {})
                # toolCall may have nested function.name + function.arguments
                func = tool_call.get("function", {})
                tool_name = item.get("name") or func.get("name", "")
                tool_call_id = tool_call.get("id", "unknown")
                parameters = func.get("arguments") or tool_call.get("arguments", {}) or {}
                if isinstance(parameters, str):
                    try:
                        parameters = json.loads(parameters)
                    except Exception:
                        parameters = {"raw": parameters}
                result = _execute_tool(tool_name, parameters)
                results.append({"toolCallId": tool_call_id, "result": result})
            return JSONResponse(status_code=200, content={"results": results})

        if tool_call_list:
            results = []
            for tc in tool_call_list:
                tool_name = tc.get("name", "")
                tool_call_id = tc.get("id", "unknown")
                parameters = tc.get("arguments", {}) or {}
                if isinstance(parameters, str):
                    try:
                        parameters = json.loads(parameters)
                    except Exception:
                        parameters = {"raw": parameters}
                result = _execute_tool(tool_name, parameters)
                results.append({"toolCallId": tool_call_id, "result": result})
            return JSONResponse(status_code=200, content={"results": results})

        # Fall back to singular format (legacy)
        tool_name = message.get("tool-name") or message.get("toolName") or message.get("name", "")
        tool_call_id = message.get("tool-call-id") or message.get("toolCallId") or message.get("id", "unknown")
        parameters = message.get("parameters") or message.get("arguments") or message.get("tool-parameters") or {}

        result = _execute_tool(tool_name, parameters)
        return JSONResponse(status_code=200, content=_tool_result(tool_call_id, result))

    # --- end-of-call-report: log transcript for observability (bonus) ---
    if msg_type == "end-of-call-report":
        transcript = message.get("transcript") or body.get("transcript")
        summary = message.get("summary")
        call_id = message.get("call-id") or message.get("callId")
        log.info("Call ended | call_id=%s | summary=%s", call_id, summary)
        if transcript:
            # Truncate very long transcripts in the log
            preview = transcript if len(transcript) < 2000 else transcript[:2000] + "...[truncated]"
            log.info("Transcript for call %s:\n%s", call_id, preview)
        # TODO: persist transcript to call_transcripts table (bonus)
        return JSONResponse(status_code=200, content={})

    # Unknown message type — ack so Vapi doesn't retry
    log.warning("Unhandled Vapi message type: %s", msg_type)
    return JSONResponse(status_code=200, content={})
