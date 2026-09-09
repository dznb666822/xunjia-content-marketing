# Multi-Agent Campaign Creator

[![Tests](https://github.com/satyamshivam13/Multi_Agent_Campaign_Creator/actions/workflows/tests.yml/badge.svg)](https://github.com/satyamshivam13/Multi_Agent_Campaign_Creator/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/badge/coverage-74%25-yellowgreen)](tests/)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**AI-powered marketing campaign generation using CrewAI and Groq**

Create complete, research-backed marketing campaigns in minutes. Four specialized AI agents work together sequentially to produce market research, compelling copy, visual direction, and an executive brief—all from a single product description.

---

## 🎯 Features

- **🔍 Research Agent** — Analyzes market trends, competitive landscape, and audience personas
- **✍️ Copywriter Agent** — Generates campaign taglines, channel-specific copy, email subjects, and hashtags
- **🎨 Art Director Agent** — Creates visual direction, mood descriptions, and image generation prompts
- **📋 Manager Agent** — Synthesizes all outputs into a cohesive executive brief with KPIs and implementation timeline
- **📦 Multi-Format Output** — Saves campaigns as Markdown briefs and structured JSON
- **⚡ Free LLM Provider** — Uses Groq's fast API with generous free-tier limits

---

## 📋 Requirements

- **Python 3.11+**
- **Groq API Key** (free tier: [console.groq.com](https://console.groq.com))
- **Serper API Key** (optional, for live trend research)

---

## 🚀 Quick Start

### 1. Clone & Setup

```powershell
# Create virtual environment
py -3.11 -m venv .venv

# Activate
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -e ".[dev]"
```

### 2. Configure Environment

```powershell
# Copy template
cp .env.example .env
```

Edit `.env` and add your API keys:

```ini
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_TEMPERATURE=0.7
GROQ_MAX_TOKENS=1400

# Optional: auto-retry on Groq TPM rate limits
GROQ_RATE_LIMIT_RETRIES=3
GROQ_RETRY_BASE_SECONDS=8
GROQ_RETRY_MAX_SECONDS=45

# Optional: for live market research
SERPER_API_KEY=your_serper_api_key_here
```

### 3. Run Demo

```powershell
# Demo with pre-configured product
python -m src.main --demo

# Interactive mode (enter your own product)
python -m src.main
```

Outputs saved to: `src/output/{product_name}_{timestamp}.{md,json}`

**Want to see the result before running it?** A complete campaign brief from a real run (AeroFlow Pro smart air purifier) is committed at [`examples/sample_campaign.md`](examples/sample_campaign.md) with the structured JSON at [`examples/sample_campaign.json`](examples/sample_campaign.json).

---

## 📁 Project Structure

```
multi_agent_campaign_creator/
├── src/
│   ├── agents/
│   │   ├── base_agent.py              # BaseAgent class + get_llm() factory
│   │   ├── research_agent.py           # Market research specialist
│   │   ├── copywriter_agent.py         # Copy & messaging specialist
│   │   ├── art_director_agent.py       # Visual direction specialist
│   │   └── manager_agent.py            # Campaign strategy & rollout
│   │
│   ├── tools/
│   │   ├── trend_research_tool.py      # Market trends (live or simulated)
│   │   ├── competitor_analysis_tool.py # Competitive landscape
│   │   ├── copy_evaluation_tool.py     # Copy quality scoring
│   │   └── image_prompt_tool.py        # DALL-E & Stable Diffusion prompts
│   │
│   ├── models/
│   │   └── campaign_models.py          # Pydantic models (CampaignRequest, CopyPackage, etc.)
│   │
│   ├── tasks/
│   │   └── campaign_tasks.py           # Task factory for CrewAI integration
│   │
│   ├── workflow/
│   │   └── crew_workflow.py            # CampaignCrew orchestrator
│   │
│   ├── config.py                       # Settings & environment loading
│   ├── main.py                         # CLI entry point
│   └── __init__.py
│
├── tests/
│   ├── test_agents.py                  # Agent initialization & execution
│   ├── test_tools.py                   # Tool output validation
│   ├── test_workflow.py                # Workflow & task wiring
│   ├── conftest.py                     # Pytest fixtures
│   └── __init__.py
│
├── output/                             # Generated campaign outputs
├── .env.example                        # Environment template
├── pyproject.toml                      # Project metadata & dependencies
├── README.md                           # This file
└── .gitignore                          # Git ignore patterns
```

---

## 🏗️ Architecture

### Sequential Agent Pipeline

```
User Input (CampaignRequest)
    ↓
[Research Agent] → Market Research Output
    ↓
[Copywriter Agent] (uses Research context) → Copy Package
    ↓
[Art Director Agent] (uses Research + Copy context) → Visual Direction
    ↓
[Manager Agent] (uses all prior outputs) → Final Campaign Brief
    ↓
Save to: markdown + JSON
```

Each agent:
- Receives context from prior agents via CrewAI's task dependencies
- Has access to specialized tools
- Uses Groq's fast LLM (llama-3.3-70b-versatile by default)

### Data Flow

- **Input**: `CampaignRequest` — product name, audience, goals, channels, brand voice
- **Output**: `CampaignBrief` — Full campaign with research, copy, visuals, strategy, and KPIs

### LangGraph Orchestration (alternative runner)

The same four agents can be driven by a [LangGraph](https://langchain-ai.github.io/langgraph/)
state machine instead of CrewAI's internal sequencer. This separates control
flow from execution the way production agentic systems do:

- **LangGraph** owns the *control flow* — which agent runs next, how state is
  threaded between stages, and where the pipeline halts on failure.
- **CrewAI** owns the *execution* — each graph node runs one CrewAI `Agent`
  inside a single-task `Crew`.

```text
[Research] → [Copywriter] → [Art Director] → [Manager] → [END]
     │             │               │
   (error)      (error)         (error)  ──────────────→ [END]
```

Each stage records its output (or an error) into a shared `CampaignState`. A
conditional edge (`should_continue`) advances to the next agent on success or
routes straight to `END` if any stage failed, so a provider outage halts the
run cleanly instead of cascading.

Run it with the `--langgraph` flag:

```bash
python -m src.main --demo --langgraph
```

Implementation: [`src/workflow/langgraph_workflow.py`](src/workflow/langgraph_workflow.py).
The default CrewAI-sequenced runner remains the standard path.

---

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ Yes | Your Groq API key from console.groq.com |
| `GROQ_MODEL` | ⚠️ Optional | LLM model name (default: `llama-3.3-70b-versatile`) |
| `GROQ_TEMPERATURE` | ⚠️ Optional | LLM temperature: 0-1 (default: 0.7, higher = more creative) |
| `GROQ_MAX_TOKENS` | ⚠️ Optional | Token cap per LLM call (default: `1400`) |
| `GROQ_RATE_LIMIT_RETRIES` | ⚠️ Optional | Retry count for Groq `429` / `rate_limit_exceeded` errors (default: `3`) |
| `GROQ_RETRY_BASE_SECONDS` | ⚠️ Optional | Base seconds for exponential fallback backoff (default: `8`) |
| `GROQ_RETRY_MAX_SECONDS` | ⚠️ Optional | Maximum wait per retry attempt (default: `45`) |
| `SERPER_API_KEY` | ❌ No | For live Google Trends; tools use deterministic simulation if not set |
| `OUTPUT_DIR` | ❌ No | Directory for campaign outputs (default: `src/output`) |

---

## 📖 Usage Examples

### Demo Mode (Recommended First Run)

```powershell
python -m src.main --demo
```

Preset product: **AeroFlow Pro** (AI-powered air purifier)

Output:
- Research on market trends (indoor air quality, smart home adoption, wellness)
- Competitor analysis (Dyson, Levoit, Molekule)
- Channel-specific copy (social media, email, display ads, influencer)
- Visual direction with image prompts
- 30-day implementation timeline

### Interactive Mode

```powershell
python -m src.main
```

You'll be prompted for:
1. **Product name** → "Smart Water Bottle"
2. **Description** → "Tracks hydration with app integration"
3. **Target audience** → "Fitness enthusiasts, health-conscious millennials"
4. **Campaign goals** → "10k units in Q1, 3% engagement rate"
5. **Channels** → social_media, email, influencer, content_marketing
6. **Brand voice** → professional, casual, playful, luxury, etc.
7. **Additional context** → Competitors, launch timeline, budget constraints

---

## 🧪 Testing

Run the test suite (25 tests, ~2-3 seconds):

```powershell
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_agents.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

**Test Coverage:**
- ✅ Agent initialization and basic execution
- ✅ Tool output validation (trends, competitor analysis, copy scoring)
- ✅ Task factory and CrewAI wiring
- ✅ Workflow integration

---

## ⚠️ Troubleshooting

### Rate Limit (429 Error)

Groq free tier: **12,000 tokens per minute (TPM)**

**Solution:**
- Wait and retry (the app now auto-retries up to `GROQ_RATE_LIMIT_RETRIES` times)
- Upgrade to [Groq Dev Tier](https://console.groq.com/settings/billing) for higher limits
- Use a different model (try `gemma2-9b-it` for faster/smaller outputs)
- Lower `GROQ_MAX_TOKENS` (e.g., `900`) to reduce TPM pressure

### Missing API Key

```
Error: GROQ_API_KEY not found in environment
```

**Solution:**
```bash
echo "GROQ_API_KEY=your_key_here" >> .env
```

### Import Errors

```
ModuleNotFoundError: No module named 'crewai'
```

**Solution:**
```powershell
pip install -e ".[dev]"
pip install --upgrade crewai langchain-groq litellm
```

### Tools Return Stubbed Output

If tools return deterministic placeholders instead of live data, set `SERPER_API_KEY` in `.env`:

```ini
SERPER_API_KEY=your_serper_api_key
```

Get free API key: [serper.dev](https://serper.dev)

---

## 📚 Model Details

### Agents

| Agent | Role | Temperature | Tools |
|-------|------|-------------|-------|
| **Research** | Senior Market Research Analyst | 0.3 (analytical) | TrendResearchTool, CompetitorAnalysisTool |
| **Copywriter** | Senior Creative Copywriter | 0.7 (creative) | CopyEvaluationTool |
| **Art Director** | Senior Art Director | 0.6 (balanced) | ImagePromptGeneratorTool |
| **Manager** | Campaign Strategy Lead | 0.4 (strategic) | None |

### Models (Pydantic)

- `CampaignRequest` — User input (product, audience, goals, channels, tone)
- `CampaignBrief` — Final output (research, copy, visuals, strategy)
- `MarketResearch` — Trends, competitors, personas, opportunities
- `CopyPackage` — Tagline, elevator pitch, channel copy, email subjects, hashtags
- `VisualDirection` — Brand identity, key visuals, image prompts

---

## 🤝 Contributing

Contributions welcome! Areas for enhancement:

- [ ] Retry logic with exponential backoff for rate limits
- [ ] Support for additional LLM providers (Claude, OpenAI, Mistral)
- [ ] Web UI for campaign builder
- [ ] A/B testing framework for copy variants
- [ ] Integration with Canva/Figma for asset generation
- [ ] Database storage for campaign history

---

## 📄 License

MIT

---

## 🔗 Resources

- [CrewAI Documentation](https://docs.crewai.com)
- [Groq API Docs](https://console.groq.com/docs)
- [LiteLLM Reference](https://docs.litellm.ai)
- [Pydantic Validation](https://docs.pydantic.dev)

---

**Questions or Issues?** Check the [Troubleshooting](#troubleshooting) section or review test files for usage examples.
