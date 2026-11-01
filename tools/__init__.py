from .bash import bash, BASH_TOOL_SCHEMAS
from .filesystemtools import read_file, write_file, str_replace, READ_TOOL_SCHEMAS, WRITE_TOOL_SCHEMAS, REPLACE_TOOL_SCHEMAS


TOOLS = {
    "bash": bash,
    "read_file": read_file,
    "write_file": write_file,
    "str_replace": str_replace,
}

TOOL_SCHEMAS = [
    BASH_TOOL_SCHEMAS,
    READ_TOOL_SCHEMAS,
    WRITE_TOOL_SCHEMAS,
    REPLACE_TOOL_SCHEMAS,
]