# ADR-003: Human-in-the-Loop

## Status
Accepted

## Context
Zero-loss transformation is difficult to guarantee from source text alone. Humans must be able to inspect semantic and visual quality.

## Decision
Use two explicit LangGraph interrupt checkpoints:
1. outline approval
2. rendered deck approval

Checkpoint identity is the graph thread ID.

## Consequences
Positive:
- explicit human control
- resumable workflow
- audit trail

Negative:
- UI must maintain run identity
- rejected runs need a bounded revision policy

## Future
Add a structured review payload:
- approve
- request content revision
- request style revision
- request both
with reviewer comments stored in typed state.
