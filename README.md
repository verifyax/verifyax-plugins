# VerifyAX Plugins

A [Claude Code](https://code.claude.com/) plugin marketplace for [VerifyAX](https://verifyax.com) —
the agent evaluation and verification platform from [Conscium](https://conscium.com).

## What is VerifyAX?

VerifyAX is a platform for **testing and evaluating AI agents**. You register an agent (an A2A or
REST endpoint), generate **scenarios** that exercise specific skills, run your agent through them as
**simulations**, and get back scored **evaluations** plus full transcripts — so you can benchmark,
regression-test, and verify agent behaviour instead of eyeballing it.

These plugins bring that whole loop into Claude Code. Instead of clicking through the
[console](https://console.verifyax.com) or hand-writing API calls, you describe what you want
("register this agent and run an empathy eval") and Claude drives VerifyAX for you.

## Who this is for

- **You already have (or are evaluating) a VerifyAX account** and want to drive it from Claude Code
  rather than the web UI.
- **You're building or testing an AI agent** and want repeatable, scored evals wired into your dev
  workflow.

If you've never heard of VerifyAX, start at [verifyax.com](https://verifyax.com) to see what the
platform does first — these plugins are a client for it, not a standalone tool. You'll need an
account and an API key (below) before they do anything useful.

## Plugins

| Plugin         | Description                                                                                                                                                                                  |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `verifyax-api` | Drive the VerifyAX REST API programmatically (a skill) — register agents, generate scenarios, trigger simulations, fetch evaluations. **Best for writing code.**                             |
| `verifyax-mcp` | The same actions as native MCP tools Claude calls directly — register agents, generate scenarios, evaluate, inspect results. **Best for conversational, no-code use.** Installs [`@verifyax/mcp-server`](https://www.npmjs.com/package/@verifyax/mcp-server). |

Not sure which? Pick **`verifyax-mcp`** for conversational workflows (Claude calls the tools for
you); **`verifyax-api`** when you want Claude to write scripts against the API.

## Before you start

1. **Create a VerifyAX account** (or sign in) at the [VerifyAX console](https://console.verifyax.com).
2. **Get an API key** — **Settings → API Keys** in the console. Keys look like `sk-ver-api-...` and
   the full secret is shown **only once** at creation, so copy it then.
3. **Make sure your workspace has credits.** Generating scenarios and running simulations consume
   credits; operations fail with a payment error if the balance is empty.

## Install

Add the marketplace, then install whichever plugin you want:

```
/plugin marketplace add verifyax/verifyax-plugins
/plugin install verifyax-api@verifyax-plugins    # the skill
/plugin install verifyax-mcp@verifyax-plugins    # the MCP server
```

How you provide the API key depends on the plugin:

- **`verifyax-mcp`** prompts for the key when you enable the plugin and stores it securely.
- **`verifyax-api`** reads it from the `VERIFYAX_API_KEY` environment variable:

  ```bash
  export VERIFYAX_API_KEY=sk-ver-api-...
  ```

  The skill reads the key from this variable; it will never ask you to paste it into a chat.

## Quickstart: zero to your first evaluation

Once a plugin is installed and your key is set, just describe the goal in plain language — Claude
chains the steps (register → generate scenario → simulate → evaluate → fetch results) for you. A
first run, end to end:

> _"Using VerifyAX: register my A2A agent at `https://my-agent.example.com`, generate one
> `info_exchange` scenario tagged `empathy`, run my agent against it, and show me the evaluation
> scores when it's done."_

Claude will register the agent, create the scenario (async — it polls until ready), trigger the
simulation, wait for it to complete, and return the scores. From there you can iterate:

- _"Register this A2A agent on VerifyAX and run a quick interview-style eval against it."_
- _"List my failed simulations from the last week and show the error_details for each."_
- _"Generate a batch of 5 info_exchange scenarios with the empathy and active_listening tags."_

> 💡 Runs cost credits — ask Claude to _"estimate the credits before running"_ and it'll preview the
> cost first.

## Key concepts

A quick glossary so the examples above make sense:

| Term | What it is |
| ---- | ---------- |
| **Agent** | The AI endpoint you're testing — an **A2A** or **REST** service you register with VerifyAX. |
| **Scenario** | A test environment your agent is run through. Two types: **`info_exchange`** (multi-agent, the default) and **`interview`** (1-to-1). |
| **Skill tag** | A label (e.g. `empathy`, `active_listening`) that targets what a scenario measures. |
| **Simulation run** | One execution of an agent against a scenario. Produces a transcript. |
| **Evaluation** | The scoring of a completed run against the scenario's ground truth. |
| **Job** | An async handle for long-running work (scenario creation, simulation, evaluation): `PENDING → PROCESSING → COMPLETED / FAILED / CANCELLED`. |
| **Credits** | Workspace spend consumed by generation, simulation, and evaluation. |

**The pipeline:** Register agent → Create scenario → Trigger simulation → Evaluate → Fetch results.

## Learn more

- **Platform & sign-up:** [verifyax.com](https://verifyax.com) · [console.verifyax.com](https://console.verifyax.com)
- **Company:** [Conscium](https://conscium.com)
- **Full API reference:** bundled with the `verifyax-api` plugin (its `SKILL.md` documents every
  endpoint, status code, and the end-to-end workflow).

## Update

After we publish changes, refresh with:

```
/plugin marketplace update verifyax-plugins
```

## Also available as a Claude.ai skill

If you use [Claude.ai](https://claude.ai) (not Claude Code), grab the `.skill` bundle from the
Releases page and upload it via **Settings → Capabilities → Skills**. Same SKILL.md, different
wrapper.

### Building the `.skill` bundle (maintainers)

The bundle attached to each release is built from the plugin's skill directory with:

```bash
scripts/build-skill.sh            # → dist/verifyax-api.skill
scripts/build-skill.sh <plugin> <skill>   # for any other plugin/skill
```

A `.skill` file is just a zip whose top level is a single `<skill>/` folder containing `SKILL.md`
(and any resource files). After a version bump, rebuild and attach the new `dist/<skill>.skill` to
the GitHub Release. Build output lives in `dist/` (gitignored).

## Versioning

Each plugin pins an explicit `version` in its `plugin.json` and is versioned independently. Users
only receive updates when we bump the version, so we bump on every release. Current versions:
**`verifyax-api` 0.2.0**, **`verifyax-mcp` 0.1.0**. See [`CHANGELOG.md`](CHANGELOG.md) for release
notes.

## License

Apache-2.0. See [`LICENSE`](LICENSE).

## Contributing

Found a bug, an outdated endpoint, or want to add a new plugin (workbench helpers, scenario
authoring, etc.)? Open an issue or a PR.
