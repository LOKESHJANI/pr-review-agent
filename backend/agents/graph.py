import re
import uuid
from datetime import datetime, timezone
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from db.database import AsyncSessionLocal
from db.models import Review, AgentOutput, TraceEvent
from schemas.agent_outputs import (
    CodeReaderOutput,
    BugDetectorOutput,
    TestSuggesterOutput,
    DocWriterOutput,
)
from agents.code_reader import run as run_code_reader_agent
from agents.bug_detector import run as run_bug_detector_agent
from agents.test_suggester import run as run_test_suggester_agent
from agents.doc_writer import run as run_doc_writer_agent
from agents.aggregator import (
    format_github_comment,
    compute_consensus_risk_score,
)
from services.github_client import (
    get_installation_token,
    get_pr_diff,
    get_pr_files,
    post_pr_comment,
    post_check_run,
)

from langgraph.graph import StateGraph, END


# ──────────────────────────────────────────────────────────────
# State definition
# ──────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    review_id: str
    installation_id: int
    owner: str
    repo: str
    pr_number: int
    sha: str
    diff: str
    code_reader_output: CodeReaderOutput
    bug_detector_output: BugDetectorOutput
    test_suggester_output: TestSuggesterOutput
    doc_writer_output: DocWriterOutput


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _parse_line_hint_start(line_hint: str) -> int | None:
    if not line_hint:
        return None
    m = re.search(r"\d+", line_hint)
    return int(m.group()) if m else None


def _parse_line_hint_end(line_hint: str) -> int | None:
    if not line_hint:
        return None
    nums = re.findall(r"\d+", line_hint)
    return int(nums[-1]) if len(nums) > 1 else _parse_line_hint_start(line_hint)


async def save_trace(db: AsyncSession, review_id: str, event_type: str, agent_name: str, payload: dict) -> None:
    db.add(
        TraceEvent(
            review_id=uuid.UUID(review_id),
            event_type=event_type,
            agent_name=agent_name,
            payload=payload,
        )
    )
    await db.commit()


# ──────────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────────

async def fetch_pr_data(state: AgentState) -> AgentState:
    async with AsyncSessionLocal() as db:
        await save_trace(db, state["review_id"], "agent_started", "fetch_pr", {})
        token = await get_installation_token(state["installation_id"])
        diff = await get_pr_diff(token, state["owner"], state["repo"], state["pr_number"])
        files = await get_pr_files(token, state["owner"], state["repo"], state["pr_number"])

        # Get SHA from the first file’s sha (or you can fetch PR metadata if needed)
        sha = files[0]["sha"] if files else ""

        review = await db.get(Review, uuid.UUID(state["review_id"]))
        if review is None:
            review = Review(
                id=uuid.UUID(state["review_id"]),
                repo=f"{state['owner']}/{state['repo']}",
                pr_number=state["pr_number"],
                pr_title="",
                pr_url=f"https://github.com/{state['owner']}/{state['repo']}/pull/{state['pr_number']}",
                status="running",
            )
            db.add(review)

        await db.commit()
        await save_trace(
            db,
            state["review_id"],
            "agent_done",
            "fetch_pr",
            {"diff_len": len(diff), "files_count": len(files)},
        )

    return {
        **state,
        "diff": diff,
        "sha": sha,
    }


async def run_code_reader(state: AgentState) -> AgentState:
    async with AsyncSessionLocal() as db:
        await save_trace(db, state["review_id"], "agent_started", "code_reader", {})
        output, tokens, latency = run_code_reader_agent(state["diff"], f"PR #{state['pr_number']}")
        db.add(
            AgentOutput(
                review_id=uuid.UUID(state["review_id"]),
                agent_name="code_reader",
                output=output.model_dump(),
                tokens_used=tokens,
                latency_ms=latency,
            )
        )
        await db.commit()
        await save_trace(
            db,
            state["review_id"],
            "agent_done",
            "code_reader",
            {"tokens": tokens, "files": len(output.files_changed)},
        )
    return {**state, "code_reader_output": output}


async def run_bug_detector(state: AgentState) -> AgentState:
    async with AsyncSessionLocal() as db:
        await save_trace(db, state["review_id"], "agent_started", "bug_detector", {})
        file_summary = f"PR #{state['pr_number']} in {state['owner']}/{state['repo']}"
        output, tokens, latency = run_bug_detector_agent(state["diff"], file_summary)
        db.add(
            AgentOutput(
                review_id=uuid.UUID(state["review_id"]),
                agent_name="bug_detector",
                output=output.model_dump(),
                tokens_used=tokens,
                latency_ms=latency,
            )
        )
        await db.commit()
        await save_trace(
            db,
            state["review_id"],
            "agent_done",
            "bug_detector",
            {"tokens": tokens, "findings": len(output.findings)},
        )
    return {**state, "bug_detector_output": output}


async def run_test_suggester(state: AgentState) -> AgentState:
    async with AsyncSessionLocal() as db:
        await save_trace(db, state["review_id"], "agent_started", "test_suggester", {})
        key_functions = [
            f.key_functions
            for f in state["code_reader_output"].files_changed
        ]
        # Flatten list of lists
        key_functions_flat = [fn for sublist in key_functions for fn in sublist]
        output, tokens, latency = run_test_suggester_agent(state["diff"], key_functions_flat)
        db.add(
            AgentOutput(
                review_id=uuid.UUID(state["review_id"]),
                agent_name="test_suggester",
                output=output.model_dump(),
                tokens_used=tokens,
                latency_ms=latency,
            )
        )
        await db.commit()
        await save_trace(
            db,
            state["review_id"],
            "agent_done",
            "test_suggester",
            {"tokens": tokens, "tests_suggested": len(output.suggested_tests)},
        )
    return {**state, "test_suggester_output": output}


async def run_doc_writer(state: AgentState) -> AgentState:
    async with AsyncSessionLocal() as db:
        await save_trace(db, state["review_id"], "agent_started", "doc_writer", {})
        output, tokens, latency = run_doc_writer_agent(state["diff"])
        db.add(
            AgentOutput(
                review_id=uuid.UUID(state["review_id"]),
                agent_name="doc_writer",
                output=output.model_dump(),
                tokens_used=tokens,
                latency_ms=latency,
            )
        )
        await db.commit()
        await save_trace(
            db,
            state["review_id"],
            "agent_done",
            "doc_writer",
            {"tokens": tokens, "improvements": len(output.improvements)},
        )
    return {**state, "doc_writer_output": output}


# ──────────────────────────────────────────────────────────────
# Aggregator + Check Run
# ──────────────────────────────────────────────────────────────

async def aggregate_and_post(state: AgentState) -> AgentState:
    async with AsyncSessionLocal() as db:
        await save_trace(db, state["review_id"], "agent_started", "aggregator", {})

        # 1. Build consensus_findings from bug_detector findings
        consensus_findings = []
        for f in state["bug_detector_output"].findings:
            consensus_findings.append(
                {
                    "severity": f.severity,
                    "file_path": f.filename,
                    "line_start": _parse_line_hint_start(f.line_hint),
                    "line_end": _parse_line_hint_end(f.line_hint),
                    "description": f.description,
                    "fix_suggestion": f.fix_suggestion,
                    "consensus_score": 1.0,  # single-agent for now
                    "agreeing_agents": ["bug_detector"],
                }
            )

        # 2. Format comment with consensus findings
        comment_body = format_github_comment(
            state["code_reader_output"],
            state["bug_detector_output"],
            state["test_suggester_output"],
            state["doc_writer_output"],
            consensus_findings=consensus_findings,
        )

        # 3. Compute consensus-based risk score (0–10)
        risk = compute_consensus_risk_score(consensus_findings)

        token = await get_installation_token(state["installation_id"])

        # 4. Post PR comment
        comment_url = await post_pr_comment(
            token, state["owner"], state["repo"], state["pr_number"], comment_body
        )

        # 5. Post GitHub Check Run
        has_blocking = any(
            cf["severity"] in ("critical", "high", "warning")
            and cf.get("consensus_score", 0.5) >= 0.5
            for cf in consensus_findings
        )
        conclusion = "failure" if has_blocking else "success"

        summary = (
            f"AI Review: {conclusion.upper()}. "
            f"Risk score: {risk:.1f}/10. "
            f"Findings: {len(consensus_findings)}."
        )

        details_lines = ["## AI Code Review\n"]
        for sev in ["critical", "high", "warning", "medium", "low"]:
            findings = [f for f in consensus_findings if f["severity"] == sev]
            if not findings:
                continue
            details_lines.append(f"### {sev.capitalize()}\n")
            for f in findings:
                loc = ""
                if f.get("file_path"):
                    loc = f" in `{f['file_path']}`"
                    if f.get("line_start") is not None:
                        end = f.get("line_end", f["line_start"])
                        loc += f" (lines {f['line_start']}-{end})"
                details_lines.append(f"- **{f.get('fix_suggestion', 'Issue')}**{loc}\n")
        details = "\n".join(details_lines)

        await post_check_run(
            token,
            state["owner"],
            state["repo"],
            state["sha"],
            conclusion,
            summary,
            details,
        )

        # 6. Update review row
        review = await db.get(Review, uuid.UUID(state["review_id"]))
        review.status = "done"
        review.overall_risk_score = risk
        review.github_comment_url = comment_url
        review.completed_at = datetime.now(timezone.utc)
        await db.commit()

        await save_trace(
            db,
            state["review_id"],
            "agent_done",
            "aggregator",
            {"risk_score": risk, "comment_url": comment_url},
        )

    return state


# ──────────────────────────────────────────────────────────────
# Graph builder
# ──────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("fetch_pr", fetch_pr_data)
    graph.add_node("code_reader", run_code_reader)
    graph.add_node("bug_detector", run_bug_detector)
    graph.add_node("test_suggester", run_test_suggester)
    graph.add_node("doc_writer", run_doc_writer)
    graph.add_node("aggregator", aggregate_and_post)

    graph.set_entry_point("fetch_pr")
    graph.add_edge("fetch_pr", "code_reader")
    graph.add_edge("code_reader", "bug_detector")
    graph.add_edge("bug_detector", "test_suggester")
    graph.add_edge("test_suggester", "doc_writer")
    graph.add_edge("doc_writer", "aggregator")
    graph.add_edge("aggregator", END)

    return graph.compile()


_graph = build_graph()


async def run_review_graph(
    review_id: str,
    installation_id: int,
    owner: str,
    repo: str,
    pr_number: int,
) -> None:
    """
    Entry point called from the webhook background task.
    Constructs the initial AgentState and runs the graph.
    """
    initial_state: AgentState = {
        "review_id": review_id,
        "installation_id": installation_id,
        "owner": owner,
        "repo": repo,
        "pr_number": pr_number,
        "sha": "",  # will be populated by fetch_pr_data
        "diff": "",  # will be populated by fetch_pr_data
        "code_reader_output": None,  # type: ignore
        "bug_detector_output": None,  # type: ignore
        "test_suggester_output": None,  # type: ignore
        "doc_writer_output": None,  # type: ignore
    }
    await _graph.ainvoke(initial_state)
