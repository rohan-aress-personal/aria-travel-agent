"""
agents/travel_agent.py
──────────────────────
LangGraph ReAct agent — Aria Travel Assistant.

gpt-5.3-chat specifics:
  - api_version          : 2024-12-01-preview
  - max_completion_tokens: 16384 (via model_kwargs — rejects max_tokens)
  - temperature          : NOT SET (only default=1 supported)
"""

import os
import requests
from dotenv import load_dotenv

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from tools.travel_tools import ALL_TOOLS
from tools.email_tool import send_email
from tools.pdf_blob_tool import generate_and_save_pdf

load_dotenv()

ALL_TOOLS_EXTENDED = ALL_TOOLS + [send_email, generate_and_save_pdf]

DEFAULT_ENDPOINT   = "https://visha-mmsqm1vp-eastus2.cognitiveservices.azure.com/"
DEFAULT_DEPLOYMENT = "gpt-5.3-chat"
DEFAULT_API_VER    = "2024-12-01-preview"
DEFAULT_MAX_TOKENS = 16384

SYSTEM_PROMPT = """You are Aria, a professional AI travel agent assistant.
You only discuss travel, tourism, destinations, itineraries, weather,
currency, and related logistics. All topics are strictly travel-related.

Your capabilities:
  🌤 Weather      — Check real-time weather for any city
  💱 Currency     — Convert between currencies at live rates
  🗺 Attractions  — Discover top sights and activities
  🌍 Country Info — Visa, language, currency, culture facts
  ✈️ Travel Tips  — Practical advice for safe, enjoyable travel
  📅 Itineraries  — Build day-by-day personalised travel plans
  📧 Email + PDF  — Email travel details AND auto-save a PDF copy to cloud storage

Guidelines:
  • Always be warm, enthusiastic, and helpful.
  • Use tools proactively — don't guess when you can look up real data.
  • For trip planning questions, combine multiple tools for a complete answer.
  • Format responses clearly with emojis and structure for readability.
  • If a tool call fails, acknowledge it gracefully and provide best-effort advice.
  • Keep answers concise but complete — travellers are busy people!

  EMAIL + PDF RULE (VERY IMPORTANT — always follow this exactly):
    When the user says "email me", "send this to [email]", "mail the details", etc:

    STEP 1 — Call send_email(to_address, subject, body)
             • to_address : extract from user's message, or ask if missing
             • subject    : concise title e.g. "Your 5-Day Bali Itinerary"
             • body       : the FULL content just discussed — all details,
                            weather, itinerary, tips, country info, etc.
             NOTE: send_email automatically generates and attaches a PDF to
             the email. The recipient gets both the HTML email AND a PDF attachment.

    STEP 2 — Immediately after send_email succeeds, call generate_and_save_pdf(
               subject   = same subject as the email,
               body      = same body as the email,
               recipient = same email address
             )
             This saves an archival PDF copy to Azure Blob Storage.

    STEP 3 — Report all three results to the user:
             "✅ Email sent to [address] with PDF attached
              📄 PDF archived to blob storage: [URL]"

    NEVER skip Step 2. Always archive to blob even if user only asked for email.
    If blob storage is not configured, still complete Step 1 and mention that
    blob archiving needs AZURE_STORAGE_CONNECTION_STRING in .env.
"""


def list_deployments() -> list[dict]:
    """List Azure OpenAI deployments — used by the sidebar debug panel."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", DEFAULT_ENDPOINT).rstrip("/")
    api_key  = os.environ.get("AZURE_OPENAI_API_KEY", "")
    version  = os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_API_VER)
    if not api_key:
        return []
    url = f"{endpoint}/openai/deployments?api-version={version}"
    try:
        resp = requests.get(url, headers={"api-key": api_key}, timeout=10)
        resp.raise_for_status()
        return [
            {"id": d["id"], "model": d.get("model", "unknown")}
            for d in resp.json().get("data", [])
        ]
    except Exception:
        return []


def build_llm(deployment_name: str | None = None) -> AzureChatOpenAI:
    endpoint   = os.environ.get("AZURE_OPENAI_ENDPOINT",    DEFAULT_ENDPOINT).rstrip("/") + "/"
    api_key    = os.environ.get("AZURE_OPENAI_API_KEY",     "")
    api_ver    = os.environ.get("AZURE_OPENAI_API_VERSION", DEFAULT_API_VER)
    deployment = deployment_name or os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", DEFAULT_DEPLOYMENT)

    if not api_key:
        raise ValueError(
            "AZURE_OPENAI_API_KEY is not set.\n"
            "Find it: portal.azure.com → your OpenAI resource → Keys and Endpoint"
        )

    return AzureChatOpenAI(
        azure_endpoint   = endpoint,
        api_version      = api_ver,
        api_key          = api_key,
        azure_deployment = deployment,
        model_kwargs     = {"max_completion_tokens": DEFAULT_MAX_TOKENS},
    )


def build_agent(deployment_name: str | None = None):
    """
    Build the LangGraph ReAct agent with 8 tools:
      get_weather, convert_currency, get_attractions, get_country_info,
      get_travel_tips, build_itinerary, send_email, generate_and_save_pdf
    """
    llm = build_llm(deployment_name)
    return create_react_agent(
        model          = llm,
        tools          = ALL_TOOLS_EXTENDED,
        state_modifier = SystemMessage(content=SYSTEM_PROMPT),
    )
