import time
import json
import os
import groq
from schemas.agent_outputs import TestSuggesterOutput

client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))

def run(diff: str, key_functions: list[str]) -> tuple[TestSuggesterOutput, int, int]:
    start = time.monotonic()
    functions_hint = ", ".join(key_functions) if key_functions else "unknown"

    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1500,
        messages=[
            {
                "role": "system",
                "content": "You are a test engineering expert. Return only valid JSON, no markdown fences."
            },
            {
                "role": "user",
                "content": f"""Key changed functions: {functions_hint}

Diff:
<diff>
{diff[:5000]}
</diff>

Return this exact JSON:
{{
  "suggested_tests": [
    {{
      "function_name": "function_name",
      "test_description": "what this test verifies",
      "pytest_stub": "def test_example():\\n    result = func()\\n    assert result is not None"
    }}
  ],
  "coverage_gaps": ["area with no tests"]
}}

Return ONLY the JSON."""
            }
        ],
    )

    latency_ms = int((time.monotonic() - start) * 1000)
    tokens = message.usage.total_tokens
    data = json.loads(message.choices[0].message.content)
    output = TestSuggesterOutput(**data)
    return output, tokens, latency_ms
