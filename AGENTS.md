# AGENTS.md

Edit, add, or delete files freely. Goal: every file stays readable on its
own, so future edits never require loading the whole codebase.

## Boundaries

- Keep logic that has no UI/framework dependency (parsing, building
  commands, pure calculations) free of UI imports and app state.
- A module should expose a small, stable interface and talk to others
  only through that interface — not by reaching into their internals.
- Only one module (the orchestrator/entry layer) should know about and
  wire together multiple other modules. Everything else stays local.

## Code

- One file, one job. One function, one job. Split if you can't describe
  it in a sentence.
- Keep each file's public interface small and stable; let internals
  change freely behind it.
- Avoid new shared/global state. Pass values as arguments instead.
- Prefer a new file over growing an existing one past one responsibility.

## License

Add the following header while creating a new source file:

```python
# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only
```
## Docs

After any change, update `ARCHITECTURE.md` so it still matches the code —
edit the relevant section in place, no changelog.

### What `ARCHITECTURE.md` is for

It outlines the overall program flow, which parts do what, and how the application is structured, modularized, and separated.

### What `ARCHITECTURE.md` is NOT for

It is not for documenting the detailed workings of everything. Readers should refer to the source files for that. It should only serve as a map of what exists where, what things do, and where to look.

### `ARCHITECTURE.md` conventions

Do not use tables.