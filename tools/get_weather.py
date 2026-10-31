#get_weather.py
import requests
import json

def get_weather(city):
    try:
        resp = requests.get(
            f"https://wttr.in/{city}",
            params={"format": "j1"},
            headers={"User-Agent": "weather-agent"},
            timeout=15,
        )
        resp.raise_for_status()
        current = resp.json()["current_condition"][0]

        return json.dumps({
            "city": city,
            "temp_c": current["temp_C"],
            "feels_like_c": current["FeelsLikeC"],
            "humidity_percent": current["humidity"],
        })
    except Exception as e:
        return json.dumps({"error": f"Could not fetch weather for {city}: {e}"})

WEATHER_TOOL_SCHEMA = {
    "type": "function",
    "name": "get_weather",
    "description": "Get the current weather for a city.",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name, e.g. 'Hyderabad'",
            }
        },
        "required": ["city"],
        "additionalProperties": False,
    },
    "strict": True,
}