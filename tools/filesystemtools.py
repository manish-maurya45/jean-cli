def read_file(path: str) -> str:
    """Read a file and return its contents."""
    with open(path) as f:
        return f.read()

def write_file(path: str, content: str) -> str:
    """Create a file, or overwrite it if it already exists."""
    with open(path, "w") as f:
        f.write(content)
    return f"Wrote {path}"


def str_replace(path, old_str, new_str, allow_multi_edit=False):
    """Swap exact text in a file. old_str must match exactly once."""
    with open(path) as f:
        content = f.read()

    count = content.count(old_str)
    if count == 0:
        return f"Error: old_str was not found in {path}"
    if count > 1 and not allow_multi_edit:
        return (
            f"Error: old_str matches {count} times in {path}. "
            "Add surrounding lines to make it unique, "
            "or set allow_multi_edit to replace them all."
        )

    with open(path, "w") as f:
        f.write(content.replace(old_str, new_str))
    return f"Replaced {count} match(es) in {path}"

READ_TOOL_SCHEMAS = {
    "type": "function",
    "name": "read_file",
    "description": "Read a file and return its contents.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read",
            }
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    "strict": True,
}

WRITE_TOOL_SCHEMAS = {
    "type": "function",
    "name": "write_file",
    "description": "Create a file, or overwrite it if it already exists.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File to write",
            },
            "content": {
                "type": "string",
                "description": "The full contents",
            },
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    },
    "strict": True,
}

REPLACE_TOOL_SCHEMAS  =  {
    "type": "function",
    "name": "str_replace",
    "description": (
        "Replace exact text in a file. old_str must appear exactly once, "
        "so include surrounding lines if needed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File to edit",
            },
            "old_str": {
                "type": "string",
                "description": "Exact text to find",
            },
            "new_str": {
                "type": "string",
                "description": "Text to put in its place",
            },
            "allow_multi_edit": {
                "type": "boolean",
                "description": "Replace every match instead of failing",
            },
        },
        "required": [
            "path",
            "old_str",
            "new_str",
            "allow_multi_edit",
        ],
        "additionalProperties": False,
    },
    "strict": True,
}