# LiteLLM Integration Architecture

This document describes the LiteLLM gateway integration in TradegentSwarm and its relationship with the UCX documentation framework.

---

## Overview

TradegentSwarm uses **LiteLLM** as a unified gateway for multi-provider LLM access. This enables:

- **Provider abstraction**: Single interface to OpenAI, Anthropic, Azure, Ollama, Gemini, OpenRouter
- **Role-based routing**: Different model classes for different tasks
- **Deterministic fallback**: Ordered fallback chains when providers fail
- **Cost optimization**: Route by task complexity and budget constraints
- **Observability**: Unified telemetry across all providers

---

## Architecture

```
┌─ TRADEGENT PLATFORM ─────────────────────────────────────────────┐
│                                                                   │
│  ┌─ ADK Runtime ─────────────────────────────────────────────┐   │
│  │                                                            │   │
│  │  CoordinatorAgent                                          │   │
│  │    ├─ SubagentInvoker                                      │   │
│  │    │    ├─ DraftAnalysisAgent (reasoning_standard)         │   │
│  │    │    ├─ CriticAgent (critic_model)                      │   │
│  │    │    ├─ RepairAgent (reasoning_standard)                │   │
│  │    │    ├─ RiskGateAgent (reasoning_premium)               │   │
│  │    │    └─ SummaryAgent (summarizer_fast)                  │   │
│  │    │                                                       │   │
│  │    └─ LiteLLMGatewayClient ─────────────────────────────── │   │
│  │              │                                              │   │
│  └──────────────│──────────────────────────────────────────────┘   │
│                 │                                                   │
│  ┌─ LiteLLM Gateway ──────────────────────────────────────────┐   │
│  │              │                                              │   │
│  │   Role Routing Table                                        │   │
│  │   ├─ reasoning_premium  → openai/gpt-4o                    │   │
│  │   ├─ reasoning_standard → openrouter/gpt-4o-mini, openai   │   │
│  │   ├─ extraction_fast    → openai/gpt-4o-mini               │   │
│  │   ├─ critic_model       → openai/gpt-4o-mini               │   │
│  │   └─ summarizer_fast    → openai/gpt-4o-mini               │   │
│  │                                                             │   │
│  │   Fallback Chain: LITELLM_FALLBACK_MODELS                  │   │
│  │                                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                 │                                                   │
└─────────────────│───────────────────────────────────────────────────┘
                  │
    ┌─────────────┴─────────────┬─────────────┬─────────────┐
    │                           │             │             │
    ▼                           ▼             ▼             ▼
┌─────────┐               ┌──────────┐  ┌─────────┐  ┌──────────┐
│ OpenAI  │               │OpenRouter│  │  Azure  │  │  Ollama  │
│ API     │               │ API      │  │ OpenAI  │  │ (local)  │
└─────────┘               └──────────┘  └─────────┘  └──────────┘
```

---

## Role-Based Model Classes

The gateway routes requests based on task role, not individual model selection:

| Role Alias | Purpose | Default Route | Use Case |
|------------|---------|---------------|----------|
| `reasoning_premium` | High-stakes synthesis, gate decisions | `openai/gpt-4o` | RiskGateAgent, final decisions |
| `reasoning_standard` | Primary analysis, drafting | `openrouter/gpt-4o-mini` | DraftAnalysisAgent, RepairAgent |
| `extraction_fast` | Parsing, normalization | `openai/gpt-4o-mini` | ContextRetrievalAgent |
| `critic_model` | Self-review, contradiction checks | `openai/gpt-4o-mini` | CriticAgent |
| `summarizer_fast` | UI summaries, short responses | `openai/gpt-4o-mini` | SummaryAgent |

---

## Configuration

### Environment Variables

```bash
# Default model (fallback when role route not configured)
LLM_MODEL=gpt-4o-mini

# Role-based routing chains (ordered, deterministic fallback)
# Format: provider/model,provider/model
LITELLM_ROUTE_REASONING_PREMIUM=openai/gpt-4o
LITELLM_ROUTE_REASONING_STANDARD=openrouter/openai/gpt-4o-mini,openai/gpt-4o-mini
LITELLM_ROUTE_EXTRACTION_FAST=openai/gpt-4o-mini
LITELLM_ROUTE_CRITIC_MODEL=openai/gpt-4o-mini
LITELLM_ROUTE_SUMMARIZER_FAST=openai/gpt-4o-mini

# Global fallback chain appended to each role route
LITELLM_FALLBACK_MODELS=openrouter/openai/gpt-4o-mini,openai/gpt-4o-mini

# Provider API keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...
AZURE_API_KEY=...
AZURE_API_BASE=https://your-resource.openai.azure.com
GEMINI_API_KEY=...
```

### ADK Sub-Agent LLM Control

```bash
# Enable shared LiteLLM path for ADK sub-agent phases
# false: emit route metadata only (safe default)
# true: execute sub-agent calls through LiteLLM shared gateway
ADK_SUBAGENT_LLM_ENABLED=false
```

---

## Supported Providers

| Provider | Model Format | API Key Env | Notes |
|----------|-------------|-------------|-------|
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` | Primary provider |
| Anthropic | `anthropic/claude-opus-4-5-20251101` | `ANTHROPIC_API_KEY` | Claude models |
| OpenRouter | `openrouter/openai/gpt-4o-mini` | `OPENROUTER_API_KEY` | Multi-provider proxy |
| Azure OpenAI | `azure/gpt-4` | `AZURE_API_KEY` | Enterprise compliance |
| Google Gemini | `gemini/gemini-pro` | `GEMINI_API_KEY` | Google models |
| Ollama | `ollama/llama3` | - | Local inference |
| Mistral | `mistral/mistral-large` | `MISTRAL_API_KEY` | Mistral AI |

### Local Ollama Configuration

```bash
# Use Ollama for all routes (cost-free, slower)
LLM_MODEL=ollama/llama3
LITELLM_ROUTE_REASONING_PREMIUM=ollama/llama3
LITELLM_ROUTE_REASONING_STANDARD=ollama/llama3
LITELLM_ROUTE_EXTRACTION_FAST=ollama/qwen3:8b
LITELLM_ROUTE_CRITIC_MODEL=ollama/llama3
LITELLM_ROUTE_SUMMARIZER_FAST=ollama/qwen3:8b
```

---

## Python API

### LiteLLMGatewayClient

```python
from tradegent.llm_gateway import LiteLLMGatewayClient, LLMChatResult

# Load routes from environment
client = LiteLLMGatewayClient.from_env()

# JSON response (structured output)
result: LLMChatResult = await client.chat_json(
    role_alias="reasoning_standard",
    messages=[{"role": "user", "content": "Analyze MSFT"}],
    temperature=0.2,
    max_tokens=4096,
)

# Text response (free-form)
result: LLMChatResult = await client.chat_text(
    role_alias="summarizer_fast",
    messages=[{"role": "user", "content": "Summarize this analysis"}],
    temperature=0.3,
)

# Access result fields
print(result.content)        # Response text
print(result.model_alias)    # Role alias used
print(result.model)          # Actual model called
print(result.provider)       # Provider (openai, anthropic, etc.)
print(result.input_tokens)   # Input token count
print(result.output_tokens)  # Output token count
```

### Custom Routes

```python
# Define custom routes
routes = {
    "reasoning_premium": ["openai/gpt-4o", "anthropic/claude-opus-4-5-20251101"],
    "reasoning_standard": ["openai/gpt-4o-mini", "ollama/llama3"],
    "extraction_fast": ["ollama/qwen3:8b"],
    "critic_model": ["openai/gpt-4o-mini"],
    "summarizer_fast": ["ollama/qwen3:8b"],
}

client = LiteLLMGatewayClient(
    routes=routes,
    timeout=120.0,
    max_retries=2,
)
```

---

## Fallback Behavior

The gateway implements deterministic fallback:

1. Try first model in route chain
2. On failure, try next model
3. Continue until success or chain exhausted
4. Raise `RuntimeError` if all models fail

```
LITELLM_ROUTE_REASONING_STANDARD=openrouter/openai/gpt-4o-mini,openai/gpt-4o-mini
LITELLM_FALLBACK_MODELS=anthropic/claude-3-5-haiku-20241022

Execution order:
1. openrouter/openai/gpt-4o-mini  → if fails
2. openai/gpt-4o-mini             → if fails
3. anthropic/claude-3-5-haiku     → if fails
4. RuntimeError raised
```

---

## UCX Integration

The **UCX** (Unified Context Framework) documentation system also uses LiteLLM for multi-provider support. Both systems can share configuration.

### UCX Location

```
/opt/data/docs_flow_framework/UCX/
```

### UCX LiteLLM Client

```python
from ucx.ai import LiteLLMClient

# Short aliases map to Claude models
client = LiteLLMClient(model="opus")  # → anthropic/claude-opus-4-5-20251101
client = LiteLLMClient(model="sonnet") # → anthropic/claude-sonnet-4-20250514
client = LiteLLMClient(model="haiku")  # → anthropic/claude-3-5-haiku-20241022

# Or use any LiteLLM model format
client = LiteLLMClient(model="openai/gpt-4o")
client = LiteLLMClient(model="ollama/llama3", api_base="http://localhost:11434")
```

### Shared Configuration Pattern

Both Tradegent and UCX can use the same provider credentials:

```bash
# Shared provider keys (used by both systems)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENROUTER_API_KEY="sk-or-..."

# Tradegent-specific routing
export LITELLM_ROUTE_REASONING_STANDARD=openrouter/openai/gpt-4o-mini

# UCX-specific model selection
export UCX_MODEL=opus
export UCX_API_BASE=  # Optional: custom endpoint
```

### Use Cases

| System | Primary Use | Model Selection |
|--------|-------------|-----------------|
| Tradegent | Trading analysis, execution | Role-based routing |
| UCX | Document creation, review, remediation | Model aliases (opus/sonnet/haiku) |

---

## Observability

### Telemetry Fields

Every LLM call captures:

| Field | Type | Description |
|-------|------|-------------|
| `model_alias` | string | Role alias (reasoning_standard, etc.) |
| `model` | string | Actual model called |
| `provider` | string | Provider (openai, anthropic, etc.) |
| `input_tokens` | int | Prompt tokens |
| `output_tokens` | int | Completion tokens |
| `response_id` | string | Provider response ID |
| `latency_ms` | int | Request duration |

### Metrics

```
tradegent_llm_requests_total{role_alias, model, provider, status}
tradegent_llm_tokens_total{role_alias, direction}
tradegent_llm_latency_ms{role_alias, model}
tradegent_llm_cost_usd{role_alias, model}
tradegent_llm_fallback_total{role_alias, from_model, to_model}
```

---

## Cost Management

### Per-Role Budget Caps

Configure budget limits per skill or per role:

```bash
# Per-analysis budget cap (USD)
configured_skill_budget_cap_usd=0.50

# Token limits per sub-agent
budget_tokens_in_max=50000
budget_tokens_out_max=8000
```

### Cost Optimization Strategies

1. **Route by complexity**: Use premium models only for high-stakes decisions
2. **Use fallback chains**: Start with cheaper models, escalate on failure
3. **Local Ollama**: Use for development and low-stakes tasks
4. **OpenRouter**: Access to discounted model routes

---

## Related Documentation

- [ADK Multi-Provider Orchestration](adk-multi-provider-orchestration.md) - Full orchestration architecture
- [Architecture Overview](overview.md) - System architecture
- [UCX README](/opt/data/docs_flow_framework/UCX/README.md) - UCX documentation system
