import os
import sys
import httpx

# Ensure project root is on the path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # .../backend/scripts
PROJECT_ROOT = os.path.dirname(BASE_DIR)               # .../backend
sys.path.append(PROJECT_ROOT)

from services.github_client import _get_jwt  # use the existing helper

jwt = _get_jwt()
print("JWT prefix:", jwt[:30], "...")  # quick sanity check

headers = {
    "Authorization": f"Bearer {jwt}",
    "Accept": "application/vnd.github+json",
}

resp = httpx.get("https://api.github.com/app/installations", headers=headers)
print("Status:", resp.status_code)
print(resp.text)