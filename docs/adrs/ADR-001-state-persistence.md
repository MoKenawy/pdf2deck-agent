# ADR-001: State Persistence

## Status
Accepted

## Context
The workflow contains HITL checkpoints and potentially expensive LLM stages. State must survive UI reconnects and worker restarts.

## Decision
Use LangGraph checkpointing keyed by an opaque run/thread ID.

- MVP: `InMemorySaver`
- Production: PostgreSQL-backed LangGraph persistence

Store artifact binaries outside graph state.

## Consequences
Positive:
- resumable HITL
- deterministic restart boundary
- inspectable execution state

Negative:
- persistence infrastructure becomes mandatory in production
- schema migrations must be managed

## Alternatives
1. Stateless orchestration + database manually managed by application
2. Redis-only transient state
3. Filesystem checkpoints

Rejected because they duplicate graph orchestration semantics or provide weaker durability.
