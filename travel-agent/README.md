# ✈️ Aria — AI Travel Agent
### Built with LangChain · LangGraph · Azure OpenAI · Streamlit

---

## 🗂 Project Structure

```
travel-agent/
│
├── app.py                    ← Streamlit UI + orchestration
├── .env.example              ← API key template (copy → .env)
├── requirements.txt          ← Python dependencies
├── startup.txt               ← Azure App Service startup command
│
├── agents/
│   └── travel_agent.py       ← LangGraph ReAct agent definition
│
└── tools/
    └── travel_tools.py       ← 6 LangChain tools (external APIs)
```

---

## 🔑 Free API Keys Required

| # | Service | Free Tier | Sign Up |
|---|---------|-----------|---------|
| 1 | **Azure OpenAI** | Azure for Students ($100 credit) or F0 tier | [portal.azure.com](https://portal.azure.com) |
| 2 | **OpenWeatherMap** | 1,000 calls/day free | [openweathermap.org/api](https://openweathermap.org/api) |
| 3 | **ExchangeRate-API** | 1,500 calls/month free | [exchangerate-api.com](https://www.exchangerate-api.com/) |
| 4 | **OpenTripMap** | 500 calls/day free | [opentripmap.io](https://opentripmap.io/product) |
| ✅ | **RestCountries** | Completely free, no key | [restcountries.com](https://restcountries.com/) |
| ✅ | **Open-Meteo** | Completely free, no key (fallback weather) | [open-meteo.com](https://open-meteo.com/) |

> **💡 Tip:** Keys 2–4 are optional. The app has fallbacks — Open-Meteo replaces OpenWeatherMap, open.er-api.com replaces ExchangeRate, and OpenTripMap gracefully degrades to LLM-generated tips.

---

## 🏗 Architecture & Workflow

```
User types message
       │
       ▼
  Streamlit UI (app.py)
  ├─ Renders chat history
  ├─ Passes message to LangGraph agent
  └─ Streams response back to UI
       │
       ▼
  LangGraph ReAct Agent (agents/travel_agent.py)
  ┌────────────────────────────────────────────┐
  │  1. LLM Node (Azure OpenAI gpt-35-turbo)   │
  │     • Reads system prompt (Aria persona)   │
  │     • Reads full conversation history      │
  │     • Decides: call a tool OR final answer │
  │                                            │
  │  2. Tool Node (if tool selected)           │
  │     • Executes one of 6 tools              │
  │     • Returns result back to LLM           │
  │                                            │
  │  3. Loop repeats until final answer        │
  └────────────────────────────────────────────┘
       │
       ▼
  Tools (tools/travel_tools.py)
  ├─ get_weather(city)           → OpenWeatherMap API
  ├─ convert_currency(...)       → ExchangeRate-API
  ├─ get_attractions(city)       → OpenTripMap API
  ├─ get_country_info(country)   → RestCountries API
  ├─ get_travel_tips(dest)       → LLM-generated
  └─ build_itinerary(dest, days) → LLM-generated
```

### ReAct Loop Explained

The agent uses the **ReAct** (Reasoning + Acting) pattern:

1. **Reason** — LLM reads the user's query and thinks: *"To answer this, I need weather data"*
2. **Act** — LLM emits a tool call: `get_weather("Paris")`
3. **Observe** — Tool runs and returns: `"🌤 Paris: 18°C, Partly Cloudy"`
4. **Reason again** — LLM reads the result and either calls another tool or writes the final answer
5. **Repeat** until the LLM decides it has enough information

This is all handled automatically by **LangGraph's `create_react_agent`**.

---

## 🚀 Local Setup

### 1. Clone & Install

```bash
cd travel-agent
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
cp .env.example .env
# Edit .env and fill in your keys
```

### 3. Run

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## ☁️ Deploy on Azure App Service (Free F1 Tier)

### Step 1 — Create App Service

```bash
# Install Azure CLI, then:
az login
az group create --name travel-agent-rg --location eastus
az appservice plan create \
  --name travel-agent-plan \
  --resource-group travel-agent-rg \
  --sku F1 \          # FREE tier
  --is-linux

az webapp create \
  --resource-group travel-agent-rg \
  --plan travel-agent-plan \
  --name my-travel-agent-app \     # must be globally unique
  --runtime "PYTHON:3.11"
```

### Step 2 — Set Environment Variables on Azure

```bash
az webapp config appsettings set \
  --resource-group travel-agent-rg \
  --name my-travel-agent-app \
  --settings \
    AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/" \
    AZURE_OPENAI_API_KEY="your-key" \
    AZURE_OPENAI_DEPLOYMENT_NAME="gpt-35-turbo" \
    AZURE_OPENAI_API_VERSION="2024-02-01" \
    OPENWEATHER_API_KEY="your-key" \
    EXCHANGE_RATE_API_KEY="your-key" \
    OPENTRIPMAP_API_KEY="your-key"
```

### Step 3 — Set Startup Command

```bash
az webapp config set \
  --resource-group travel-agent-rg \
  --name my-travel-agent-app \
  --startup-file "python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0"
```

### Step 4 — Deploy Code

```bash
# Zip deploy
zip -r app.zip . -x "*.git*" -x "__pycache__/*" -x "*.env"

az webapp deployment source config-zip \
  --resource-group travel-agent-rg \
  --name my-travel-agent-app \
  --src app.zip
```

Your app will be live at: `https://my-travel-agent-app.azurewebsites.net`

---

## 🔍 Code Walkthrough

### `tools/travel_tools.py`

Each function decorated with `@tool` becomes a LangChain tool:
- The **docstring** is the tool's description — the LLM reads this to decide when to use it
- The **function signature** defines the arguments the LLM must provide
- **Fallbacks** are built in for every paid API — the app works even with zero API keys

### `agents/travel_agent.py`

```python
agent = create_react_agent(
    model=llm,           # Azure OpenAI instance
    tools=ALL_TOOLS,     # 6 tool definitions
    state_modifier=...,  # System prompt (Aria persona)
)
```

`create_react_agent` from LangGraph automatically builds the full ReAct loop as a compiled `StateGraph`. No manual node/edge wiring needed.

### `app.py`

- `@st.cache_resource` — agent is built once and reused across all requests
- `agent.stream(...)` — streams LangGraph events; we extract tool calls and final answers
- `st.session_state.messages` — persists conversation within the browser session
- Quick-action buttons inject pre-written prompts via `_pending_prompt` state trick

---

## 💬 Example Conversations

| User says | Tools used |
|-----------|------------|
| "Weather in Dubai?" | `get_weather` |
| "Plan 5 days in Kyoto, I love temples" | `get_weather` + `get_attractions` + `build_itinerary` |
| "Convert 500 GBP to Thai Baht" | `convert_currency` |
| "Tell me about Brazil" | `get_country_info` |
| "Is Vietnam safe to travel?" | `get_travel_tips` |
| "Best time to visit Iceland?" | `get_travel_tips` + `get_weather` |
