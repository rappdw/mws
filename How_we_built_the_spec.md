# From Idea to Specification: How `mws` Took Shape

> A narrative account of a collaborative AI-assisted specification process.  
> Total elapsed time: approximately 2 hours.

---

## Overview

This document captures how `SPECIFICATION.md` was developed — not just what decisions were made, but how the conversation moved from a vague idea to a refined, implementation-ready specification. It's intended as a reference for how we might approach similar API integration work at Proofpoint: using AI collaboration not just to write code, but to think through architecture before a line of code is written.

---

## Phase 1: The Seed Idea (~5 minutes)

The starting point was a simple observation: the Google Workspace team had just published [`gws`](https://github.com/googleworkspace/cli), a new CLI for Gmail, Drive, Calendar, and other Workspace services. The question was whether something equivalent existed for Microsoft 365, and if not, whether it was worth building.

A quick search surfaced the answer: yes, there is an existing M365 CLI — [`pnp/cli-microsoft365`](https://github.com/pnp/cli-microsoft365), a mature Node-based tool maintained by the Microsoft community. It's comprehensive, actively developed, and uses the binary name `m365`.

This immediately sharpened the question: **why build something new rather than use what exists?**

The answer was not "because we can," but a specific set of reasons: `m365` is Node-based (adding a runtime dependency), human-first in its design (not optimized for agent use), and covers an enormous surface area (SharePoint administration, Power Platform, Viva) that isn't relevant for developer-focused M365 automation. A Python-native, agent-first alternative that followed the `gws` design philosophy had a meaningful differentiated position.

---

## Phase 2: Naming and Initial Framing (~10 minutes)

Before writing any spec, we settled on naming. The `gws` binary name follows the pattern `[vendor initials]ws` — so the natural parallel was `mws` (Microsoft Workspace). This became both the repo name and binary name.

This might seem like a small decision, but getting it right early mattered: the name would appear throughout the spec, in the `pyproject.toml`, in documentation, and in every example command. Changing it later is friction.

---

## Phase 3: Scoping the First Spec (~20 minutes)

A short exchange established the key parameters before writing anything:

- **Language:** Python, because it was the most familiar language for the project owner, and distribution via `pipx` (later updated to `uv`/`uvx`) was sufficient for personal/team use
- **Services:** Mail, Calendar, Teams, SharePoint/OneDrive — the four M365 services covering the majority of developer-relevant workflows
- **Auth:** Not yet determined — the spec would need to cover setup from scratch since no Azure AD app registration existed

With those parameters set, the first full specification was written. It was a conventional hand-coded CLI spec: explicit command definitions for each service (`mws mail list`, `mws calendar create`, etc.), per-operation flag tables, and a static implementation order.

This version was complete and workable — but it was already the wrong architecture.

---

## Phase 4: The Architectural Pivot (~20 minutes)

A deeper look at how `gws` actually works revealed the key insight: **`gws` doesn't define commands statically. It reads Google's Discovery Service at runtime and generates its entire command surface dynamically.**

This is a fundamentally different approach. Instead of writing 30-odd command handlers, you write a command engine that consumes an API schema and builds commands from it automatically. When the API adds new endpoints, the CLI picks them up without a code change.

Microsoft Graph has an equivalent: a full OpenAPI 3 specification, published at `https://aka.ms/graph/v1.0/openapi.yaml`. This meant the same architecture was available for `mws`.

The implications cascaded through the entire spec:

- The hand-coded command modules (`commands/mail.py`, `commands/calendar.py`, etc.) were replaced by a schema engine and dynamic command builder
- The implementation order shifted — schema fetch and parse had to come before any commands could be registered
- A new `mws schema <path>` introspection command became a first-class feature (the primary mechanism for agents to self-orient)
- `--dry-run` became a global flag rather than a per-command option
- The default output format flipped from `table` to `json` — because the primary consumer is an agent, not a human

This is the kind of architectural shift that is much cheaper to make in a specification than in code. The entire pivot took one conversation exchange and produced a substantially better design.

---

## Phase 5: Validating Against Reference Implementations (~15 minutes)

Two research questions arose during the architectural pivot:

**1. Was `gws` inspired by `m365`?**

No. `gws` was created by a Google Developer Relations engineer and published just weeks before this conversation. Its design philosophy — "you need to rewrite your CLI for AI agents" — is explicitly agent-first and represents a different design generation than `m365`, which is a traditional human-oriented admin tool.

**2. Should `mws` use Kiota, Microsoft's OpenAPI-to-SDK generator?**

Kiota is designed to consume the Graph OpenAPI spec at *build time* and generate a typed SDK. `mws`'s schema engine consumes the same spec at *runtime* to build a dynamic command surface. These two approaches are fundamentally incompatible — using Kiota would eliminate the self-updating command surface that makes `mws` architecturally interesting. Decision: skip Kiota, use `msal` + `httpx` directly.

**3. What are the correct OpenAPI spec URLs?**

The spec initially referenced a GitHub raw URL for the OpenAPI spec. Research confirmed Microsoft publishes canonical URLs:
- `https://aka.ms/graph/v1.0/openapi.yaml`
- `https://aka.ms/graph/beta/openapi.yaml`

These replaced the GitHub URL, and a `--api-version beta` flag was added to the global flags.

---

## Phase 6: Reference-Driven Specification (~20 minutes)

The final structural decision was how to handle the two existing implementations — `gws` and `m365` — in relation to `mws`. Rather than describing implementation details prescriptively (which would be redundant and potentially wrong), the spec was restructured to use submodules as living references.

```
research/
├── gws/    # Primary style reference
└── m365/   # Graph API field guide
```

The specification was rewritten to establish a clear division of responsibility:

- **Follow `gws`** for architecture, command surface shape, output format, skill file structure, MCP server mode, and UX defaults
- **Consult `m365`** for Graph API auth patterns, OData query syntax, permission scope inventory, and endpoint-specific edge cases

This made the spec significantly shorter — prescriptive implementation detail was replaced with precise pointers to source code. It also made it more reliable: Claude Code reading actual `gws` source is better than Claude Code following a prose description of how gws works.

Each phase of the implementation order was annotated with which submodule to read first.

---

## Phase 7: Language/Runtime Question (~10 minutes)

A final question: should `mws` follow `gws` all the way — including implementing in Rust and distributing via npm?

The analysis: probably not. The architectural and stylistic spirit of `gws` is worth following closely. The implementation language is not. Rust is a significant learning curve, and the ability to read, debug, and extend the output is as important as the output itself. Python with `uv`/`uvx` provides clean distribution without a runtime dependency, which was the actual distribution requirement. The Rust/npm pattern is worth knowing about for future projects where broader public distribution is the goal.

---

## What This Process Illustrates

A few things worth carrying into future API integration work:

**Specifications are cheaper to refactor than code.** The architectural pivot from hand-coded commands to a dynamic schema engine happened in a single exchange. If this had been discovered after implementation started, it would have been a significant rewrite.

**"Does this already exist?" is always the first question.** The existence of `m365` didn't kill the project — it sharpened it. Understanding what's already out there is what lets you define a meaningful differentiated position rather than accidentally rebuilding something.

**Reference implementations are better than prose descriptions.** The final spec is shorter and more precise because it points to `research/gws/src/` instead of describing what that code does. Claude Code reading actual source code is more reliable than Claude Code following a written paraphrase of that source code.

**Agent-first is a design choice, not a feature.** Flipping the default output format from `table` to `json`, making `--dry-run` global, adding schema introspection — none of these are individually large. Together they represent a coherent philosophy that makes the tool qualitatively different from a human-first CLI. It requires deciding upfront which audience you're optimizing for.

**Technology choices should match the person maintaining the tool.** The Rust question was answered not by what's technically superior but by what allows the person who owns the project to read, debug, and extend the output. The best implementation is the one that can actually be maintained.

---

## Artifact Summary

| Artifact | Description |
|---|---|
| `SPECIFICATION.md` | Implementation-ready spec for Claude Code |
| `research/gws` | Submodule: primary style and architecture reference |
| `research/m365` | Submodule: Graph API field guide |
| `HOW-WE-BUILT-THIS-SPEC.md` | This document |
