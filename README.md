# Curriculum Gap MCP Server

An MCP server that lets you ask an AI assistant questions about a training catalog: what it covers, what it doesn't, and what order the modules should be taken in.

The question behind it is one every enablement team gets asked and nobody can answer well. Are our courses actually teaching people what the business needs, and are we presenting them in an order that works?

That sounds like something a spreadsheet could handle. It isn't, because a spreadsheet can't tell the difference between a skill a module trains and a skill it just mentions in passing.

```
find_gaps(["prompt writing", "output verification", "agent building"])

covered    prompt-writing        taught by prompt-120
partial    output-verification   touched by crm-210, prompt-120, prompt-220, res-130
uncovered  agent-building        not in the catalog
```

The middle row is the reason this exists. Four modules mention verifying AI output. Not one of them teaches it. A catalog that tracks topics in a single field reports that skill as thoroughly covered, and the question gets closed.

It reads a folder of markdown files, one per module, and exposes four tools. Read-only, no database, no external services, no auth.

---

## Why files instead of a database

Most enablement teams are already maintaining this information somewhere. It's a spreadsheet with course title, learning objectives, duration, and level. The data exists. It just isn't in a form anything can query.

The obvious next step is a database, and it's the wrong one. A database is an extra layer of gatekeeping. Someone has to own it, someone has to grant access, and adding a field means a change request and a ticket. The person who knows the answer, the instructional designer who just built the module, is usually the one person who can't update it.

Markdown files in version control buy two things the spreadsheet doesn't. A change to a learning objective shows up in a pull request, so it's visible and reviewable rather than silently overwritten. And there's version history for free.

What it gives up is real. A spreadsheet sorts, filters, and can be opened by anyone in the org without explanation. Markdown can't do any of that.

The other cost is that markdown accepts anything. Nothing catches a bad value at write time the way a database would, which is why the loader validates the entire folder at startup and refuses to serve a broken catalog at all. That validation isn't defensive habit. It's the bill for this choice.

---

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

Most of these fields are ordinary. `teaches` and `touches` are the reason this works.

**`teaches`** means a learner walks away knowing something more in depth than when they came in. **`touches`** means the skill is tangential or briefly mentioned, a callout rather than a focus area.

Most catalogs collapse this into a single topics field, or carry nothing but name, level, and description. Those three fields describe a course. They don't describe what a learner leaves able to do, which is why coverage questions get answered by someone reading course descriptions and guessing.

The metadata also tends to be fragile. It lives in a spreadsheet one person maintains, and when that person leaves it's lost to the ether and rebuilt from scratch by whoever inherits the problem. Keeping it in files next to the content means a tag change shows up in the same pull request as the content change, with version history, rather than sitting in a document nobody knows to update.

As for who decides: the subject matter expert makes the call, since they know the content. I check it as a learner would, at whatever level the module is written for. If my understanding doesn't match what they intended, either the tag is wrong or the module is, and both are worth knowing. Courses also drift. Something scoped as a callout grows into a section, or an objective gets cut in review and nobody updates the metadata, so the tags get revisited when content changes rather than set once at build time.

Two honest limits. Tagging depends on the SME being available, which is why it's much cheaper at build time than retroactively on someone else's course. And this binary is a rough stand-in for something our learning objectives already express more precisely: a module that gets a learner to *identify* when AI output needs checking and one that gets them to *evaluate* it against a source are doing different work, and both currently flatten to the same `teaches` entry.

---

## The four tools

| Tool | What it does |
|---|---|
| `search_modules(query, audience, limit)` | Weighted keyword search. Returns the score and which terms matched. |
| `get_module(module_id)` | Full record for one module. |
| `find_gaps(skills, include_draft)` | Classifies each skill as covered, partial, or uncovered. |
| `suggest_sequence(goal_skill, audience, include_draft)` | Ordered path to a target skill, prerequisites resolved. |

### Search is keyword matching, not embeddings

A term in the title scores 3, in the skill list 2, in the description 1.

This will miss things. A search for "how do I talk to the AI" finds nothing, where a semantic search would find Prompt Basics. That's a real cost, and at a large enough catalog it would be the deciding one.

At this size it isn't. A few hundred modules is small enough that a person can skim the whole thing, so a missed result is annoying rather than fatal. What matters more is that every result returns its score and the terms that matched, so any ranking can be accounted for. When the output is a gap report someone will push back on, being able to show exactly what was searched for and where is worth more than catching every phrasing.

At several thousand modules I'd expect that tradeoff to flip.

### Gaps come back in three categories, not two

Covered means a module has the skill as a learning objective. Partial means it is only touched on. Uncovered means it is absent.

Partial happens by accumulation, not by anyone making a bad call. Every module that has a learner generate something naturally adds a line about checking it before it goes out. That's the responsible thing to do in each case. But four modules each spending two minutes on verification produces a topic that appears throughout the catalog and is trained nowhere in it. There's no error to find and no one to point at. The gap is the result of everyone doing their job.

Which is why partial is the only one of the three that tells anyone something new. If a skill is covered or missing outright, someone usually already knows. Partial is invisible, because from the outside it looks exactly like coverage.

The consequence is a confidently wrong answer to a question that then gets closed.

Someone asks whether sellers can verify AI output before it reaches a customer. A binary audit says covered, in four modules. Nothing gets built.

A quarter later the behaviour hasn't changed, and nobody connects it back to the catalog, because the catalog said yes.

That's the real cost. "Uncovered" sends someone to go build something. A wrong "covered" stops the conversation.

### The path sorts by prerequisite first, then level, then duration

Prerequisites are hard constraints. Where several modules are available at the same point, the tie goes to the lower level before the shorter module, because knowing what came before is what makes the pathway forward make sense. Sorting by duration first would let someone reach an advanced module before the groundwork it assumes.

### An unreachable goal returns a finding, not an error

Asking for a path to a skill nothing teaches returns `resolved: false` and an explanation, rather than an empty list. An error is broad and leaves the reader guessing whether they asked the question wrong. A finding is actionable: the query was fine, the catalog has a hole.

---

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
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/curriculum-gap-mcp/server.py"]
    }
  }
}
```

Point it at a different catalog with the `CURRICULUM_DIR` environment variable.

Things to ask once it's connected:

- "What skills does our catalog not cover for sales managers?"
- "Build me a path to prompt library design and tell me how long it takes."
- "We need sellers competent at output verification by Q3. What do we have?"

### Notes from setting this up

Built against `mcp` 2.x, where `FastMCP` was renamed to `MCPServer`. Most tutorials still show the old import, `from mcp.server.fastmcp import FastMCP`, which raises a `ModuleNotFoundError` on 2.x. You'll need to either update the import or pin `mcp<2` in your requirements.

The `command` value has to point at the virtual environment's Python rather than the system one. If it points at the wrong one, the server exits immediately because `mcp` isn't installed there, and the host doesn't report anything at all.

On Windows, the Microsoft Store build of Claude Desktop sandboxes AppData, so the config file lives under `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\` rather than `%APPDATA%\Claude\`. The way to spot this is that `%APPDATA%\Claude\` won't exist at all. A running application always leaves files behind, so if that folder is empty or missing, you're looking in the wrong place.

Also on Windows, PowerShell's `Out-File -Encoding UTF8` writes a byte-order mark at the start of the file, and Claude Desktop then rejects the file as invalid JSON. Use `[System.IO.File]::WriteAllText($path, $text)` instead, which writes clean UTF-8 without one.

If the server doesn't show up in the client at all, run the exact command from your config by hand in a terminal. A working server prints nothing and sits there waiting for input. The reason this is worth doing is that a process which fails at startup inside a host fails invisibly, and running it yourself puts the error message in front of you.

---

## Scope and limits

This is a portfolio project. These are deliberate boundaries rather than things I didn't get to.

**The module data is synthetic.** Eleven modules for a fictional company. No real catalog content appears here.

**Runs locally for one person, read-only.** The server talks to the assistant over the same input and output channels a terminal uses, so there's no web address and nothing to log in to. It never writes anything back and makes no network calls.

**No controlled list of skill names.** Skill names are cleaned up before they're compared, so `Prompt Writing`, `prompt_writing`, and `prompt-writing` all resolve to the same skill. That catches formatting differences but not synonyms. `prompt-writing` and `prompt-authoring` would read as two unrelated skills, and gap analysis would report a hole that isn't there.

**Search ties break alphabetically.** Searching "prompt" returns three modules tied at score 6, sorted by id, which puts an advanced draft module above Prompt Basics. Adding level as a second sort key is the obvious fix.

**No real test suite.** `smoke_test.py` checks that each tool runs and returns something sensible. It doesn't test the edge cases.

### What production would need

1. An approved list of skill names in its own file, with the loader rejecting anything not on it. This is the highest-value change and it makes every other tool more trustworthy.
2. Authentication and per-audience filtering at the server level, so a manager-only module isn't returned to a seller's assistant.
3. A write path with review, so a gap found in conversation can open a pull request against the catalog.
4. Reloading a module file when it changes, instead of loading everything once at startup.
5. Real tests around `suggest_sequence`, especially circular prerequisites, missing prerequisites, and the case where two modules share the same prerequisite.

---

## What I learned building this

The markdown files here are a catalog metadata layer, not the courses. Real content is built in Rise 360 and published as SCORM packages into an LMS. The production version of this would read the LMS API rather than a folder, and the module record is already the common shape both would produce, so that's a swap rather than a rewrite.

The harder question was where the metadata comes from. No LMS captures `teaches` versus `touches` in any queryable form, and my first assumption was that somebody would have to sit down and generate it from scratch.

That turned out to be wrong. Our course descriptions already carry Bloom's taxonomy objectives stating what a learner should leave able to do. That's a `teaches` entry, written in prose. The information exists. Nothing can query it, which is a different problem and a much smaller one.

Bloom's is also more precise than the model I built. The verb carries the cognitive level. *Identify* and *describe* sit at the bottom, *apply* and *demonstrate* in the middle, *evaluate* and *create* at the top. A module whose objective is "identify when AI output needs verification" and one whose objective is "evaluate AI output against a source" are doing genuinely different work, and this schema flattens both into the same entry.

So the binary here is a rough version of a six-level scale the organization already uses. The sharper question isn't "do we cover output verification." It's "we cover it at *understand* and the business needs *evaluate*." That's a gap neither a binary nor a three-way audit catches, and it's the one that actually bites, because it's the case where everyone agrees the topic is covered and performance still doesn't change.

That's the next version.
