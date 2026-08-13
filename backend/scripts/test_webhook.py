

import hashlib
import hmac
import json
import os
import httpx

SECRET = os.environ["GITHUB_WEBHOOK_SECRET"]

payload = {
    "action": "opened",
    "installation": {"id": 143167179},
    "repository": {
        "full_name": "LOKESHJANI/pr-agent-test-repo",
    },
    "pull_request": {
        "number": 2,
        "title": "Test PR for AI review",
        "html_url": "https://github.com/LOKESHJANI/pr-agent-test-repo/pull/2",
    },
}

body = json.dumps(payload, separators=(",", ":")).encode()  # compact JSON, no spaces
signature = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

resp = httpx.post(
    "http://127.0.0.1:8000/webhook/github",
    headers={
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": signature,
        "Content-Type": "application/json",
    },
    json=payload,
)

print(resp.status_code, resp.text)
