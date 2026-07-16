"""Medical Voice Assistant — Patient Registration via Voice AI.

A FastAPI service that:
  * Exposes a REST API for patient CRUD operations (backed by Supabase Postgres).
  * Receives Vapi webhooks to drive a conversational voice agent (Groq LLM)
    that collects patient demographics over the phone and persists them.
"""

__version__ = "0.1.0"
