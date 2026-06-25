# VerifyAX Plugins

A [Claude Code](https://code.claude.com/) plugin marketplace for [VerifyAX](https://verifyax.com) —
the agent evaluation and verification platform from [Conscium](https://conscium.com).

## Plugins

| Plugin         | Description                                                                                                                                                                                  |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `verifyax-api` | Drive the VerifyAX REST API programmatically (a skill) — register agents, generate scenarios, trigger simulations, fetch evaluations. **Best for writing code.**                             |
| `verifyax-mcp` | The same actions as native MCP tools Claude calls directly — register agents, generate scenarios, evaluate, inspect results. **Best for conversational, no-code use.** Installs [`@verifyax/mcp-server`](https://www.npmjs.com/package/@verifyax/mcp-server). |

Not sure which? Pick **`verifyax-mcp`** for conversational workflows (Claude calls the tools for
you); **`verifyax-api`** when you want Claude to write scripts against the API.

## Install

Add the marketplace, then install whichever plugin you want:

```
/plugin marketplace add verifyax/verifyax-plugins
/plugin install verifyax-api@verifyax-plugins    # the skill
/plugin install verifyax-mcp@verifyax-plugins    # the MCP server
```

You need a VerifyAX API key — get one from **Settings → API Keys** in the
[VerifyAX console](https://console.verifyax.com). How you provide it depends on the plugin:

- **`verifyax-mcp`** prompts for the key when you enable the plugin and stores it securely.
- **`verifyax-api`** reads it from the `VERIFYAX_API_KEY` environment variable:

  ```bash
  export VERIFYAX_API_KEY=sk-ver-api-...
  ```

  The skill reads the key from this variable; it will never ask you to paste it into a chat.

## Use

Once installed, just describe what you want and Claude reaches for the right tool:

- _"Register this A2A agent on VerifyAX and run a quick interview-style eval against it."_
- _"List my failed simulations from the last week and show the error_details for each."_
- _"Generate a batch of 5 info_exchange scenarios with the empathy and active_listening tags."_

## Update

After we publish changes, refresh with:

```
/plugin marketplace update verifyax-plugins
```

## Also available as a Claude.ai skill

If you use [Claude.ai](https://claude.ai) (not Claude Code), grab the `.skill` bundle from the
Releases page and upload it via **Settings → Capabilities → Skills**. Same SKILL.md, different
wrapper.

## Versioning

Each plugin pins an explicit `version` in its `plugin.json`. Users only receive updates when we
bump the version, so we bump on every release. The current version is **0.1.0**.

## License

Apache-2.0. See [`LICENSE`](LICENSE).

## Contributing

Found a bug, an outdated endpoint, or want to add a new plugin (workbench helpers, scenario
authoring, etc.)? Open an issue or a PR.
