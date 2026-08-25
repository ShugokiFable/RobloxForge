---
name: roblox-docs
description: Use when needing CURRENT Roblox API facts, Luau syntax, service behavior, or Roblox documentation - DataStore, RemoteEvent, TweenService, ProcessReceipt, Streaming, task scheduler, engine limits. Searches the official creator-docs corpus locally instead of recalling it.
---

# Roblox docs (RobloxForge current-knowledge system)

Roblox ships engine changes continuously. Model memory of the Roblox API is
stale by construction, and a wrong method signature or a wrong DataStore limit
does not fail loudly -- it fails in production, on someone else's experience.

This skill reads the official `Roblox/creator-docs` corpus from a local cache,
so the answer comes from the documentation rather than from recall.

## Resolution priority

```
observed runtime  >  current official docs  >  verified community practice  >  model memory
```

Never stop at the last one. If the docs do not state it, verify it in Studio
through the Roblox Studio MCP before writing it down as fact.

## Use it

MCP (agent):

| Tool | Purpose |
|---|---|
| `rb_docs_search` | find pages by query; returns paths |
| `rb_docs_read` | read one cached page (bounded); takes a path from search |
| `rb_docs_update` | refresh the cache from upstream |

CLI (equivalent, no MCP schema cost):

```bash
rbforge docs status
rbforge docs search "TweenService:Create"
rbforge docs read <path-from-search>
rbforge docs update
```

`rbforge docs status` reports cache freshness honestly, including when the cache
is absent or stale. **A stale cache is still evidence, an absent one is not** --
if the cache is missing, say so rather than answering from memory.

## What to look up rather than recall

These change, and they are the ones that get invented:

- `DataStoreService` request budgets, throttling, and `UpdateAsync` semantics
- `ProcessReceipt` idempotency requirements and correct return values
- `RemoteEvent` / `RemoteFunction` trust boundaries and rate limits
- `TweenService` easing behavior and completion signals
- Streaming-enabled replication and instance lifetime
- `task.*` scheduling versus the deprecated `wait` / `spawn`
- Instance, string, and network limits

## Non-negotiable

- Never invent a class, property, method, enum, event, or limit.
- Quote the doc path you took a fact from, so it can be re-checked.
- A search result is not a read: open the page before asserting what it says.
- If search returns nothing, report that. Silence is not confirmation.
