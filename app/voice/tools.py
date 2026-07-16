"""Tool definitions for the Vapi assistant.

Vapi sends a `tool-call` message to our webhook when the LLM decides to invoke
one of these tools. We execute the tool server-side and return a `tool-result`
so the LLM can continue the conversation.

We define three tools (all in OpenAI function-calling format):
  - lookup_patient_by_phone  — duplicate detection on call-in
  - save_patient             — create a new patient record (after confirmation)
  - update_patient           — update an existing record (for returning callers)
"""

from __future__ import annotations

# All tools use the OpenAI function-calling format:
#   { "type": "function", "function": { "name": ..., "description": ..., "parameters": {...} } }
# Vapi forwards these to Groq so the LLM knows how to call each tool.

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_patient_by_phone",
            "description": (
                "Look up an existing patient by their 10-digit US phone number. "
                "Call this BEFORE saving whenever the caller has provided their "
                "phone number, to detect returning patients."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "phone_number": {
                        "type": "string",
                        "description": "10-digit US phone number (digits only or formatted).",
                    }
                },
                "required": ["phone_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_patient",
            "description": (
                "Save a NEW patient record to the database. ONLY call this AFTER the "
                "caller has confirmed all the read-back information. All required "
                "fields must be present."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {"type": "string"},
                    "last_name": {"type": "string"},
                    "date_of_birth": {
                        "type": "string",
                        "description": "ISO date YYYY-MM-DD",
                    },
                    "sex": {
                        "type": "string",
                        "enum": ["Male", "Female", "Other", "Decline to Answer"],
                    },
                    "phone_number": {"type": "string", "description": "10-digit US phone"},
                    "email": {"type": "string", "description": "Optional. Valid email."},
                    "address_line_1": {"type": "string"},
                    "address_line_2": {"type": "string", "description": "Optional."},
                    "city": {"type": "string"},
                    "state": {"type": "string", "description": "2-letter US state abbreviation"},
                    "zip_code": {"type": "string"},
                    "insurance_provider": {"type": "string", "description": "Optional."},
                    "insurance_member_id": {"type": "string", "description": "Optional."},
                    "preferred_language": {
                        "type": "string",
                        "description": "Optional. Default English.",
                    },
                    "emergency_contact_name": {"type": "string", "description": "Optional."},
                    "emergency_contact_phone": {
                        "type": "string",
                        "description": "Optional. 10-digit US phone.",
                    },
                },
                "required": [
                    "first_name",
                    "last_name",
                    "date_of_birth",
                    "sex",
                    "phone_number",
                    "address_line_1",
                    "city",
                    "state",
                    "zip_code",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_patient",
            "description": (
                "Update an EXISTING patient record. Use this when a returning caller "
                "wants to change specific fields. Pass patient_id plus only the "
                "fields they want to change. ONLY call after re-confirming the "
                "changes with the caller."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "UUID of the existing patient"},
                    "first_name": {"type": "string"},
                    "last_name": {"type": "string"},
                    "date_of_birth": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "sex": {
                        "type": "string",
                        "enum": ["Male", "Female", "Other", "Decline to Answer"],
                    },
                    "phone_number": {"type": "string"},
                    "email": {"type": "string"},
                    "address_line_1": {"type": "string"},
                    "address_line_2": {"type": "string"},
                    "city": {"type": "string"},
                    "state": {"type": "string"},
                    "zip_code": {"type": "string"},
                    "insurance_provider": {"type": "string"},
                    "insurance_member_id": {"type": "string"},
                    "preferred_language": {"type": "string"},
                    "emergency_contact_name": {"type": "string"},
                    "emergency_contact_phone": {"type": "string"},
                },
                "required": ["patient_id"],
            },
        },
    },
]
