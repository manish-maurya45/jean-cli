from .bash import bash, BASH_TOOL_SCHEMAS
from .filesystemtools import read_file, write_file, str_replace, READ_TOOL_SCHEMAS, WRITE_TOOL_SCHEMAS, REPLACE_TOOL_SCHEMAS
from .skills import read_skill,READ_SKILL_TOOL_SCHEMAS
from .todos import write_todos, TODOS_TOOL_SCHEMAS

TOOLS = {
    "bash": bash,
    "read_file": read_file,
    "write_file": write_file,
    "str_replace": str_replace,
    "read_skill": read_skill,
    "write_todos": write_todos,
}

TOOL_SCHEMAS = [
    BASH_TOOL_SCHEMAS,
    READ_TOOL_SCHEMAS,
    WRITE_TOOL_SCHEMAS,
    REPLACE_TOOL_SCHEMAS,
    READ_SKILL_TOOL_SCHEMAS,
    TODOS_TOOL_SCHEMAS,
]