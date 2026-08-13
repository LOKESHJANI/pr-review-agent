import jwt
import time
import httpx
from pathlib import Path

APP_ID = 4178544  # from your .env
INSTALLATION_ID = 143415603
PRIVATE_KEY_PATH = Path("./github_private_key.pem")

private_key = PRIVATE_KEY_PATH.read_text()

jwt_payload = {
    "iat": int(time.time()) - 60,
    "exp": int(time.time()) + 600,
    "iss": APP_ID,
}

jwt_token = jwt.encode(jwt_payload, private_key, algorithm="RS256")

resp = httpx.post(
    f"https://api.github.com/app/installations/{INSTALLATION_ID}/access_tokens",
    headers={
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    },
)

print(resp.status_code)
print(resp.text)
