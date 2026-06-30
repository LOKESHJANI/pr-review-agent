import hashlib
import hmac
import json
import os
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from db.database import get_db
from db.models import Review
from agents.graph import run_review_graph

router = APIRouter()


def verify_signature(payload: bytes, signature: str) -> bool:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").encode()
    expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(payload_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event")
    data = json.loads(payload_bytes)

    if event == "pull_request" and data.get("action") in ("opened", "synchronize"):
        pr = data["pull_request"]
        installation_id = data["installation"]["id"]
        repo_full = data["repository"]["full_name"]
        owner, repo_name = repo_full.split("/")

        review = Review(
            repo=repo_full,
            pr_number=pr["number"],
            pr_title=pr["title"],
            pr_url=pr["html_url"],
            status="pending",
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)

        background_tasks.add_task(
            run_review_graph,
            review_id=str(review.id),
            installation_id=installation_id,
            owner=owner,
            repo=repo_name,
            pr_number=pr["number"],
        )

    return {"status": "received"}
