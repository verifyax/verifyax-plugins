# VerifyAX Claude Plugins

A [Claude Code](https://code.claude.com/) plugin marketplace for [VerifyAX](https://verifyax.com) — the agent evaluation and verification platform from [Conscium](https://conscium.com).

## What's in here

| Plugin | Description |
|---|---|
| `verifyax-api` | Drive the VerifyAX REST API programmatically (a skill) — register agents, generate test scenarios, trigger simulations, fetch evaluations. Best for writing code. |
| `verifyax-mcp` | Native MCP tools for VerifyAX — the same workflow as conversational tools Claude executes directly. Best for conversational use. Wraps [`@verifyax/mcp-server`](https://www.npmjs.com/package/@verifyax/mcp-server). |

## Install

Add the marketplace, then install a plugin:

```
/plugin marketplace add verifyax/claude-plugins
/plugin install verifyax-api@verifyax-plugins    # the skill
/plugin install verifyax-mcp@verifyax-plugins    # the MCP server
```

Not sure which? `verifyax-mcp` for conversational workflows (Claude calls the tools for you);
`verifyax-api` for writing scripts against the API.

## Use

Once installed, just describe what you want and Claude will reach for the skill automatically:

- *"Register this A2A agent on VerifyAX and run a quick interview-style eval against it."*
- *"List my failed simulations from the last week and show the error_details for each."*
- *"Generate a batch of 5 info_exchange scenarios with the empathy and active_listening tags."*

You still need a VerifyAX API key. Get one from **Settings → API Keys** in the [VerifyAX console](https://console.verifyax.com) and export it before starting your session:

```bash
export VERIFYAX_API_KEY=sk-ver-api-...
```

The skill expects to read the key from this env var; it will never ask you to paste it into a chat.

## Update

After we push changes, users refresh with:

```
/plugin marketplace update verifyax-plugins
```

## Also available as a Claude.ai skill

If you use [Claude.ai](https://claude.ai) (not Claude Code), grab the `.skill` bundle from the Releases page and upload it via **Settings → Capabilities → Skills**. Same SKILL.md, different wrapper.

## Versioning

Each plugin pins an explicit `version` in its `plugin.json`. Users only receive updates when we bump the version, so we'll bump on every release. The current version is **0.1.0**.

## License

Apache-2.0. See `LICENSE`.

## Contributing

Found a bug, an outdated endpoint, or want to add a new plugin (workbench helpers, scenario authoring, etc.)? Open an issue or a PR.
