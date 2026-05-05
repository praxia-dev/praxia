# Praxia design specifications

This directory holds the formal design documents — basic design, interface specification, and detailed design — in both English and Japanese.

| Document | English | Japanese |
|---|---|---|
| Basic design (基本設計仕様書) | [basic-design.en.md](basic-design.en.md) | [basic-design.ja.md](basic-design.ja.md) |
| Interface spec (I/F 仕様書) | [interface-spec.en.md](interface-spec.en.md) | [interface-spec.ja.md](interface-spec.ja.md) |
| Detailed design (詳細設計仕様書) | [detailed-design.en.md](detailed-design.en.md) | [detailed-design.ja.md](detailed-design.ja.md) |

## When each document applies

- **Basic design** — purpose, scope, system context, layered architecture, configuration model, non-functional requirements. Read this first.
- **Interface spec** — every public surface: Python SDK, CLI, REST API (`praxia serve`), config keys, plugin protocols (connectors, memory backends, parsers, exporters, OAuth providers, skills, flows).
- **Detailed design** — module-level class diagrams, sequence diagrams, data structures, error handling, concurrency model. Read this when extending Praxia or debugging cross-module interactions.

## Status

These documents describe Praxia as of **v1.0** (2026-05). When public API changes, the corresponding section is updated in the same PR. If you find a mismatch between the spec and the code, the **code wins** — please open a PR fixing the spec.
