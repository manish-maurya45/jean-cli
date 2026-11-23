import sandbox
from ui import ui

def bash(command):
    cmd_preview = command if len(command) <= 30 else command[:27] + "..."
    with ui.working(f"executing {cmd_preview} bash command in the sandbox {sandbox.name()} ..."):
        result = sandbox.run(command)
    return result.stdout + result.stderr

BASH_TOOL_SCHEMAS = {
    "type": "function",
    "name": "bash",
    "description": "Run a shell command.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {"type": "string"}
        },
        "required": ["command"],
        "additionalProperties": False,
    },
    "strict": True,
}



if __name__ == "__main__":
    print("current directory:", bash("pwd"))
