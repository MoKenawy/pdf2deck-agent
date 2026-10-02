# ADR-004: MCP vs Standard Tool Integration

## Status
Accepted

## Context
The product may eventually connect to external enterprise systems, but its core operations are deterministic local services.

## Decision
Use normal typed Python service interfaces for:
- PDF parsing
- chunking
- PPTX rendering
- object storage adapters

Adopt MCP only for external tools that benefit from an independently deployed, standardized tool protocol.

## Consequences
The core system remains simple and testable while retaining an integration path for enterprise tool ecosystems.

## Rejected approach
Making every function an MCP tool would add network/protocol complexity without improving the core pipeline.
