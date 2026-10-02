# ADR-002: Slide Rendering Engine

## Status
Accepted for MVP

## Context
The system must generate editable `.pptx` files while preserving user-provided presentation styles.

## Decision
Use `python-pptx` behind a renderer interface.

The renderer receives validated semantic slide models and performs deterministic layout operations.

## Consequences
Positive:
- native Python
- editable PPTX
- easy unit testing
- template/presentation can act as the starting design surface

Negative:
- limited support for some advanced PowerPoint features
- visual fidelity requires additional rendering/QA
- notes/layout APIs vary by version/template

## Alternatives
- PptxGenJS: strong alternative if JS ecosystem is preferred
- Office automation: higher fidelity but harder deployment and Linux scaling
- HTML/SVG-to-slides: more visual control, less native editability

The interface allows replacement later.
