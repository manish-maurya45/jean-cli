
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

TOOLS = {
    "get_weather": get_weather,
}

TOOL_SCHEMAS = [WEATHER_TOOL_SCHEMA]


def main():
    user_input = input("Enter your prompt> ")

    history = [{"role": "user", "content": user_input}]

    response = client.responses.create(
        model="deepseek/deepseek-v4-flash",
        instructions=SYSTEM_PROMPT,
        input=history,
        tools=TOOL_SCHEMAS,
    )

    while True:
        tool_calls = [
            item for item in response.output if item.type == "function_call"
        ]

        if not tool_calls:
            break

        history.extend(response.output)
        tool_outputs = []

        for tool_call in tool_calls:
            tool_args = json.loads(tool_call.arguments)
            print(f"\nTool: {tool_call.name}")

            tool_fn = TOOLS.get(tool_call.name)

            if tool_fn:
                try:
                    tool_result = tool_fn(**tool_args)
                except Exception as exc:
                    tool_result = f"Tool error: {exc}"
            else:
                tool_result = f"Unknown tool: {tool_call.name}"

            print(tool_result)

            tool_outputs.append({
                "type": "function_call_output",
                "call_id": tool_call.call_id,
                "output": str(tool_result),
            })

        history.extend(tool_outputs)

        response = client.responses.create(
            model="deepseek/deepseek-v4-flash",
            instructions=SYSTEM_PROMPT,
            input=history,
            tools=TOOL_SCHEMAS,
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