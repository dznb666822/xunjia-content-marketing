"""
CampaignCrew — orchestrates agents + tasks via CrewAI.

    crew = CampaignCrew(request)
    brief = crew.run()
"""

from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime
from typing import Optional

from crewai import Crew, Process
from rich.console import Console
from rich.panel import Panel

from src.agents import (
    create_art_director_agent,
    create_copywriter_agent,
    create_manager_agent,
    create_research_agent,
)
from src.config import settings
from src.models.campaign_models import (
    CampaignBrief,
    CampaignRequest,
    CopyPackage,
    MarketResearch,
    RunID,
    VisualDirection,
)
from src.runtime.run_store import RunStore
from src.tasks.campaign_tasks import CampaignTaskFactory

console = Console()

RATE_LIMIT_ERROR_MARKERS = (
    "rate limit",
    "rate_limit_exceeded",
    "429",
    "too many requests",
)


class CampaignCrew:
    """High-level facade around a CrewAI crew."""

    def __init__(
        self,
        request: CampaignRequest,
        store: Optional[RunStore] = None,
        parent_run_id: Optional[RunID] = None,
        task_callback=None,
        run_id: Optional[RunID] = None,
        output_language: str = "",
    ) -> None:
        self.request = request
        self.store = store or RunStore()  # Default to output_dir/runs.db
        self.run_id = run_id or RunID.generate()  # Immutable run ID for entire execution
        self.parent_run_id = parent_run_id  # Links rerun children to parent (D-08)
        self._factory = CampaignTaskFactory(request, output_language=output_language)

        # Build agents
        console.print("  [dim]Creating Research Agent...[/dim]")
        self.researcher = create_research_agent()

        console.print("  [dim]Creating Copywriter Agent...[/dim]")
        self.copywriter = create_copywriter_agent()

        console.print("  [dim]Creating Art Director Agent...[/dim]")
        self.art_director = create_art_director_agent()

        console.print("  [dim]Creating Manager Agent...[/dim]")
        self.manager = create_manager_agent()

        # Build tasks (order matters)
        self.research_task = self._factory.research_task(self.researcher)
        self.copy_task = self._factory.copywriting_task(
            self.copywriter, self.research_task
        )
        self.art_task = self._factory.art_direction_task(
            self.art_director, self.research_task, self.copy_task
        )
        self.manager_task = self._factory.manager_task(
            self.manager, self.research_task, self.copy_task, self.art_task
        )

        # Assemble the crew (task_callback enables external progress hooks)
        crew_kwargs = dict(
            agents=[
                self.researcher,
                self.copywriter,
                self.art_director,
                self.manager,
            ],
            tasks=[
                self.research_task,
                self.copy_task,
                self.art_task,
                self.manager_task,
            ],
            process=Process.sequential,
            verbose=True,
        )
        if task_callback is not None:
            crew_kwargs["task_callback"] = task_callback
        self.crew = Crew(**crew_kwargs)

    def run(self) -> CampaignBrief:
        """Execute the full workflow and return a structured brief."""
        console.print(
            "\n[bold cyan]═══ AGENT WORKFLOW STARTING ═══[/bold cyan]\n"
        )

        # Create run record in SQLite at start (D-03: source of truth)
        try:
            self.store.create_run(
                run_id=self.run_id,
                request=self.request,
                parent_run_id=self.parent_run_id,
            )
            console.print(f"[dim]Run ID: {self.run_id}[/dim]")
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to create run record: {e}[/yellow]")

        # Kick off CrewAI execution with retry on provider TPM rate limits.
        retry_attempt = 0
        while True:
            try:
                result = self.crew.kickoff()
                break
            except Exception as exc:
                # Update status on non-retryable errors
                if not self._is_rate_limit_error(exc):
                    try:
                        self.store.update_run_status(
                            run_id=self.run_id,
                            status="failed",
                            end_time=datetime.utcnow(),
                            terminal_failure_reason=str(exc)[:500],
                        )
                    except Exception:
                        pass  # Best effort
                    raise

                if retry_attempt >= settings.groq_rate_limit_retries:
                    try:
                        self.store.update_run_status(
                            run_id=self.run_id,
                            status="failed",
                            end_time=datetime.utcnow(),
                            terminal_failure_reason="Rate limit retries exhausted",
                        )
                    except Exception:
                        pass
                    raise

                wait_seconds = self._compute_retry_delay(exc, retry_attempt)
                
                # Record retry attempt in SQLite (D-06)
                try:
                    self.store.update_run_status(
                        run_id=self.run_id,
                        status="running",
                        retry_count=retry_attempt + 1,
                    )
                except Exception:
                    pass  # Best effort
                
                console.print(
                    f"[yellow]Rate limit hit. Retrying in {wait_seconds:.2f}s "
                    f"({retry_attempt + 1}/{settings.groq_rate_limit_retries})... "
                    f"(Run: {self.run_id})[/yellow]"
                )
                time.sleep(wait_seconds)
                retry_attempt += 1

        # Get the raw output string
        raw_output = str(result)

        console.print(
            "\n[bold cyan]═══ AGENT WORKFLOW COMPLETE ═══[/bold cyan]\n"
        )

        # Build structured brief
        brief = self._build_brief(raw_output)

        # Save to disk (also registers artifacts)
        self._save_outputs(brief, raw_output)

        # Update success status in SQLite (D-03)
        try:
            self.store.update_run_status(
                run_id=self.run_id,
                status="success",
                end_time=datetime.utcnow(),
                retry_count=retry_attempt,
            )
        except Exception:
            pass  # Best effort

        return brief

    @staticmethod
    def _is_rate_limit_error(exc: Exception) -> bool:
        """Detect provider throttling errors from common status/message patterns."""
        message = str(exc).lower()
        return any(marker in message for marker in RATE_LIMIT_ERROR_MARKERS)

    @staticmethod
    def _extract_retry_after_seconds(message: str) -> float | None:
        """Parse Groq's suggested wait time from error text when available."""
        match = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)s", message, re.IGNORECASE)
        if not match:
            return None
        return float(match.group(1))

    @staticmethod
    def _exponential_backoff(attempt: int) -> float:
        """Compute fallback retry wait with a bounded exponential schedule."""
        delay = settings.groq_retry_base_seconds * (2 ** attempt)
        return min(delay, settings.groq_retry_max_seconds)

    def _compute_retry_delay(self, exc: Exception, attempt: int) -> float:
        """Use provider hint when present, else fallback to exponential backoff."""
        provider_wait = self._extract_retry_after_seconds(str(exc))
        if provider_wait is not None:
            return min(provider_wait, settings.groq_retry_max_seconds)
        return self._exponential_backoff(attempt)

    def _build_brief(self, raw_output: str) -> CampaignBrief:
        """Wrap raw crew output into a typed CampaignBrief."""
        return CampaignBrief(
            client_name=self.request.product_name,
            campaign_name=f"{self.request.product_name} Campaign",
            objective=self.request.campaign_goals,
            target_audience=self.request.target_audience,
            budget=None,
            timeline=None,
            constraints=None,
            request=self.request,
            research=MarketResearch(
                market_summary="See full Markdown brief for detailed research."
            ),
            copy_package=CopyPackage(
                campaign_tagline="See full Markdown brief for tagline.",
                elevator_pitch="See full Markdown brief for pitch.",
            ),
            visuals=VisualDirection(
                brand_visual_identity="See full Markdown brief for visuals."
            ),
            executive_summary=raw_output[:3000],
            final_recommendations=raw_output,
        )

    def _save_outputs(self, brief: CampaignBrief, raw_output: str) -> None:
        """Save the campaign brief as Markdown and JSON."""
        # Use run_id in filename for traceability
        slug = self.request.product_name.lower().replace(" ", "_")[:30]
        base = settings.output_dir / f"{slug}_{self.run_id}"

        # Save Markdown
        md_path = base.with_suffix(".md")
        md_content = self._format_markdown(brief, raw_output)
        md_path.write_text(md_content, encoding="utf-8")
        console.print(f"\n[green]✓ Saved Markdown:[/green] {md_path}")

        # Save JSON
        json_path = base.with_suffix(".json")
        json_path.write_text(
            brief.model_dump_json(indent=2), encoding="utf-8"
        )
        console.print(f"[green]✓ Saved JSON:[/green]     {json_path}")

        # Register artifacts with RunStore (D-04: Link artifacts to run)
        try:
            md_hash = hashlib.sha256(md_content.encode()).hexdigest()
            json_hash = hashlib.sha256(json_path.read_bytes()).hexdigest()
            self.store.record_artifact(
                self.run_id,
                str(md_path.relative_to(settings.output_dir)),
                md_hash
            )
            self.store.record_artifact(
                self.run_id,
                str(json_path.relative_to(settings.output_dir)),
                json_hash
            )
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to record artifacts: {e}[/yellow]")

    def _format_markdown(
        self, brief: CampaignBrief, raw_output: str
    ) -> str:
        """Create a well-formatted Markdown document."""
        channels = ", ".join(c.value for c in self.request.channels)
        return f"""# {brief.campaign_name}

**Generated:** {brief.created_at.strftime("%Y-%m-%d %H:%M:%S")}

---

## Campaign Configuration

| Field | Value |
|-------|-------|
| **Product** | {self.request.product_name} |
| **Description** | {self.request.product_description} |
| **Target Audience** | {self.request.target_audience} |
| **Goals** | {self.request.campaign_goals} |
| **Budget** | {self.request.budget_range or "Not specified"} |
| **Channels** | {channels} |
| **Brand Voice** | {self.request.brand_voice.value} |

---

## Full Campaign Brief

{raw_output}

---

*Generated by Multi-Agent Campaign Creator*
"""
