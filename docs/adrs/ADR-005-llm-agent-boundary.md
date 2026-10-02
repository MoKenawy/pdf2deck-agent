# ADR-005: Bounded Agentic Reasoning

## Status
Accepted

## Context
The workflow is mostly deterministic. Unbounded agent loops would make costs, correctness, and debugging harder.

## Decision
Use a normal LangGraph state machine for the end-to-end pipeline. Use `create_agent()` or a bounded sub-agent only inside stages that genuinely need tool-driven reasoning.

The current MVP uses structured-output LLM invocation rather than a free-form agent because the outline task has a fixed contract.

## Consequences
- deterministic transitions
- easier evaluation
- lower operational risk
- agent patterns remain available for future research/asset selection stages
