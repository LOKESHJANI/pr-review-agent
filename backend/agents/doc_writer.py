import time
import json
import os
import groq
from schemas.agent_outputs import DocWriterOutput

client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))

def run(diff: str) -> tuple[DocWriterOutput, int, int]:
    start = time.monotonic()

    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1500,
        messages=[
            {
                "role": "system",
                "content": "You are a technical documentation expert. Return only valid JSON, no markdown fences."
            },
            {
                "role": "user",
                "content": f"""Review this diff and suggest docstring improvements:

<diff>
{diff[:5000]}
</diff>

Return this exact JSON:
{{
  "improvements": [
    {{
      "filename": "path/to/file.py",
      "function_name": "function_name",
      "current_doc": "existing docstring or none",
      "improved_doc": "improved docstring"
    }}
  ],
  "missing_docs_count": 0
}}

If no improvements needed return empty improvements array.
Return ONLY the JSON."""
            }
        ],
    )

    latency_ms = int((time.monotonic() - start) * 1000)
    tokens = message.usage.total_tokens
    data = json.loads(message.choices[0].message.content)
    output = DocWriterOutput(**data)
    return output, tokens, latency_ms
