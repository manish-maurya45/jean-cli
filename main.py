
import json

from llm import SYSTEM_PROMPT, call_llm
from tools import TOOLS
from ui import ui

def main():
    ui.banner()

    # Responses API input history
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    while True:
        user_input = ui.ask()

        if not user_input:
            break

        messages.append({
            "role": "user",
            "content": user_input,
        })

        while True:
            with ui.working():
                response, usage = call_llm(messages)

            # Preserve model output items, including function calls.
            messages.extend(
                item.model_dump(exclude_none=True)
                for item in response.output
            )

            ui.usage(usage)

            if response.output_text:
                ui.agent(response.output_text)

            tool_calls = [
                item
                for item in response.output
                if item.type == "function_call"
            ]

            if not tool_calls:
                break

            for tool_call in tool_calls:
                args = json.loads(tool_call.arguments)
                tool = TOOLS.get(tool_call.name)

                if tool is None:
                    result = f"Unknown tool: {tool_call.name}"
                else:
                    try:
                        result = tool(**args)
                    except Exception as exc:
                        result = f"Tool error: {exc}"

                ui.tool(tool_call.name, args, result)

                messages.append({
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": str(result),
                })

    ui.summary()


if __name__ == "__main__":
    main()
