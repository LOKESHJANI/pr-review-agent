import httpx
import jwt
import time
import os
from pathlib import Path


def _get_jwt() -> str:
    private_key = Path(os.getenv("GITHUB_PRIVATE_KEY_PATH", "./github_private_key.pem")).read_text()
    app_id = os.getenv("GITHUB_APP_ID")
    payload = {
        "iat": int(time.time()) - 60,
        "exp": int(time.time()) + 600,
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


async def get_installation_token(installation_id: int) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {_get_jwt()}",
                "Accept": "application/vnd.github+json",
            },
        )
        resp.raise_for_status()
        return resp.json()["token"]


async def get_pr_diff(token: str, owner: str, repo: str, pr_number: int) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.diff",
            },
        )
        resp.raise_for_status()
        return resp.text


async def get_pr_files(token: str, owner: str, repo: str, pr_number: int) -> list:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def post_pr_comment(token: str, owner: str, repo: str, pr_number: int, body: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json={"body": body},
        )
        resp.raise_for_status()
        return resp.json()["html_url"]
    
async def post_check_run(
    token: str,
    owner: str,
    repo: str,
    sha: str,
    conclusion: str,  # "success" | "failure" | "neutral"
    summary: str,
    details: str,
) -> dict:
    """
    Post a GitHub Check Run named 'AI Review'.
    conclusion: 'success' | 'failure' | 'neutral'
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/check-runs",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
            },
            json={
                "name": "AI Review",
                "head_sha": sha,
                "status": "completed",
                "conclusion": conclusion,
                "output": {
                    "title": "AI Code Review",
                    "summary": summary,
                    "text": details,
                },
            },
        )
        resp.raise_for_status()
        return resp.json()
