
import os
import json
import requests
from dotenv import load_dotenv
from openai import OpenAI
from tools import TOOLS, TOOL_SCHEMAS

load_dotenv()

client = OpenAI(
    base_url=os.environ["BASE_URL"],
    api_key=os.environ["API_KEY"],
)

SYSTEM_PROMPT = """
You are a coding agent.

You have access to tools. Use them whenever they help you answer the request,
such as looking up information or performing actions you can't do on your own.
If no tool is needed, answer directly.
"""

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