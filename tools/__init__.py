from .get_weather import get_weather, WEATHER_TOOL_SCHEMA

TOOLS = {
    "get_weather": get_weather,
}

TOOL_SCHEMAS = [
    WEATHER_TOOL_SCHEMA,
]