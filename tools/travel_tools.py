"""
tools/travel_tools.py
─────────────────────
All LangChain @tool definitions for the Travel Agent.

Each tool wraps a FREE external API:
  • WeatherTool        → OpenWeatherMap (free tier, 1k calls/day)
  • CurrencyTool       → ExchangeRate-API (free tier, 1.5k calls/month)
  • AttractionsTool    → OpenTripMap (free tier, 500 calls/day)
  • CountryInfoTool    → RestCountries (100% free, no key)
  • TravelTipsTool     → LLM-generated (no external API call)
  • ItineraryTool      → LLM-generated (no external API call)
"""

import os
import requests
from langchain_core.tools import tool


# ─────────────────────────────────────────────
# TOOL 1 — Weather
# ─────────────────────────────────────────────
@tool
def get_weather(city: str) -> str:
    """
    Fetch current weather for a given city using OpenWeatherMap's free API.

    Args:
        city: Name of the city (e.g. "Paris", "Tokyo")

    Returns:
        A human-readable weather summary string.
    """
    api_key = os.getenv("OPENWEATHER_API_KEY", "")

    # Fallback: use Open-Meteo (no key needed) via geocoding
    if not api_key or api_key.startswith("<"):
        return _get_weather_openmeteo(city)

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        temp      = data["main"]["temp"]
        feels     = data["main"]["feels_like"]
        humidity  = data["main"]["humidity"]
        desc      = data["weather"][0]["description"].capitalize()
        wind      = data["wind"]["speed"]
        country   = data["sys"]["country"]

        return (
            f"🌤 Weather in {city.title()}, {country}:\n"
            f"  • Condition : {desc}\n"
            f"  • Temperature: {temp}°C (feels like {feels}°C)\n"
            f"  • Humidity   : {humidity}%\n"
            f"  • Wind speed : {wind} m/s"
        )
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 404:
            return f"City '{city}' not found. Please check the spelling."
        return f"Weather service error: {e}"
    except Exception as e:
        return f"Could not fetch weather: {e}"


def _get_weather_openmeteo(city: str) -> str:
    """Open-Meteo fallback — no API key required."""
    try:
        # Step 1: geocode city name
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        geo = requests.get(geo_url, params={"name": city, "count": 1}, timeout=10).json()
        if not geo.get("results"):
            return f"Could not locate city: {city}"

        r       = geo["results"][0]
        lat, lon = r["latitude"], r["longitude"]
        name    = r.get("name", city)
        country = r.get("country", "")

        # Step 2: fetch weather
        wx_url = "https://api.open-meteo.com/v1/forecast"
        wx = requests.get(wx_url, params={
            "latitude": lat, "longitude": lon,
            "current_weather": True,
            "hourly": "relativehumidity_2m",
            "forecast_days": 1,
        }, timeout=10).json()

        cw   = wx.get("current_weather", {})
        temp = cw.get("temperature", "N/A")
        wind = cw.get("windspeed", "N/A")
        wc   = cw.get("weathercode", 0)

        wc_desc = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 51: "Light drizzle", 61: "Light rain", 71: "Light snow",
            80: "Rain showers", 95: "Thunderstorm",
        }.get(wc, f"Code {wc}")

        return (
            f"🌤 Weather in {name}, {country} (Open-Meteo):\n"
            f"  • Condition  : {wc_desc}\n"
            f"  • Temperature: {temp}°C\n"
            f"  • Wind speed : {wind} km/h"
        )
    except Exception as e:
        return f"Weather lookup failed: {e}"


# ─────────────────────────────────────────────
# TOOL 2 — Currency Converter
# ─────────────────────────────────────────────
@tool
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """
    Convert an amount between two currencies using ExchangeRate-API (free tier).

    Args:
        amount       : Amount to convert (e.g. 100.0)
        from_currency: ISO 4217 source currency code (e.g. "USD")
        to_currency  : ISO 4217 target currency code (e.g. "EUR")

    Returns:
        Conversion result as a readable string.
    """
    api_key = os.getenv("EXCHANGE_RATE_API_KEY", "")
    from_c  = from_currency.upper().strip()
    to_c    = to_currency.upper().strip()

    if not api_key or api_key.startswith("<"):
        # Fallback: use open.er-api.com (free, no key required for basic)
        url  = f"https://open.er-api.com/v6/latest/{from_c}"
        try:
            data = requests.get(url, timeout=10).json()
            rate = data["rates"].get(to_c)
            if not rate:
                return f"Currency code '{to_c}' not found."
            converted = round(amount * rate, 2)
            return (
                f"💱 Currency Conversion:\n"
                f"  {amount} {from_c} = {converted} {to_c}\n"
                f"  Exchange rate: 1 {from_c} = {rate} {to_c}"
            )
        except Exception as e:
            return f"Currency conversion failed: {e}"

    url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{from_c}/{to_c}/{amount}"
    try:
        data      = requests.get(url, timeout=10).json()
        result    = data.get("conversion_result", 0)
        rate      = data.get("conversion_rate", 0)
        return (
            f"💱 Currency Conversion:\n"
            f"  {amount} {from_c} = {result} {to_c}\n"
            f"  Exchange rate: 1 {from_c} = {rate} {to_c}"
        )
    except Exception as e:
        return f"Currency conversion failed: {e}"


# ─────────────────────────────────────────────
# TOOL 3 — Attractions / Points of Interest
# ─────────────────────────────────────────────
@tool
def get_attractions(city: str, limit: int = 5) -> str:
    """
    Retrieve top tourist attractions in a city via OpenTripMap (free tier).

    Args:
        city : City name to search attractions in.
        limit: How many attractions to return (default 5, max 10).

    Returns:
        Formatted list of attractions with descriptions.
    """
    api_key = os.getenv("OPENTRIPMAP_API_KEY", "")
    limit   = min(limit, 10)

    if not api_key or api_key.startswith("<"):
        return (
            f"⚠️ OpenTripMap API key not set.\n"
            f"Popular things to do in {city.title()} typically include:\n"
            f"  • Visit historic old town / city centre\n"
            f"  • Explore local museums & art galleries\n"
            f"  • Try local cuisine at food markets\n"
            f"  • Take a walking tour\n"
            f"  • Visit parks and scenic viewpoints\n"
            f"(Add your OPENTRIPMAP_API_KEY to .env for live results)"
        )

    try:
        # Step 1: geocode
        geo_url = "https://api.opentripmap.com/0.1/en/places/geoname"
        geo = requests.get(geo_url, params={"name": city, "apikey": api_key}, timeout=10).json()
        lat, lon = geo["lat"], geo["lon"]

        # Step 2: fetch POIs within 10 km radius
        poi_url = "https://api.opentripmap.com/0.1/en/places/radius"
        params  = {
            "radius": 10000, "lon": lon, "lat": lat,
            "kinds": "interesting_places", "limit": limit,
            "format": "json", "apikey": api_key,
        }
        pois = requests.get(poi_url, params=params, timeout=10).json()

        if not pois:
            return f"No attractions found for {city}."

        lines = [f"🗺 Top {len(pois)} Attractions in {city.title()}:\n"]
        for i, poi in enumerate(pois, 1):
            name = poi.get("name") or "Unnamed site"
            kind = poi.get("kinds", "").split(",")[0].replace("_", " ").title()
            lines.append(f"  {i}. {name}  [{kind}]")

        return "\n".join(lines)
    except Exception as e:
        return f"Could not fetch attractions: {e}"


# ─────────────────────────────────────────────
# TOOL 4 — Country Information
# ─────────────────────────────────────────────
@tool
def get_country_info(country_name: str) -> str:
    """
    Retrieve detailed country information (capital, currency, language, region, etc.)
    using the completely free RestCountries API — no API key required.

    Args:
        country_name: Name of the country (e.g. "France", "Japan")

    Returns:
        Formatted country fact sheet.
    """
    url = f"https://restcountries.com/v3.1/name/{country_name}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data     = resp.json()[0]
        name     = data["name"]["common"]
        capital  = data.get("capital", ["N/A"])[0]
        region   = data.get("region", "N/A")
        sub      = data.get("subregion", "N/A")
        pop      = f"{data.get('population', 0):,}"
        area     = f"{data.get('area', 0):,} km²"

        currencies = ", ".join(
            f"{v['name']} ({v.get('symbol','')})"
            for v in data.get("currencies", {}).values()
        ) or "N/A"

        languages = ", ".join(data.get("languages", {}).values()) or "N/A"
        timezones = ", ".join(data.get("timezones", [])[:3]) or "N/A"
        driving   = data.get("car", {}).get("side", "N/A")

        return (
            f"🌍 Country Info: {name}\n"
            f"  • Capital    : {capital}\n"
            f"  • Region     : {sub}, {region}\n"
            f"  • Population : {pop}\n"
            f"  • Area       : {area}\n"
            f"  • Currency   : {currencies}\n"
            f"  • Languages  : {languages}\n"
            f"  • Timezones  : {timezones}\n"
            f"  • Driving    : {driving.title()} side of road"
        )
    except requests.exceptions.HTTPError:
        return f"Country '{country_name}' not found. Try full official name."
    except Exception as e:
        return f"Country info lookup failed: {e}"


# ─────────────────────────────────────────────
# TOOL 5 — Travel Tips (LLM-generated, no API)
# ─────────────────────────────────────────────
@tool
def get_travel_tips(destination: str) -> str:
    """
    Return general travel tips for a destination based on common travel knowledge.
    This tool synthesises tips from the agent's own knowledge — no external API needed.

    Args:
        destination: City or country name

    Returns:
        A list of practical travel tips for the destination.
    """
    # This tool is intentionally lightweight — the agent's LLM will populate
    # this at runtime. We return a structured prompt hint so the LLM knows
    # what category of tips to supply.
    return (
        f"[TRAVEL TIPS REQUEST for: {destination}]\n"
        "Please provide 6-8 concise, practical travel tips covering:\n"
        "  1. Best time to visit / seasons\n"
        "  2. Local customs & etiquette\n"
        "  3. Safety advice\n"
        "  4. Transport within the destination\n"
        "  5. Must-try local food\n"
        "  6. Approximate daily budget range\n"
        "  7. Visa & entry requirements (general)\n"
        "  8. Language / communication tips"
    )


# ─────────────────────────────────────────────
# TOOL 6 — Itinerary Builder (LLM-generated)
# ─────────────────────────────────────────────
@tool
def build_itinerary(destination: str, days: int, interests: str) -> str:
    """
    Build a day-by-day travel itinerary for a destination.
    The agent constructs this from its knowledge — no external API needed.

    Args:
        destination: Target city/country for the trip.
        days       : Duration of the trip in days.
        interests  : Comma-separated list of traveller interests
                     (e.g. "history, food, nature, nightlife").

    Returns:
        A structured day-by-day itinerary prompt for the LLM to complete.
    """
    return (
        f"[ITINERARY REQUEST]\n"
        f"Destination : {destination}\n"
        f"Duration    : {days} days\n"
        f"Interests   : {interests}\n\n"
        "Please create a detailed day-by-day itinerary. For each day include:\n"
        "  • Morning activity (with brief description)\n"
        "  • Afternoon activity\n"
        "  • Evening activity / dinner recommendation\n"
        "  • Practical tip for that day\n"
        "Format with clear Day 1, Day 2 … headings."
    )


# ─────────────────────────────────────────────
# Export all tools as a list for the agent
# ─────────────────────────────────────────────
ALL_TOOLS = [
    get_weather,
    convert_currency,
    get_attractions,
    get_country_info,
    get_travel_tips,
    build_itinerary,
]
