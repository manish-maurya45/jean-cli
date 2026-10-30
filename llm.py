
import os
import json
from dotenv import load_dotenv

load_dotenv() 

from openai import OpenAI

client = OpenAI(
    base_url=os.environ["BASE_URL"],
    api_key=os.environ["API_KEY"],
)

SYSTEM_PROMPT = """
You are a coding agent. Your job is to code. Always code.
"""


def main():
    user_input = input("Enter your prompt> ")

    response = client.responses.create(
        model="deepseek/deepseek-v4-flash",
        instructions=SYSTEM_PROMPT,
        input=user_input,
    )

    # Extract the generated response
    output = response.output_text

    # Extract token usage details
    usage_data = response.usage

    usage = {
        "prompt_tokens": usage_data.input_tokens,
        "completion_tokens": usage_data.output_tokens,
        "total_tokens": usage_data.total_tokens,
        "reasoning_tokens": (
            usage_data.output_tokens_details.reasoning_tokens
            if usage_data.output_tokens_details
            else None
        ),
        "cached_tokens": (
            usage_data.input_tokens_details.cached_tokens if usage_data.input_tokens_details else None
        ),
    }

    print(output)
   
    print("\nToken Usage:")
    print(json.dumps(usage, indent=4))


if __name__ == "__main__":
    main()