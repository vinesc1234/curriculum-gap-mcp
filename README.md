# Curriculum Gap MCP Server

An MCP server that answers a question every learning team asks and no tool answers well: **does our training catalog actually teach the skills the business says it needs?**

It reads a folder of markdown files, one per training module, and exposes four tools to an AI assistant. Read-only, no external services, no auth.

```
find_gaps(["prompt writing", "output verification", "agent building"])

covered    prompt-writing        taught by prompt-120
partial    output-verification   touched by 4 modules, taught by none
uncovered  agent-building        not in the catalog
```

That middle row is the reason this exists. Four modules mention output verification. None of them teach it. A spreadsheet audit reports that skill as covered.

---

## Why this instead of a database

The catalog is markdown with YAML frontmatter, stored in git.

Instructional designers already write in markdown, the files diff cleanly in a pull request, and a curriculum lead can change a learning objective without asking anyone for database access. The cost is no referential integrity at write time, which is why the loader validates the whole folder at startup and refuses to serve a broken catalog at all.

## The data model

```yaml
---
id: prompt-220
title: Prompts for Discovery Calls
audience: [seller]
level: practitioner
duration_minutes: 40
teaches: [prompt-iteration, discovery-preparation]
touches: [prospect-research, output-verification]
prerequisites: [prompt-120]
format: workshop
status: published
---
Iterating a prompt across several turns to prepare for a discovery call.
```

**`teaches` versus `touches` is the central design decision.** `teaches` means the module has this as a learning objective and assesses it. `touches` means the skill appears but the learner is not expected to leave competent.

Most catalog metadata collapses these into one `topics` field. That single choice is what makes coverage reports lie, because a skill mentioned in passing looks identical to a skill actually trained. Splitting them costs one extra field per module and turns gap analysis from a keyword match into a real answer.

## The four tools

| Tool | What it does |
|---|---|
| `search_modules(query, audience, limit)` | Weighted keyword search. Returns the score and which terms matched. |
| `get_module(module_id)` | Full record for one module. |
| `find_gaps(skills, include_draft)` | Classifies each skill as covered, partial, or uncovered. |
| `suggest_sequence(goal_skill, audience, include_draft)` | Ordered path to a target skill, prerequisites resolved. |

### Decisions worth defending

**Search is keyword, not embeddings.** A catalog is 50 to 300 modules. At that size a transparent score beats a better one, because when a result looks wrong the person can see exactly why it ranked. Every result returns `score` and `matched_terms`. If this grew past a few thousand modules the tradeoff would flip.

**Skill names are normalized to slugs.** `Prompt Writing`, `prompt_writing`, and `prompt-writing` are one skill. Without this, gap analysis reports false gaps caused by typing, which is the fastest way to make the tool untrustworthy. A controlled vocabulary file would be stricter and is the obvious next step.

**Gaps are three-way, not binary.** Covered, partial, uncovered. See above.

**Sequencing is a topological sort with tie-breaks.** Prerequisites are hard constraints, resolved with Kahn's algorithm. Where several modules are ready at once, the tie-break is level first, then duration ascending, then id, so a learner meets a short foundation module before a long advanced one. Prerequisite cycles are detected and reported with the module ids involved rather than hanging or silently dropping a module.

**An unreachable goal is a finding, not an error.** `suggest_sequence("agent-building")` returns `resolved: false` with a reason saying the catalog does not teach it. Returning an empty list would let the assistant report "no path found" as if the query were wrong. The query is fine. The catalog has a hole.

**Draft modules are excluded by default.** `include_draft` exists because "what would our coverage look like if we shipped what is in flight" is a real planning question, but the honest default is what learners can take today.

**The catalog loads once, not per call.** Reloading per call would pick up edits live, but one malformed file would then break every tool at once. Loading at startup fails loudly, which is what you want when the catalog is the product.

**Errors are short and actionable.** Tools return `{"error": "..."}` with a next step, not a traceback. A missing module id suggests near matches. The model has to act on the error string, so a Python stack trace is a dead end for it.

## Running it

```bash
pip install -r requirements.txt
python smoke_test.py          # checks the catalog logic with no client attached
```

Then add it to a client. For Claude Desktop, in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "curriculum-gap": {
      "command": "python",
      "args": ["/absolute/path/to/curriculum-gap-mcp/server.py"]
    }
  }
}
```

Point it at your own catalog with the `CURRICULUM_DIR` environment variable.

Things to ask once it is connected:

- "What skills does our catalog not cover for sales managers?"
- "Build me a path to prompt library design and tell me how long it takes."
- "We need sellers competent at output verification by Q3. What do we have?"

## Scope and limits

This is a portfolio project, and these are deliberate boundaries rather than things I did not get to.

- **The module data is synthetic.** Eleven modules for a fictional company. No real catalog content appears here.
- **stdio transport only, single user, read-only.** No auth, no writes, no network calls.
- **No controlled skill vocabulary.** Slug normalization catches formatting drift but not synonyms. `prompt-writing` and `prompt-authoring` would read as two skills.
- **Search will not scale past a few thousand modules.** See above.
- **No test suite.** `smoke_test.py` is a smoke test, not coverage.

### What production would need

1. A skills taxonomy as its own file, with the loader rejecting any skill not in it. This is the single highest-value change and it makes every other tool more trustworthy.
2. Authentication and per-audience filtering at the server level, so a manager-only module is not returned to a seller's assistant.
3. A write path with review, so a gap found in conversation can open a pull request against the catalog.
4. Caching with invalidation on file change, replacing load-once.
5. Real tests around `suggest_sequence`, especially cycles, missing prerequisites, and diamond dependencies.

## Note on the SDK

Built against `mcp` 2.x, where `FastMCP` was renamed to `MCPServer`. Most tutorials still show `from mcp.server.fastmcp import FastMCP`, which raises a `ModuleNotFoundError` on 2.x. If you are following an older guide, either update the import or pin `mcp<2`.
