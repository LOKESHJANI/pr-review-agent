import time
import json
import os
import groq
from schemas.agent_outputs import CodeReaderOutput

client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))

def run(diff: str, pr_title: str) -> tuple[CodeReaderOutput, int, int]:
    start = time.monotonic()

    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1024,
        messages=[
            {
                "role": "system",
                "content": "You are a senior software engineer reviewing a pull request diff. Return only valid JSON, no markdown fences."
            },
            {
                "role": "user",
                "content": f"""PR title: {pr_title}

Diff:
<diff>
{diff[:6000]}
</diff>

Return this exact JSON:
{{
  "files_changed": [
    {{
      "filename": "path/to/file.py",
      "change_type": "added",
      "summary": "what changed",
      "key_functions": ["function_name"]
    }}
  ],
  "overall_summary": "2-3 sentence summary",
  "language": "Python",
  "complexity_estimate": "low"
}}

Return ONLY the JSON."""
            }
        ],
    )

    latency_ms = int((time.monotonic() - start) * 1000)
    tokens = message.usage.total_tokens
    data = json.loads(message.choices[0].message.content)
    output = CodeReaderOutput(**data)
    return output, tokens, latency_ms
