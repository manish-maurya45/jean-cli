
import json

from llm import SYSTEM_PROMPT, call_llm
from tools import TOOLS
from ui import ui
from commands import SlashCompleter, all_commands

from context import reminder


def new_history():
    return [{"role": "system", "content": SYSTEM_PROMPT}]


def handle_slash(line, messages):
    """Returns (action, payload). action: 'exit' | 'handled' | 'send'."""
    cmd, _, args = line.partition(" ")
    cmd = cmd.lower()
    args = args.strip()

    if cmd in ("/exit", "/quit"):
        return "exit", None

    if cmd == "/clear":
        messages[:] = new_history()
        ui.banner()
        return "handled", None

    if cmd == "/help":
        ui.help(all_commands())
        return "handled", None

    commands = all_commands()
    if cmd in commands:  # a skill: /pdf extract the tables from report.pdf
        name = cmd[1:]
        prompt = (
            f"Use the '{name}' skill for this task. "
            f"Open it with read_skill first, then follow its instructions."
        )
        if args:
            prompt += f"\n\nTask: {args}"
        return "send", prompt

    ui.notice(f"Unknown command {cmd}. Type /help to see what's available.", style="red")
    return "handled", None


def main():
    ui.banner()

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    while True:
        user_input = ui.ask(completer=SlashCompleter())

        if user_input is None:      # ctrl-c / ctrl-d
            break
        if not user_input:          # empty enter: ignore instead of quitting
            continue

        if user_input.startswith("/"):
            action, payload = handle_slash(user_input, messages)
            if action == "exit":
                break
            if action == "handled":
                continue
            user_input = payload    # action == "send"

        messages.append({
            "role": "user",
            "content": user_input,
        })

        while True:
            with ui.working():
                response, usage = call_llm(messages + [reminder()])

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
