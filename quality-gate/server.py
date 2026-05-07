"""
Quality Gate Service — external validation for AI-generated code.

Runs a linter pass + fresh Claude reviewer + optional human review queue.
Returns a PASS/FAIL/HUMAN_REVIEW verdict that the Claude Code hook uses
to block or allow sub-agent completion.

Run: python server.py (defaults to http://127.0.0.1:7733)
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
except ImportError:
    print("ERROR: pip install fastapi uvicorn pydantic", file=sys.stderr)
    sys.exit(1)

from linters import run_linter, detect_language
from reviewer import run_fresh_reviewer
from queue_store import QueueStore
from project_analyzer import get_index, check_reuse, check_conventions

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
DB_PATH = os.environ.get("GATE_DB", "quality-gate.db")
HOST = os.environ.get("GATE_HOST", "127.0.0.1")
PORT = int(os.environ.get("GATE_PORT", "7733"))
# Public URL shown in review links (clients can't reach 0.0.0.0; remap to localhost)
PUBLIC_HOST = os.environ.get("GATE_PUBLIC_HOST", "127.0.0.1" if HOST == "0.0.0.0" else HOST)
LINTER_TIMEOUT_S = int(os.environ.get("GATE_LINTER_TIMEOUT", "60"))
REVIEWER_TIMEOUT_S = int(os.environ.get("GATE_REVIEWER_TIMEOUT", "120"))
# In strict mode the gate FAILS when neither the linter nor the reviewer
# actually ran (i.e. no tools available). Default false — weak validation
# surfaces a warning but allows the turn.
STRICT_MODE = os.environ.get("GATE_STRICT", "false").lower() == "true"

_store: QueueStore | None = None


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class ChangedFile(BaseModel):
    path: str
    content: str | None = None
    diff: str | None = None


class CheckRequest(BaseModel):
    session_id: str
    agent_name: str
    project_root: str
    changed_files: list[ChangedFile]
    quality_audit: str | None = None
    require_human_review: bool = False


class Finding(BaseModel):
    source: str  # linter | reviewer | human
    severity: str  # critical | major | minor | info
    file: str | None = None
    line: int | None = None
    rule: str | None = None
    message: str


class Verdict(BaseModel):
    check_id: str
    verdict: str  # PASS | FAIL | HUMAN_REVIEW_REQUIRED
    summary: str
    findings: list[Finding]
    linter_ran: bool
    reviewer_ran: bool
    project_indexed: bool = False
    project_indexed_files: int = 0
    human_review_url: str | None = None
    duration_ms: int


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store
    _store = QueueStore(DB_PATH)
    print(f"[quality-gate] Service started on http://{HOST}:{PORT}")
    print(f"[quality-gate] DB: {DB_PATH}")
    yield


app = FastAPI(title="Claude Agent Team — Quality Gate", lifespan=lifespan)


# --------------------------------------------------------------------------- #
# Core endpoint
# --------------------------------------------------------------------------- #
@app.post("/gate/check", response_model=Verdict)
async def gate_check(req: CheckRequest) -> Verdict:
    """Run linter + fresh reviewer + optional human queue, return verdict."""
    started = datetime.utcnow()
    check_id = str(uuid.uuid4())

    if not req.changed_files:
        return Verdict(
            check_id=check_id,
            verdict="PASS",
            summary="No changed files — nothing to check",
            findings=[],
            linter_ran=False,
            reviewer_ran=False,
            duration_ms=0,
        )

    # Run linter, reviewer, and project analysis in parallel — all independent
    linter_task = asyncio.create_task(_run_linter_stage(req))
    reviewer_task = asyncio.create_task(_run_reviewer_stage(req))
    project_task = asyncio.create_task(_run_project_analysis_stage(req))

    linter_findings, linter_ran = await linter_task
    reviewer_findings, reviewer_ran = await reviewer_task
    reuse_findings, convention_findings, project_indexed = await project_task

    all_findings: list[Finding] = [*linter_findings, *reviewer_findings, *reuse_findings, *convention_findings]

    # Determine verdict
    critical_count = sum(1 for f in all_findings if f.severity == "critical")
    major_count = sum(1 for f in all_findings if f.severity == "major")

    verdict = "PASS"
    summary_parts: list[str] = []

    # Weak validation check — if NOTHING actually ran, we can't claim PASS
    if not linter_ran and not reviewer_ran:
        all_findings.append(
            Finding(
                source="gate",
                severity="major" if STRICT_MODE else "info",
                rule="weak-validation",
                message=(
                    "Neither the linter nor the fresh reviewer was able to validate "
                    "this change (no linter tool available for this language AND no "
                    "reviewer API configured). The verdict is advisory only. Install "
                    "a linter for the file's language or configure OPENAI_API_KEY / "
                    "GOOGLE_AI_KEY / claude CLI to enable the fresh reviewer."
                ),
            )
        )
        if STRICT_MODE:
            verdict = "FAIL"
            summary_parts.append("weak validation (strict mode)")
            major_count += 1  # reflect in counts

    if critical_count > 0:
        verdict = "FAIL"
        summary_parts.append(f"{critical_count} critical issue(s)")
    if major_count > 0:
        if verdict != "FAIL":
            verdict = "FAIL"
        summary_parts.append(f"{major_count} major issue(s)")

    if req.require_human_review and verdict == "PASS":
        verdict = "HUMAN_REVIEW_REQUIRED"
        summary_parts.append("queued for human review")

    # Queue if human review needed
    human_review_url: str | None = None
    assert _store is not None
    if verdict == "HUMAN_REVIEW_REQUIRED":
        _store.enqueue(
            check_id=check_id,
            session_id=req.session_id,
            agent_name=req.agent_name,
            project_root=req.project_root,
            files=[f.path for f in req.changed_files],
            findings=[f.model_dump() for f in all_findings],
            audit=req.quality_audit or "",
        )
        human_review_url = f"http://{PUBLIC_HOST}:{PORT}/review/{check_id}"

    duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    summary = (
        "All checks passed"
        if verdict == "PASS"
        else ", ".join(summary_parts) or "See findings"
    )

    return Verdict(
        check_id=check_id,
        verdict=verdict,
        summary=summary,
        findings=all_findings,
        linter_ran=linter_ran,
        reviewer_ran=reviewer_ran,
        project_indexed=project_indexed > 0,
        project_indexed_files=project_indexed,
        human_review_url=human_review_url,
        duration_ms=duration_ms,
    )


async def _run_linter_stage(req: CheckRequest) -> tuple[list[Finding], bool]:
    """Detect language per file and run the matching linter.

    Returns (findings, truly_ran). `truly_ran` is True only if at least one
    file was successfully linted with the tool actually available. If the
    tool is missing or every call failed, `truly_ran` is False so callers
    can detect weak validation.
    """
    findings: list[Finding] = []
    truly_ran = False
    languages_seen: set[str] = set()
    tools_missing: set[str] = set()

    for cf in req.changed_files:
        lang = detect_language(cf.path)
        if not lang:
            continue
        languages_seen.add(lang)

        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(
                    run_linter, lang, cf.path, req.project_root, cf.content or ""
                ),
                timeout=LINTER_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            findings.append(
                Finding(
                    source="linter",
                    severity="info",
                    file=cf.path,
                    message=f"Linter timed out after {LINTER_TIMEOUT_S}s",
                )
            )
            continue
        except Exception as e:  # noqa: BLE001
            findings.append(
                Finding(
                    source="linter",
                    severity="info",
                    file=cf.path,
                    message=f"Linter error: {e}",
                )
            )
            continue

        # linters.run_linter returns [] when the tool isn't installed. We can't
        # distinguish "tool missing" from "no issues" from the empty list alone,
        # but we CAN detect it by checking whether the underlying binary exists.
        tool_available = _linter_tool_available(lang)
        if not tool_available:
            tools_missing.add(lang)
            continue
        truly_ran = True

        for item in raw:
            findings.append(
                Finding(
                    source="linter",
                    severity=item.get("severity", "minor"),
                    file=cf.path,
                    line=item.get("line"),
                    rule=item.get("rule"),
                    message=item.get("message", ""),
                )
            )

    # If we saw files of a language but the tool wasn't available, surface that
    for lang in tools_missing:
        findings.append(
            Finding(
                source="linter",
                severity="info",
                file=None,
                rule="linter-missing",
                message=(
                    f"No linter available for language '{lang}' in the gate environment. "
                    f"Install the tool on the host, run the service natively, or install "
                    f"it inside the container."
                ),
            )
        )

    return findings, truly_ran


def _linter_tool_available(lang: str) -> bool:
    """Check if the backing linter executable is available."""
    import shutil
    tool_map = {
        "js": "npx", "ts": "npx",
        "py": "ruff",  # falls back to pylint internally — check both
        "go": "go",
        "rs": "cargo",
        "cs": "dotnet",
        "rb": "rubocop",
        "php": "phpstan",
        "java": None, "kt": None, "swift": None,  # not implemented yet
    }
    tool = tool_map.get(lang)
    if not tool:
        return False
    if lang == "py":
        return shutil.which("ruff") is not None or shutil.which("pylint") is not None
    return shutil.which(tool) is not None


async def _run_reviewer_stage(req: CheckRequest) -> tuple[list[Finding], bool]:
    """Spawn a fresh Claude instance that reviews the diff independently.

    Returns (findings, truly_ran). `truly_ran` is False if the reviewer
    returned an 'unavailable' sentinel finding (no API keys / claude CLI),
    so callers can detect weak validation.
    """
    try:
        raw = await asyncio.wait_for(
            asyncio.to_thread(
                run_fresh_reviewer,
                [f.model_dump() for f in req.changed_files],
                req.quality_audit or "",
            ),
            timeout=REVIEWER_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        return (
            [
                Finding(
                    source="reviewer",
                    severity="info",
                    message=f"Fresh reviewer timed out after {REVIEWER_TIMEOUT_S}s",
                )
            ],
            False,
        )
    except Exception as e:  # noqa: BLE001
        return (
            [
                Finding(
                    source="reviewer",
                    severity="info",
                    message=f"Fresh reviewer error: {e}",
                )
            ],
            False,
        )

    # If the only finding is 'reviewer-unavailable', the reviewer didn't actually run
    if len(raw) == 1 and raw[0].get("rule") == "reviewer-unavailable":
        return (
            [
                Finding(
                    source="reviewer",
                    severity=raw[0].get("severity", "info"),
                    rule=raw[0].get("rule"),
                    message=raw[0].get("message", ""),
                )
            ],
            False,
        )

    findings = [
        Finding(
            source="reviewer",
            severity=item.get("severity", "minor"),
            file=item.get("file"),
            line=item.get("line"),
            rule=item.get("rule"),
            message=item.get("message", ""),
        )
        for item in raw
    ]
    return findings, True


# --------------------------------------------------------------------------- #
# Project analysis stage — reuse + convention checks against the existing repo
# --------------------------------------------------------------------------- #
async def _run_project_analysis_stage(
    req: CheckRequest,
) -> tuple[list[Finding], list[Finding], int]:
    """Index the project at req.project_root and check for:
      - Reuse violations: new code duplicating existing exports
      - Convention violations: new code breaking the project's style

    Returns (reuse_findings, convention_findings, indexed_files_count).
    Both lists are empty when the project root doesn't exist or can't be scanned.
    """
    if not req.project_root:
        return [], [], 0

    try:
        index = await asyncio.wait_for(
            asyncio.to_thread(get_index, req.project_root),
            timeout=20,
        )
    except (asyncio.TimeoutError, Exception):
        return [], [], 0

    new_files = [f.model_dump() for f in req.changed_files]

    reuse_raw = check_reuse(new_files, index)
    convention_raw = check_conventions(new_files, index)

    reuse_findings = [
        Finding(
            source="reuse",
            severity=item.get("severity", "minor"),
            file=item.get("file"),
            line=item.get("line"),
            rule=item.get("rule"),
            message=item.get("message", ""),
        )
        for item in reuse_raw
    ]
    convention_findings = [
        Finding(
            source="convention",
            severity=item.get("severity", "minor"),
            file=item.get("file"),
            line=item.get("line"),
            rule=item.get("rule"),
            message=item.get("message", ""),
        )
        for item in convention_raw
    ]
    return reuse_findings, convention_findings, index.indexed_files


# --------------------------------------------------------------------------- #
# Human review UI
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    assert _store is not None
    pending = _store.list_pending()
    rows = "".join(
        f"""
        <tr>
          <td><a href="/review/{p['check_id']}">{p['check_id'][:8]}</a></td>
          <td>{p['agent_name']}</td>
          <td>{len(p['files'])}</td>
          <td>{p['created_at']}</td>
        </tr>
        """
        for p in pending
    )
    return _INDEX_HTML.replace("{{rows}}", rows or "<tr><td colspan='4'>No pending reviews</td></tr>")


@app.get("/review/{check_id}", response_class=HTMLResponse)
async def review_detail(check_id: str) -> str:
    assert _store is not None
    item = _store.get(check_id)
    if not item:
        raise HTTPException(404, "Not found")
    findings_html = "".join(
        f"""<li><span class="sev sev-{f['severity']}">{f['severity']}</span>
        <strong>{f.get('file','')}{':'+str(f['line']) if f.get('line') else ''}</strong>
        — {f['message']}</li>"""
        for f in item["findings"]
    )
    files_html = "<br>".join(item["files"])
    return _REVIEW_HTML.replace("{{check_id}}", check_id) \
        .replace("{{agent}}", item["agent_name"]) \
        .replace("{{project}}", item["project_root"]) \
        .replace("{{files}}", files_html) \
        .replace("{{audit}}", item["audit"] or "(none)") \
        .replace("{{findings}}", findings_html or "<li>No findings</li>")


@app.post("/review/{check_id}/decide")
async def decide(check_id: str, request: Request) -> JSONResponse:
    assert _store is not None
    data = await request.json()
    decision = data.get("decision", "APPROVE")
    comment = data.get("comment", "")
    _store.decide(check_id, decision, comment)
    return JSONResponse({"ok": True, "decision": decision})


@app.get("/review/{check_id}/status")
async def status(check_id: str) -> JSONResponse:
    assert _store is not None
    item = _store.get(check_id)
    if not item:
        raise HTTPException(404, "Not found")
    return JSONResponse({
        "decision": item.get("decision"),
        "comment": item.get("comment"),
        "resolved_at": item.get("resolved_at"),
    })


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "quality-gate"}


# --------------------------------------------------------------------------- #
# HTML templates (minimal inline)
# --------------------------------------------------------------------------- #
_INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Quality Gate</title>
<style>
body{font:14px system-ui;padding:24px;max-width:900px;margin:0 auto;background:#fafaf9;color:#1c1917}
h1{font-size:20px;margin-bottom:4px}
.sub{color:#78716c;margin-bottom:20px}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.05)}
th,td{padding:10px 14px;text-align:left;border-bottom:1px solid #f5f5f4;font-size:13px}
th{background:#f5f5f4;font-weight:600;text-transform:uppercase;font-size:11px;color:#78716c}
a{color:#4f46e5;text-decoration:none}
a:hover{text-decoration:underline}
</style></head><body>
<h1>Quality Gate — Review Queue</h1>
<div class="sub">Items flagged for human review</div>
<table><thead><tr><th>ID</th><th>Agent</th><th>Files</th><th>Created</th></tr></thead>
<tbody>{{rows}}</tbody></table>
</body></html>
"""

_REVIEW_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Review {{check_id}}</title>
<style>
body{font:14px system-ui;padding:24px;max-width:900px;margin:0 auto;background:#fafaf9;color:#1c1917}
h1{font-size:20px;margin-bottom:4px}
.meta{background:#fff;padding:14px 18px;border-radius:8px;margin:16px 0;font-size:13px;box-shadow:0 1px 3px rgba(0,0,0,0.05)}
.meta div{margin-bottom:6px}
.meta strong{color:#57534e}
ul{list-style:none;padding:0}
ul li{background:#fff;padding:10px 14px;border-radius:6px;margin-bottom:6px;font-size:13px;border-left:3px solid #a8a29e}
.sev{display:inline-block;padding:2px 8px;border-radius:3px;font-size:10px;font-weight:700;text-transform:uppercase;margin-right:6px}
.sev-critical{background:#fef2f2;color:#ef4444}
.sev-major{background:#fffbeb;color:#f59e0b}
.sev-minor{background:#f5f5f4;color:#78716c}
.sev-info{background:#eff6ff;color:#3b82f6}
pre{background:#1e293b;color:#e2e8f0;padding:14px;border-radius:6px;font-size:12px;overflow-x:auto;white-space:pre-wrap}
.actions{margin-top:20px;display:flex;gap:10px}
button{padding:10px 20px;border:none;border-radius:6px;font-weight:600;cursor:pointer;font-size:13px}
.approve{background:#22c55e;color:#fff}
.reject{background:#ef4444;color:#fff}
.defer{background:#a8a29e;color:#fff}
textarea{width:100%;margin:8px 0;padding:8px;border:1px solid #e7e5e4;border-radius:6px;font-family:inherit;font-size:13px;min-height:60px}
#result{margin-top:14px;padding:10px;border-radius:6px;display:none}
#result.shown{display:block}
</style></head><body>
<h1>Review {{check_id}}</h1>
<div class="meta">
  <div><strong>Agent:</strong> {{agent}}</div>
  <div><strong>Project:</strong> {{project}}</div>
  <div><strong>Files:</strong><br>{{files}}</div>
</div>
<h3>Quality Audit</h3>
<pre>{{audit}}</pre>
<h3>Findings</h3>
<ul>{{findings}}</ul>
<h3>Decision</h3>
<textarea id="comment" placeholder="Comment (optional)"></textarea>
<div class="actions">
  <button class="approve" onclick="decide('APPROVE')">Approve</button>
  <button class="reject" onclick="decide('REJECT')">Reject</button>
  <button class="defer" onclick="decide('DEFER')">Defer</button>
</div>
<div id="result"></div>
<script>
async function decide(d){
  const r = await fetch('/review/{{check_id}}/decide',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({decision:d,comment:document.getElementById('comment').value})
  });
  const data = await r.json();
  const el = document.getElementById('result');
  el.textContent = 'Decision recorded: ' + d;
  el.className = 'shown';
  el.style.background = d==='APPROVE' ? '#f0fdf4' : d==='REJECT' ? '#fef2f2' : '#f5f5f4';
}
</script>
</body></html>
"""


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("ERROR: pip install uvicorn", file=sys.stderr)
        sys.exit(1)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
