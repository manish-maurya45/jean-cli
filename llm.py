
import os
import json
import requests
from dotenv import load_dotenv
from openai import OpenAI
from tools import TOOL_SCHEMAS

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

