
import os
import json
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.environ["BASE_URL"],
    api_key=os.environ["API_KEY"],
)

SYSTEM_PROMPT = """
You are a coding agent. Always code.
Use the get_weather tool to look up current weather for a city.
"""


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


def main():
    user_input = input("Enter your prompt> ")

    history = [{"role": "user", "content": user_input}]

    response = client.responses.create(
        model="deepseek/deepseek-v4-flash",
        instructions=SYSTEM_PROMPT,
        input=history,
        tools=[WEATHER_TOOL_SCHEMA],
    )

    while True:
        calls = [
            item for item in response.output
            if item.type == "function_call"
        ]

        if not calls:
            break

        history.extend(response.output)
        outputs = []

        for call in calls:
            city = json.loads(call.arguments)["city"]
            print(f"\nTool: {call.name}")

            result = get_weather(city)

            outputs.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": result,
            })

        history.extend(outputs)

        response = client.responses.create(
            model="deepseek/deepseek-v4-flash",
            instructions=SYSTEM_PROMPT,
            input=history,
            tools=[WEATHER_TOOL_SCHEMA],
        )

    print("\nAgent:\n", response.output_text)

    usage = response.usage
    print("\nUsage:")
    print(json.dumps({
        "prompt_tokens": usage.input_tokens,
        "completion_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "reasoning_tokens": getattr(
            usage.output_tokens_details, "reasoning_tokens", None
        ),
        "cached_tokens": getattr(
            usage.input_tokens_details, "cached_tokens", None
        ),
    }, indent=4))


if __name__ == "__main__":
    main()