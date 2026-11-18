
import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from tools import TOOL_SCHEMAS
from skills import skills_prompt

load_dotenv()

client = OpenAI(
    base_url=os.environ["BASE_URL"],
    api_key=os.environ["API_KEY"],
)


SYSTEM_PROMPT = f"""
You are a coding agent. Always code.
Use bash to inspect files and execute commands.


For any task that takes more than one step, call write_todos first and plan it
out. Send the whole list every time you call it - it replaces the old one.
Keep exactly one task in_progress, mark it done the moment it is finished, and
move the next one to in_progress in the same call. Do not batch up completions
at the end. Skip the tool entirely for single-step tasks; it is noise there.

The current list is injected back to you every turn inside <todos> tags, so
that block - not the transcript - is the truth about where you are.

Your current working directory is: {os.getcwd()}

You have below skills available. Each one is a set of instructions for a task.
If a skill matches what the user wants, call read_skill first and follow it.

{skills_prompt()}
"""

def call_llm(messages):
    response = client.responses.create(
        model="deepseek/deepseek-v4-flash",
        instructions=SYSTEM_PROMPT,
        input=messages,
        tools=TOOL_SCHEMAS,
        max_output_tokens=4096,
    )

    usage_data = response.usage

    usage = {
        "prompt_tokens": usage_data.input_tokens if usage_data else 0,
        "completion_tokens": usage_data.output_tokens if usage_data else 0,
        "reasoning_tokens": (
            getattr(
                usage_data.output_tokens_details,
                "reasoning_tokens",
                None,
            )
            if usage_data and usage_data.output_tokens_details
            else None
        ),
        "cached_tokens": (
            getattr(
                usage_data.input_tokens_details,
                "cached_tokens",
                None,
            )
            if usage_data and usage_data.input_tokens_details
            else None
        ),
    }

    return response, usage


if __name__ == "__main__":
    print(SYSTEM_PROMPT)

