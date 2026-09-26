---
name: jev-decision
description: Use the local Jev decision layer for a registered business decision or a bounded choice among observed action candidates, with confidence and risk gates.
---

# Jev decision layer

Use this skill when a task needs one typed decision from explicit facts and candidates. The decision layer does not observe a screen, calculate metrics, or execute actions.

1. For an existing decision, call `list_decisions` then `decide` through the decision-layer MCP server, or use the local CLI via `scripts/invoke.py list`, `show`, and `decide`.
2. For a new one-step choice, use MCP `choose_candidate` or pass JSON on stdin to `python scripts/invoke.py choose --input -`. Provide a concrete `goal`, a small `state` containing only relevant observed facts, and 1–100 candidates with unique `id`, readable `label`, and explicit `risk` (`read_only`, `reversible`, or `irreversible`). The service adds an `other` option.
3. Treat `gate=auto` as permission from the decision layer to consider execution, not proof that the chosen target still exists. Refresh the target and verify the result through the owning application or tool. For `gate=review`, stop before acting and explain `gate_reason`.

The MCP server and CLI read `OPENROUTER_API_KEY` from the process environment. Never place a key in a command argument, JSON input, skill file, or repository. Use `debug` only when the raw answer distribution is needed.

The launcher at `scripts/invoke.py` resolves the repository from this skill's real path, including when the skill folder is installed through a directory link.
