import time
import json
import os
import groq
from schemas.agent_outputs import BugDetectorOutput

client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))

def run(diff: str, file_summary: str) -> tuple[BugDetectorOutput, int, int]:
    start = time.monotonic()

    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1500,
        messages=[
            {
                "role": "system",
                "content": "You are a security and code quality expert. Identify real bugs only. Return only valid JSON, no markdown fences."
            },
            {
                "role": "user",
                "content": f"""Context: {file_summary}

Diff:
<diff>
{diff[:6000]}
</diff>

Return this exact JSON:
{{
  "findings": [
    {{
      "severity": "warning",
      "filename": "path/to/file.py",
      "line_hint": "around line 42",
      "description": "what the bug is",
      "fix_suggestion": "how to fix it"
    }}
  ],
  "overall_risk_score": 3.0
}}

If no bugs found, return empty findings array and score 0.0.
Return ONLY the JSON."""
            }
        ],
    )

    latency_ms = int((time.monotonic() - start) * 1000)
    tokens = message.usage.total_tokens
    data = json.loads(message.choices[0].message.content)
    output = BugDetectorOutput(**data)
    return output, tokens, latency_ms
