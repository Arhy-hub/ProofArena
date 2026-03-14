"""Quick test to verify Anthropic API access."""

import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=64,
    messages=[{"role": "user", "content": "Tell me about india"}],
)

print(response.content[0].text)
