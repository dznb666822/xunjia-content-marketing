"""Web UI server for the Multi-Agent Campaign Creator.

Exposes the existing CrewAI/LangGraph campaign workflow over HTTP:

    POST /api/campaigns            -> start a campaign run (background thread)
    GET  /api/runs/{id}/events     -> SSE stream of stage progress events
    GET  /api/runs/{id}/result     -> final markdown brief + structured json
    GET  /api/runs                 -> run history (from SQLite RunStore)
    GET  /api/runs/{id}/files/{n}  -> download saved .md / .json artifacts

Run:
    python web/server.py           # http://127.0.0.1:8686
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Bootstrap: make `src.*` importable regardless of launch cwd ──────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import os  # noqa: E402

os.chdir(ROOT)  # .env and output_dir resolve against project root

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import (  # noqa: E402
    FileResponse,
    JSONResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from src.config import settings  # noqa: E402
from src.models.campaign_models import (  # noqa: E402
    CampaignChannel,
    CampaignRequest,
    CopyTone,
    RunID,
)
from src.runtime.run_store import RunStore  # noqa: E402
from src.workflow.crew_workflow import CampaignCrew  # noqa: E402
from src.workflow.langgraph_workflow import (  # noqa: E402
    _initial_state,
    build_campaign_graph,
)

APP = FastAPI(title="Campaign War Room")

# 主控制台(5000)内嵌调用本服务(8686)需要跨域许可
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STAGES = ["research", "copywriter", "art_director", "manager"]
STAGE_TITLES = {
    "research": "市场调研",
    "copywriter": "创意文案",
    "art_director": "视觉方向",
    "manager": "策略总监",
}
# The final (manager) stage writes the deliverable brief in Chinese.
OUTPUT_LANGUAGE = "简体中文"


class WebCampaignRequest(BaseModel):
    """Payload accepted by POST /api/campaigns."""

    product_name: str = ""
    product_description: str = ""
    target_audience: str = ""
    campaign_goals: str = ""
    budget_range: Optional[str] = None
    channels: list[str] = ["social_media"]
    brand_voice: str = "professional"
    additional_context: Optional[str] = None
    engine: str = "langgraph"  # "langgraph" | "crewai"


class RunManager:
    """In-memory run registry: background threads + SSE event logs."""

    def __init__(self) -> None:
        self._events: dict[str, list[dict]] = {}
        self._lock = threading.Lock()

    # ── event log helpers ────────────────────────────────────────────
    def emit(self, run_id: str, event: dict) -> None:
        event = {"ts": time.time(), **event}
        with self._lock:
            self._events.setdefault(run_id, []).append(event)

    def events_since(self, run_id: str, after: int) -> list[dict]:
        with self._lock:
            return list(self._events.get(run_id, [])[after:])

    def total_events(self, run_id: str) -> int:
        with self._lock:
            return len(self._events.get(run_id, []))

    # ── run lifecycle ────────────────────────────────────────────────
    def start(self, req: WebCampaignRequest) -> str:
        campaign = _to_campaign_request(req)
        run_id = RunID.generate().value
        with self._lock:
            self._events[run_id] = []
        self.emit(
            run_id,
            {
                "type": "run_created",
                "run_id": run_id,
                "engine": req.engine,
                "product": campaign.product_name,
                "stages": STAGES,
            },
        )
        worker = threading.Thread(
            target=self._execute,
            args=(run_id, campaign, req.engine),
            daemon=True,
        )
        worker.start()
        return run_id

    def _execute(self, run_id: str, campaign: CampaignRequest, engine: str) -> None:
        store = RunStore()
        started = time.time()
        try:
            if engine == "langgraph":
                self._run_langgraph(run_id, campaign, store, started)
            else:
                self._run_crewai(run_id, campaign, store, started)
        except Exception as exc:  # noqa: BLE001 - report any failure to the UI
            traceback.print_exc()
            self._finalize_failure(run_id, store, str(exc)[:500])
            self.emit(
                run_id,
                {
                    "type": "run_failed",
                    "message": str(exc)[:600],
                    "elapsed": round(time.time() - started, 1),
                },
            )

    # ── engine: LangGraph (per-stage streaming) ─────────────────────
    def _run_langgraph(
        self, run_id: str, campaign: CampaignRequest, store: RunStore, started: float
    ) -> None:
        try:
            store.create_run(RunID(value=run_id), campaign)
        except Exception:
            pass

        graph = build_campaign_graph()
        state = _initial_state(campaign, output_language=OUTPUT_LANGUAGE)
        merged: dict = dict(state)

        self.emit(run_id, {"type": "stage_start", "stage": STAGES[0]})

        for chunk in graph.stream(state, stream_mode="updates"):
            for node, delta in chunk.items():
                if isinstance(delta, dict):
                    merged.update(delta)
                idx = STAGES.index(node) if node in STAGES else -1
                output_key = {
                    "research": "research_output",
                    "copywriter": "copy_output",
                    "art_director": "visual_output",
                    "manager": "final_brief",
                }.get(node)
                self.emit(
                    run_id,
                    {
                        "type": "stage_done",
                        "stage": node,
                        "title": STAGE_TITLES.get(node, node),
                        "elapsed": round(time.time() - started, 1),
                        "chars": len(delta.get(output_key, "") or "")
                        if isinstance(delta, dict)
                        else 0,
                    },
                )
                if 0 <= idx < len(STAGES) - 1:
                    self.emit(
                        run_id, {"type": "stage_start", "stage": STAGES[idx + 1]}
                    )

        errors = merged.get("errors") or []
        if errors:
            try:
                store.update_run_status(
                    RunID(value=run_id),
                    status="failed",
                    end_time=datetime.utcnow(),
                    terminal_failure_reason="; ".join(errors)[:500],
                )
            except Exception:
                pass
            self.emit(
                run_id,
                {
                    "type": "run_failed",
                    "message": "; ".join(errors),
                    "elapsed": round(time.time() - started, 1),
                },
            )
            return

        try:
            store.update_run_status(
                RunID(value=run_id), status="success", end_time=datetime.utcnow()
            )
        except Exception:
            pass

        final_brief = merged.get("final_brief", "")
        artifacts = _persist_langgraph_outputs(run_id, campaign, merged, store)
        self.emit(
            run_id,
            {
                "type": "run_complete",
                "run_id": run_id,
                "elapsed": round(time.time() - started, 1),
                "artifacts": artifacts,
            },
        )

    # ── engine: CrewAI (task callbacks) ──────────────────────────────
    def _run_crewai(
        self, run_id: str, campaign: CampaignRequest, store: RunStore, started: float
    ) -> None:
        task_index = {"n": 0}

        def on_task_done(_output) -> None:
            idx = task_index["n"]
            if idx < len(STAGES):
                stage = STAGES[idx]
                self.emit(
                    run_id,
                    {
                        "type": "stage_done",
                        "stage": stage,
                        "title": STAGE_TITLES[stage],
                        "elapsed": round(time.time() - started, 1),
                        "chars": len(str(_output)) if _output else 0,
                    },
                )
                task_index["n"] += 1
                if idx + 1 < len(STAGES):
                    self.emit(
                        run_id, {"type": "stage_start", "stage": STAGES[idx + 1]}
                    )

        crew = CampaignCrew(
            campaign, store=store, task_callback=on_task_done,
            run_id=RunID(value=run_id), output_language=OUTPUT_LANGUAGE,
        )
        self.emit(run_id, {"type": "stage_start", "stage": STAGES[0]})
        brief = crew.run()
        self.emit(
            run_id,
            {
                "type": "run_complete",
                "run_id": run_id,
                "elapsed": round(time.time() - started, 1),
                "artifacts": _artifacts_from_store(store, run_id),
            },
        )

    def _finalize_failure(self, run_id: str, store: RunStore, reason: str) -> None:
        try:
            store.update_run_status(
                RunID(value=run_id),
                status="failed",
                end_time=datetime.utcnow(),
                terminal_failure_reason=reason,
            )
        except Exception:
            pass


def _to_campaign_request(req: WebCampaignRequest) -> CampaignRequest:
    channels = []
    for ch in req.channels:
        try:
            channels.append(CampaignChannel(ch))
        except ValueError:
            continue
    if not channels:
        channels = [CampaignChannel.SOCIAL_MEDIA]
    try:
        tone = CopyTone(req.brand_voice)
    except ValueError:
        tone = CopyTone.PROFESSIONAL
    return CampaignRequest(
        product_name=req.product_name.strip() or "未命名产品",
        product_description=req.product_description.strip(),
        target_audience=req.target_audience.strip(),
        campaign_goals=req.campaign_goals.strip(),
        budget_range=(req.budget_range or "").strip() or None,
        channels=channels,
        brand_voice=tone,
        additional_context=(req.additional_context or "").strip() or None,
    )


def _persist_langgraph_outputs(
    run_id: str, campaign: CampaignRequest, merged: dict, store: RunStore
) -> list[dict]:
    """Save md + json artifacts for a LangGraph run and link them in the store."""
    import hashlib

    slug = campaign.product_name.lower().replace(" ", "_")[:30]
    base = settings.output_dir / f"{slug}_{run_id}"

    channels = ", ".join(c.value for c in campaign.channels)
    md_content = f"""# {campaign.product_name} 营销方案

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} · Engine: LangGraph

---

## Campaign Configuration

| Field | Value |
|-------|-------|
| **Product** | {campaign.product_name} |
| **Description** | {campaign.product_description} |
| **Target Audience** | {campaign.target_audience} |
| **Goals** | {campaign.campaign_goals} |
| **Budget** | {campaign.budget_range or "Not specified"} |
| **Channels** | {channels} |
| **Brand Voice** | {campaign.brand_voice.value} |

---

## Research（市场调研）

{merged.get("research_output", "")}

---

## Copy（创意文案）

{merged.get("copy_output", "")}

---

## Visual Direction（视觉方向）

{merged.get("visual_output", "")}

---

## Final Brief（策略总监简报）

{merged.get("final_brief", "")}

---

*Generated by Multi-Agent Campaign Creator (LangGraph pipeline)*
"""
    md_path = base.with_suffix(".md")
    md_path.write_text(md_content, encoding="utf-8")

    json_payload = {
        "run_id": run_id,
        "request": campaign.model_dump(),
        "research_output": merged.get("research_output", ""),
        "copy_output": merged.get("copy_output", ""),
        "visual_output": merged.get("visual_output", ""),
        "final_brief": merged.get("final_brief", ""),
    }
    json_path = base.with_suffix(".json")
    json_path.write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for path in (md_path, json_path):
        try:
            store.record_artifact(
                RunID(value=run_id),
                str(path.relative_to(settings.output_dir)),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        except Exception:
            pass

    return [
        {"path": str(md_path.relative_to(settings.output_dir)),
         "url": f"/api/runs/{run_id}/files/{md_path.name}"},
        {"path": str(json_path.relative_to(settings.output_dir)),
         "url": f"/api/runs/{run_id}/files/{json_path.name}"},
    ]


def _artifacts_from_store(store: RunStore, run_id: str) -> list[dict]:
    try:
        meta = store.get_run(RunID(value=run_id))
    except Exception:
        return []
    if not meta:
        return []
    return [
        {
            "path": a["path"],
            "url": f"/api/runs/{run_id}/files/{Path(a['path']).name}",
        }
        for a in meta.artifacts
    ]


# ── FastAPI routes ───────────────────────────────────────────────────────
MANAGER = RunManager()


@APP.post("/api/campaigns")
def create_campaign(req: WebCampaignRequest):
    if req.engine not in ("langgraph", "crewai"):
        raise HTTPException(400, "engine must be 'langgraph' or 'crewai'")
    run_id = MANAGER.start(req)
    return JSONResponse({"run_id": run_id, "engine": req.engine})


@APP.get("/api/runs/{run_id}/events")
async def campaign_events(run_id: str, request: Request, after: int = 0):
    """SSE stream; replays buffered events from index `after`, ends on terminal event."""

    async def gen():
        cursor = after
        while True:
            if await request.is_disconnected():
                return
            batch = MANAGER.events_since(run_id, cursor)
            for ev in batch:
                cursor += 1
                data = json.dumps(ev, ensure_ascii=False)
                yield f"id: {cursor}\nevent: {ev.get('type', 'message')}\ndata: {data}\n\n"
                if ev.get("type") in ("run_complete", "run_failed"):
                    return
            await asyncio.sleep(0.4)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@APP.get("/api/runs/{run_id}/result")
def campaign_result(run_id: str):
    store = RunStore()
    try:
        meta = store.get_run(RunID(value=run_id))
    except Exception:
        raise HTTPException(400, "invalid run_id")
    if not meta:
        raise HTTPException(404, "run not found")

    markdown = None
    structured = None
    for artifact in meta.artifacts:
        p = settings.output_dir / artifact["path"]
        if not p.exists():
            continue
        if p.suffix == ".md":
            markdown = p.read_text(encoding="utf-8")
        elif p.suffix == ".json":
            try:
                structured = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                structured = None

    return JSONResponse(
        {
            "run_id": run_id,
            "status": meta.status,
            "product": (meta.config_snapshot or {}).get("product_name", ""),
            "engine": (meta.config_snapshot or {}).get("engine"),
            "start_time": meta.start_time.isoformat(),
            "end_time": meta.end_time.isoformat() if meta.end_time else None,
            "failure_reason": meta.terminal_failure_reason,
            "markdown": markdown,
            "json": structured,
            "artifacts": [
                {
                    "path": a["path"],
                    "url": f"/api/runs/{run_id}/files/{Path(a['path']).name}",
                }
                for a in meta.artifacts
            ],
        }
    )


@APP.get("/api/runs")
def list_runs(limit: int = 30):
    """Run history read directly from the RunStore SQLite database."""
    db = settings.output_dir / "runs.db"
    if not db.exists():
        return JSONResponse({"runs": []})
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT run_id, status, start_time, end_time, terminal_failure_reason, "
            "config_snapshot FROM runs ORDER BY start_time DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    runs = []
    for row in rows:
        try:
            snapshot = json.loads(row["config_snapshot"])
        except Exception:
            snapshot = {}
        runs.append(
            {
                "run_id": row["run_id"],
                "status": row["status"],
                "product": snapshot.get("product_name", ""),
                "engine": snapshot.get("engine"),
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "failure_reason": row["terminal_failure_reason"],
            }
        )
    return JSONResponse({"runs": runs})


@APP.get("/api/runs/{run_id}/files/{name}")
def download_artifact(run_id: str, name: str):
    """Serve a saved artifact; the name must belong to the run's artifact list."""
    store = RunStore()
    try:
        meta = store.get_run(RunID(value=run_id))
    except Exception:
        raise HTTPException(400, "invalid run_id")
    if not meta:
        raise HTTPException(404, "run not found")
    for artifact in meta.artifacts:
        if Path(artifact["path"]).name == name:
            p = settings.output_dir / artifact["path"]
            if p.exists():
                return FileResponse(p, filename=name)
    raise HTTPException(404, "artifact not found")


APP.mount(
    "/static",
    StaticFiles(directory=str(ROOT / "web" / "static")),
    name="static",
)


@APP.get("/")
def index():
    return FileResponse(str(ROOT / "web" / "static" / "index.html"))


if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("  Campaign War Room -> http://127.0.0.1:8686")
    print("=" * 60)
    uvicorn.run(APP, host="127.0.0.1", port=8686, log_level="warning")
