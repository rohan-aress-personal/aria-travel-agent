"""
app.py  —  Aria Travel Agent · Streamlit UI
Run with:  streamlit run app.py
"""

import os
import sys
import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

st.set_page_config(
    page_title="Aria — AI Travel Agent",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=DM+Sans:wght@300;400;500&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
#MainMenu,footer,header{visibility:hidden;}
.stApp{background:linear-gradient(135deg,#0f1b2d 0%,#1a2f4a 50%,#0d2137 100%);min-height:100vh;}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#0a1628 0%,#112240 100%);border-right:1px solid rgba(100,180,255,0.15);}
.user-bubble{background:linear-gradient(135deg,#1565c0,#0d47a1);border-radius:18px 18px 4px 18px;padding:14px 18px;margin:8px 0;color:#e8f4fd;font-size:0.95rem;line-height:1.6;box-shadow:0 4px 15px rgba(21,101,192,0.3);max-width:85%;margin-left:auto;}
.assistant-bubble{background:linear-gradient(135deg,#102a43,#1a3a5c);border:1px solid rgba(100,180,255,0.2);border-radius:18px 18px 18px 4px;padding:14px 18px;margin:8px 0;color:#cce7ff;font-size:0.95rem;line-height:1.7;box-shadow:0 4px 15px rgba(0,0,0,0.3);max-width:85%;white-space:pre-wrap;}
.tool-thinking{background:rgba(255,165,0,0.08);border:1px solid rgba(255,165,0,0.2);border-radius:10px;padding:10px 14px;margin:6px 0;font-size:0.8rem;color:#ffd180;font-family:monospace;}




div[data-testid="stButton"] button{background:linear-gradient(135deg,rgba(21,101,192,0.4),rgba(13,71,161,0.4))!important;border:1px solid rgba(100,180,255,0.3)!important;color:#90caf9!important;border-radius:20px!important;font-size:0.82rem!important;padding:6px 14px!important;transition:all 0.2s ease!important;width:100%;margin:2px 0;}
div[data-testid="stButton"] button:hover{background:linear-gradient(135deg,rgba(21,101,192,0.7),rgba(13,71,161,0.7))!important;border-color:rgba(100,180,255,0.6)!important;color:#e3f2fd!important;transform:translateY(-1px);}
.aria-title{font-family:'Playfair Display',serif;font-size:2.2rem;font-weight:700;background:linear-gradient(135deg,#64b5f6,#42a5f5,#90caf9);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;letter-spacing:-0.02em;}
.aria-subtitle{color:#7fb3d3;font-size:0.9rem;letter-spacing:0.08em;text-transform:uppercase;font-weight:300;}
.s-ok{display:inline-flex;align-items:center;gap:6px;background:rgba(0,200,100,0.15);border:1px solid rgba(0,200,100,0.3);border-radius:20px;padding:4px 12px;font-size:0.78rem;color:#69f0ae;margin:3px 0;}
.s-warn{display:inline-flex;align-items:center;gap:6px;background:rgba(255,160,0,0.15);border:1px solid rgba(255,160,0,0.3);border-radius:20px;padding:4px 12px;font-size:0.78rem;color:#ffd54f;margin:3px 0;}
.s-err{display:inline-flex;align-items:center;gap:6px;background:rgba(255,80,80,0.15);border:1px solid rgba(255,80,80,0.3);border-radius:20px;padding:4px 12px;font-size:0.78rem;color:#ef9a9a;margin:3px 0;}
.metric-card{background:rgba(255,255,255,0.04);border:1px solid rgba(100,180,255,0.12);border-radius:10px;padding:12px 14px;margin:6px 0;color:#90caf9;font-size:0.82rem;}
.metric-card .label{color:#7fb3d3;font-size:0.72rem;text-transform:uppercase;}
.metric-card .value{font-size:1.1rem;font-weight:500;color:#e3f2fd;}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_azure() -> tuple[bool, list[str]]:
    required = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT_NAME"]
    missing  = [k for k in required if not os.getenv(k) or os.getenv(k, "").startswith("<")]
    return len(missing) == 0, missing

def check_email() -> tuple[str, str]:
    provider = os.getenv("EMAIL_PROVIDER", "").lower().strip()
    if not provider or provider.startswith("<"):
        return "s-warn", "⚠️ Email not configured (optional)"
    reqs = {
        "gmail":    ["EMAIL_SENDER_ADDRESS", "EMAIL_SENDER_PASSWORD"],
        "outlook":  ["EMAIL_SENDER_ADDRESS", "EMAIL_SENDER_PASSWORD"],
        "sendgrid": ["SENDGRID_API_KEY", "EMAIL_SENDER_ADDRESS"],
    }
    if provider not in reqs:
        return "s-err", f"❌ Unknown EMAIL_PROVIDER: {provider}"
    missing = [k for k in reqs[provider] if not os.getenv(k) or os.getenv(k, "").startswith("<")]
    if missing:
        return "s-warn", f"⚠️ Email ({provider}) — missing keys"
    return "s-ok", f"📧 Email ready · {provider.title()}"

def check_blob() -> tuple[str, str]:
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    if not conn or conn.startswith("<") or "AccountName=<" in conn:
        return "s-warn", "⚠️ Blob Storage not configured (optional)"
    container = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "travel-images")
    return "s-ok", f"🗄 Blob Storage ready · {container}"



# ── Agent singleton ───────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="🛫 Starting Aria...")
def get_agent(deployment_override: str = ""):
    try:
        from agents.travel_agent import build_agent
        return build_agent(deployment_override or None), None
    except Exception as e:
        return None, str(e)


# ── Session state ─────────────────────────────────────────────────────────────
for k, v in [("messages", []), ("total_queries", 0), ("deployment_override", "")]:
    if k not in st.session_state:
        st.session_state[k] = v


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:20px 0 10px;'>
      <span style='font-size:3rem'>✈️</span>
      <div class='aria-title' style='font-size:1.6rem'>Aria</div>
      <div class='aria-subtitle'>AI Travel Agent</div>
    </div>""", unsafe_allow_html=True)

    env_ok, missing = check_azure()
    if env_ok:
        st.markdown('<div class="s-ok">⬤ Azure OpenAI · Connected</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="s-err">⬤ Azure OpenAI · Keys Missing</div>', unsafe_allow_html=True)
        for m in missing:
            st.markdown(f'<small style="color:#ef9a9a">  ✗ {m}</small>', unsafe_allow_html=True)

    ecls, emsg = check_email()
    st.markdown(f'<div class="{ecls}">{emsg}</div>', unsafe_allow_html=True)

    bcls, bmsg = check_blob()
    st.markdown(f'<div class="{bcls}">{bmsg}</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    c1.metric("Queries", st.session_state.total_queries)
    c2.metric("Messages", len(st.session_state.messages))

    st.divider()

    st.markdown("**⚡ Quick Questions**")
    quick = [
        ("🌤 Tokyo Weather",          "What is the current weather in Tokyo?"),
        ("💱 USD to EUR",              "Convert 500 USD to EUR"),
        ("🗺 Paris Attractions",       "What are the top attractions in Paris?"),
        ("🌍 Japan Info",              "Tell me about Japan — currency, language, entry requirements"),
        ("📅 7-Day Bali Plan",         "Plan a 7-day itinerary for Bali, I love beaches and food"),
        ("✈️ Vietnam Tips",            "Give me travel tips for Vietnam"),
        ("📧 Email Last Response",     "Email me the last response to my inbox"),
    ]
    for label, prompt in quick:
        if st.button(label, key=f"q_{label}"):
            st.session_state._pending_prompt = prompt

    st.divider()

    st.markdown("**🛠 Capabilities**")
    for icon, name, src in [
        ("🌤","Live Weather","OpenWeatherMap"),
        ("💱","Currency","ExchangeRate-API"),
        ("🗺","Attractions","OpenTripMap"),
        ("🌍","Country Facts","RestCountries"),
        ("📅","Itineraries","Azure OpenAI"),
        ("💡","Travel Tips","Azure OpenAI"),
        ("📸","Spot Images","Unsplash → Azure Blob"),
        ("📧","Email Results","Gmail / Outlook / SendGrid"),
    ]:
        st.markdown(
            f'<div class="metric-card"><span class="label">{src}</span><br>'
            f'<span class="value">{icon} {name}</span></div>',
            unsafe_allow_html=True
        )

    st.divider()
    if st.button("🗑 Clear Conversation"):
        st.session_state.messages = []
        st.session_state.total_queries = 0
        st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='padding:24px 0 8px;'>
  <span class='aria-title'>Aria — Your AI Travel Agent</span><br>
  <span class='aria-subtitle'>Azure OpenAI · LangChain · LangGraph · PDF Archiving</span>
</div>""", unsafe_allow_html=True)

if not st.session_state.messages:
    st.markdown("""
<div class='assistant-bubble' style='max-width:100%;margin:16px 0;'>
👋 <strong>Hi! I'm Aria, your personal AI travel agent.</strong>

I can help you with:
  🌤  <strong>Live weather</strong> — "What is the weather in Santorini?"
  💱  <strong>Currency conversion</strong> — "Convert 1000 INR to JPY"
  🗺  <strong>Top attractions</strong> — "Best things to do in Amsterdam"
  🌍  <strong>Country facts</strong> — "Tell me about Thailand: visa, currency, culture"
  📅  <strong>Custom itineraries</strong> — "Plan 5 days in Morocco, I love history and food"
  💡  <strong>Travel tips</strong> — "Any tips for travelling to Vietnam?"
  📧  <strong>Email + PDF</strong> — "Email me this itinerary to alice@example.com"
      → Sends HTML email + PDF attachment + archives PDF to Azure Blob 📄

Where would you like to go? ✈️
</div>""", unsafe_allow_html=True)


def render_message(msg: dict):
    """Render a single message — handles text + inline blob image grid."""
    if msg["role"] == "user":
        st.markdown(f'<div class="user-bubble">🧳 {msg["content"]}</div>', unsafe_allow_html=True)
        return

    # Assistant message
    if msg.get("tool_calls"):
        with st.expander("🔍 Agent Thinking", expanded=False):
            for tc in msg["tool_calls"]:
                st.markdown(
                    f'<div class="tool-thinking">⚙️ <strong>{tc["tool"]}</strong>'
                    f'<span style="color:#90caf9;margin-left:8px">{tc["args"]}</span></div>',
                    unsafe_allow_html=True
                )

    st.markdown(f'<div class="assistant-bubble">🌐 {msg["content"]}</div>', unsafe_allow_html=True)

    # If the response contains a PDF blob URL, show a download link
    import re as _re
    pdf_urls = _re.findall(r'https?://\S+\.blob\.core\.windows\.net/\S+\.pdf', msg["content"])
    for pdf_url in pdf_urls:
        st.markdown(
            f'<div style="margin:8px 0;padding:10px 14px;background:rgba(21,101,192,0.15);'
            f'border:1px solid rgba(100,180,255,0.3);border-radius:10px;font-size:0.85rem;color:#90caf9;">'
            f'📄 <strong>PDF saved to Azure Blob:</strong> '
            f'<a href="{pdf_url}" target="_blank" style="color:#64b5f6;">View / Download PDF</a>'
            f'</div>',
            unsafe_allow_html=True
        )


# Render history
for msg in st.session_state.messages:
    render_message(msg)


# ── Input ─────────────────────────────────────────────────────────────────────
pending    = st.session_state.pop("_pending_prompt", None)
user_input = st.chat_input("Ask Aria anything… try 'email me a Bali itinerary to alice@example.com' 📧")
query      = user_input or pending

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    st.session_state.total_queries += 1
    st.markdown(f'<div class="user-bubble">🧳 {query}</div>', unsafe_allow_html=True)

    lc_messages = []
    for m in st.session_state.messages:
        if m["role"] == "user":
            lc_messages.append(HumanMessage(content=m["content"]))
        else:
            lc_messages.append(AIMessage(content=m["content"]))

    agent, agent_error = get_agent(st.session_state.deployment_override)

    if agent_error or agent is None:
        is_404 = "DeploymentNotFound" in str(agent_error) or "404" in str(agent_error)
        fix = (
            "\n\n**Fix:** Open 🔧 panel in sidebar → List My Deployments → paste the Name in the override box."
            if is_404 else "\n\nCheck your .env file and restart."
        )
        err = f"⚠️ Agent error: {agent_error}{fix}"
        st.markdown(f'<div class="assistant-bubble">🌐 {err}</div>', unsafe_allow_html=True)
        st.session_state.messages.append({"role": "assistant", "content": err, "tool_calls": []})

    else:
        tool_calls_seen = []
        final_answer    = ""

        with st.spinner("✈️ Aria is thinking..."):
            try:
                for event in agent.stream({"messages": lc_messages}, stream_mode="values"):
                    last = event["messages"][-1]
                    if hasattr(last, "tool_calls") and last.tool_calls:
                        for tc in last.tool_calls:
                            tool_calls_seen.append({
                                "tool": tc.get("name", "?"),
                                "args": str(tc.get("args", {})),
                            })
                    if hasattr(last, "content") and isinstance(last.content, str) and last.content.strip():
                        final_answer = last.content

            except Exception as e:
                err_str = str(e)
                if "content_filter" in err_str or "content management policy" in err_str:
                    final_answer = (
                        "⚠️ Azure content filter blocked that request.\n\n"
                        "This is a false positive. Try rephrasing:\n"
                        "  • Use 'I want to visit' instead of 'dying to visit'\n"
                        "  • Use 'beautiful beaches' instead of 'killer beaches'\n\n"
                        "Or lower the filter threshold in Azure Portal → Content filters."
                    )
                elif "DeploymentNotFound" in err_str or "404" in err_str:
                    final_answer = (
                        "⚠️ Azure OpenAI Deployment Not Found (404)\n\n"
                        "Open the 🔧 panel in the sidebar → List My Deployments → paste the Name."
                    )
                elif "401" in err_str or "AuthenticationError" in err_str:
                    final_answer = (
                        "⚠️ Azure Authentication Failed (401)\n\n"
                        "Check AZURE_OPENAI_API_KEY in .env.\n"
                        "Find it at: portal.azure.com → your OpenAI resource → Keys and Endpoint"
                    )
                else:
                    final_answer = f"⚠️ Something went wrong: {err_str}"

        if tool_calls_seen:
            with st.expander("🔍 Agent Thinking", expanded=False):
                for tc in tool_calls_seen:
                    st.markdown(
                        f'<div class="tool-thinking">⚙️ <strong>{tc["tool"]}</strong>'
                        f'<span style="color:#90caf9;margin-left:8px">{tc["args"]}</span></div>',
                        unsafe_allow_html=True
                    )

        reply = final_answer or "I processed your request but got no response. Please try again."
        st.markdown(f'<div class="assistant-bubble">🌐 {reply}</div>', unsafe_allow_html=True)


        st.session_state.messages.append({
            "role": "assistant", "content": reply, "tool_calls": tool_calls_seen,
        })
# pipeline test Wed Mar 18 05:52:43 UTC 2026
