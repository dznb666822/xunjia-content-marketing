<!-- GSD:project-start source:PROJECT.md -->
## Project

**Multi-Agent Campaign Creator**

A Python CLI that generates end-to-end marketing campaigns using a sequential CrewAI workflow with four specialist agents: research, copywriting, art direction, and strategy management. It takes a structured campaign brief and produces Markdown and JSON campaign outputs for quick iteration and handoff. The primary users are marketers, founders, and builders who need fast campaign drafts with grounded structure.

**Core Value:** Generate a coherent, usable campaign brief from one product input in minutes, not days.

### Constraints

- **Tech stack**: Python + CrewAI + Groq — keep implementation aligned with existing architecture
- **Provider quota**: Groq TPM limits can interrupt runs — guardrails and retries must account for burst usage
- **Compatibility**: Preserve current CLI UX and output contracts for existing users
- **Security**: Avoid leaking raw provider/internal details in normal-mode error output
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11+ - application and tests in `src/` and `tests/` (`pyproject.toml`, `src/main.py`, `tests/test_workflow.py`)
- Markdown - user/developer docs in `README.md` and `CONTRIBUTING.md`
- YAML - CI workflow config in `.github/workflows/tests.yml`
## Runtime
- CPython 3.11+ required by project metadata (`pyproject.toml`) and CI matrix uses 3.11 and 3.12 (`.github/workflows/tests.yml`)
- pip with editable install workflow (`pip install -e ".[dev]"`) documented in `README.md` and used in `.github/workflows/tests.yml`
- Build backend: setuptools (`pyproject.toml`)
- Lockfile: missing (no `poetry.lock`, `uv.lock`, or `requirements.txt` detected)
## Frameworks
- CrewAI >=0.86.0 - multi-agent orchestration (`src/workflow/crew_workflow.py`, `src/agents/*.py`)
- LangChain Groq integration (`langchain-groq`) - declared provider dependency in `pyproject.toml`
- Pydantic >=2.10.0 - request/response data models and tool schemas (`src/models/campaign_models.py`, `src/tools/*.py`)
- pytest >=9.0 - unit/integration-style tests (`tests/`)
- pytest-asyncio >=0.24.0 - async test support declared in `pyproject.toml`
- pytest-cov >=4.0 - coverage reporting (`README.md`, `.github/workflows/tests.yml`)
- python-dotenv >=1.0.0 - `.env` loading in `src/config.py`
- rich >=13.0.0 - CLI rendering/progress panels in `src/main.py` and `src/workflow/crew_workflow.py`
- flake8 - optional CI lint gate in `.github/workflows/tests.yml`
## Key Dependencies
- `crewai` - defines `Crew`, `Process`, `Agent`, and `Task` abstractions used by the whole workflow (`src/workflow/crew_workflow.py`, `src/tasks/campaign_tasks.py`)
- `crewai.llm.LLM` - Groq model client wrapper built in `src/agents/base_agent.py`
- `pydantic` - strict schema definitions for campaign domain and tools (`src/models/campaign_models.py`, `src/tools/trend_research_tool.py`)
- `httpx` - outbound HTTPS calls to Serper search endpoint in `src/tools/trend_research_tool.py`
- `python-dotenv` - environment bootstrapping in `src/config.py`
- `Jinja2` - declared dependency in `pyproject.toml` (no direct use detected in `src/`)
## Configuration
- Environment loaded at import time via `load_dotenv()` in `src/config.py`
- Required key: `GROQ_API_KEY` validated in `Settings.__post_init__` (`src/config.py`)
- Optional Groq controls: `GROQ_MODEL`, `GROQ_TEMPERATURE`, `GROQ_MAX_TOKENS`, `GROQ_RATE_LIMIT_RETRIES`, `GROQ_RETRY_BASE_SECONDS`, `GROQ_RETRY_MAX_SECONDS` (`src/config.py`, `.env.example`)
- Optional research key: `SERPER_API_KEY`; absence triggers simulated trend output (`src/tools/trend_research_tool.py`)
- Output path control: `OUTPUT_DIR` with default `src/output` (`src/config.py`, `.env.example`)
- Packaging metadata and dependency declarations in `pyproject.toml`
- CI test workflow in `.github/workflows/tests.yml`
## Platform Requirements
- Windows/macOS/Linux shell with Python 3.11+ and pip (`README.md`)
- Network access required for live Groq and optional Serper requests (`src/agents/base_agent.py`, `src/tools/trend_research_tool.py`)
- Local `.env` file required for runtime configuration (`src/config.py`, `.env.example`)
- Deployment target: Not detected (project currently operates as a local CLI via `python -m src.main` in `src/main.py`)
- Runtime outputs persisted as local Markdown/JSON files under `src/output` (`src/workflow/crew_workflow.py`)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Use `snake_case.py` for module names (examples: `src/workflow/crew_workflow.py`, `src/tools/trend_research_tool.py`).
- Keep test files as `test_*.py` under `tests/` (examples: `tests/test_workflow.py`, `tests/test_tools.py`).
- Use `snake_case` for function and method names (examples: `get_llm` in `src/agents/base_agent.py`, `_compute_retry_delay` in `src/workflow/crew_workflow.py`).
- Use leading underscore for non-public helpers (examples: `_build_brief`, `_simulated_search`, `_run`).
- Use `snake_case` for locals and attributes (examples: `retry_attempt`, `groq_max_tokens`, `channel_limits`).
- Use uppercase constants for module-level constants (example: `RATE_LIMIT_ERROR_MARKERS` in `src/workflow/crew_workflow.py`).
- Use `PascalCase` for classes and Pydantic models (examples: `CampaignCrew`, `CampaignRequest`, `CopyEvaluationTool`).
- Use enum members in `UPPER_SNAKE_CASE` (examples: `CampaignChannel.SOCIAL_MEDIA`, `CopyTone.PROFESSIONAL` in `src/models/campaign_models.py`).
## Code Style
- No formatter configuration detected (`pyproject.toml` does not define Black/Ruff/isort settings).
- Follow existing style: type hints for most public methods and concise module/class/function docstrings.
- Keep line wrapping readable for long strings and constructor calls (patterns visible in `src/main.py` and `src/tasks/campaign_tasks.py`).
- Correct mixed indentation where introduced: tabs are present in `src/config.py` and `src/models/__init__.py`; new edits should use 4 spaces.
- CI linting is configured in `.github/workflows/tests.yml` using `flake8 src --select=E9,F63,F7,F82`.
- Lint step is non-blocking (`continue-on-error: true`), so local code changes should still be validated before commit.
## Import Organization
- No custom alias system detected; use absolute package imports rooted at `src` (example: `from src.models import CampaignRequest` in `src/tasks/campaign_tasks.py`).
## Error Handling
- Validate critical environment settings at startup and raise `EnvironmentError` for invalid/missing values (`src/config.py`).
- Guard runtime boundaries with `try/except` and user-facing error output (`run_campaign` in `src/main.py`).
- For transient provider failures, detect retryable errors, back off, and re-raise after retry budget is exhausted (`CampaignCrew.run` in `src/workflow/crew_workflow.py`).
## Logging
- Use `console.print` with semantic color/status formatting for progress and errors.
- Avoid raw `print()` in workflow/CLI code.
## Comments
- Use brief section comments for high-level phases (examples: "Build agents", "Save to disk" in `src/workflow/crew_workflow.py`).
- Keep comments focused on behavior intent, not obvious syntax.
- Keep comments focused on behavior intent, not obvious syntax.
- Python docstrings are used at module, class, and method level throughout `src/`.- Python docstrings are used at module, class, and method level throughout `src/`.
## Function Design
- Keep orchestration methods moderate and split logic into helpers (`run` delegates to `_compute_retry_delay`, `_build_brief`, `_save_outputs` in `src/workflow/crew_workflow.py`).
- Prefer explicit typed parameters with defaults for optional behavior (examples: `_run(..., channel: str = "general")` in `src/tools/copy_evaluation_tool.py`).
- Use strongly-typed Pydantic input schemas for CrewAI tool arguments (`args_schema` pattern in `src/tools/*.py`).
- Return typed domain models at workflow boundaries (`CampaignBrief` from `CampaignCrew.run`).
- Tool methods return serialized JSON strings for agent interoperability (`_run` in all tool modules under `src/tools/`).
## Module Design
- Package `__init__.py` files re-export intended public symbols via `__all__` (examples: `src/agents/__init__.py`, `src/tools/__init__.py`, `src/models/__init__.py`).
- Use package-level barrels for cross-module imports (`from src.agents import ...` and `from src.models import ...`).
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Single orchestration class (`src/workflow/crew_workflow.py`) composes all runtime collaborators.
- Layered package boundaries under `src/` (`agents`, `tools`, `tasks`, `models`, `workflow`).
- Typed domain contracts with Pydantic models in `src/models/campaign_models.py`.
## Layers
- Purpose: Collect campaign input, render progress/errors, trigger workflow execution.
- Location: `src/main.py`
- Contains: Argument parsing, interactive prompts, request summary rendering, exception-to-exit handling.
- Depends on: `src/models/campaign_models.py`, `src/workflow/crew_workflow.py`, Rich console components.
- Used by: End users invoking `python -m src.main`.
- Purpose: Build agents/tasks, execute CrewAI workflow, apply retry logic, persist outputs.
- Location: `src/workflow/crew_workflow.py`
- Contains: `CampaignCrew`, rate-limit detection/backoff logic, brief construction, markdown/json saving.
- Depends on: `src/agents/__init__.py`, `src/tasks/campaign_tasks.py`, `src/models/campaign_models.py`, `src/config.py`.
- Used by: `src/main.py` and workflow tests in `tests/test_workflow.py`.
- Purpose: Define specialist agent personas and bind tools + LLM configuration.
- Location: `src/agents/*.py`
- Contains: `create_research_agent`, `create_copywriter_agent`, `create_art_director_agent`, `create_manager_agent`, and shared `get_llm` in `src/agents/base_agent.py`.
- Depends on: `src/tools/__init__.py` and `src/config.py`.
- Used by: `CampaignCrew` in `src/workflow/crew_workflow.py`.
- Purpose: Generate CrewAI `Task` objects with explicit context dependencies.
- Location: `src/tasks/campaign_tasks.py`
- Contains: `CampaignTaskFactory` and task templates for research, copywriting, art direction, and manager synthesis.
- Depends on: `src/models/__init__.py` and CrewAI `Task`.
- Used by: `CampaignCrew` during initialization.
- Purpose: Provide deterministic or live external-analysis helpers exposed to agents.
- Location: `src/tools/*.py`
- Contains: Serper-backed trend lookup (`src/tools/trend_research_tool.py`) and deterministic analysis tools (`src/tools/competitor_analysis_tool.py`, `src/tools/copy_evaluation_tool.py`, `src/tools/image_prompt_tool.py`).
- Depends on: `src/config.py` for feature flags/API keys and Pydantic input schemas per tool.
- Used by: Agent factories in `src/agents/*.py`.
- Purpose: Define request/response schemas and enum vocabularies shared across layers.
- Location: `src/models/campaign_models.py`
- Contains: `CampaignRequest`, `CampaignBrief`, `MarketResearch`, `CopyPackage`, `VisualDirection`, enums like `CampaignChannel` and `CopyTone`.
- Depends on: Pydantic and Python stdlib types.
- Used by: CLI, task factory, workflow, tests.
## Data Flow
- Runtime state is object-local (`CampaignCrew` instance fields) and immutable global config in `src/config.py` via module singleton `settings`.
## Key Abstractions
- Purpose: Facade that hides CrewAI wiring details from CLI and tests.
- Examples: `src/workflow/crew_workflow.py`, `tests/test_workflow.py`.
- Pattern: Composition root plus orchestration service.
- Purpose: Encapsulate task descriptions and dependency chaining.
- Examples: `src/tasks/campaign_tasks.py`.
- Pattern: Factory with explicit upstream `context` linking.
- Purpose: Centralize LLM model/temperature/max token configuration.
- Examples: `src/agents/base_agent.py`, calls from each `src/agents/*_agent.py` file.
- Pattern: Shared configuration factory.
## Entry Points
- Location: `src/main.py`
- Triggers: `python -m src.main` (interactive) and `python -m src.main --demo`.
- Responsibilities: Build request, instantiate workflow, render success/failure output.
- Location: `src/workflow/crew_workflow.py`
- Triggers: `run_campaign()` in `src/main.py`.
- Responsibilities: Build and execute crew, retry on provider limits, persist outputs.
## Error Handling
- Config validation in `Settings.__post_init__` (`src/config.py`) raises `EnvironmentError` for missing/invalid values.
- Runtime retry in `CampaignCrew.run` (`src/workflow/crew_workflow.py`) catches provider throttling signatures and sleeps with bounded backoff.
## Cross-Cutting Concerns
> TODO: Document cross-cutting concerns such as observability, security patterns, and performance considerations.
<!-- GSD:architecture-end -->
<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.github/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
