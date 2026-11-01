
import subprocess


def bash(command):
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
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
