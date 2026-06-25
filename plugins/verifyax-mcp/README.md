# verifyax-mcp

A Claude Code plugin that installs the [VerifyAX](https://verifyax.com) MCP server, giving Claude
12 conversational tools for the agent-evaluation platform — register agents, generate scenarios,
run simulations, evaluate, and read results by just describing what you want.

This plugin wraps the published [`@verifyax/mcp-server`](https://www.npmjs.com/package/@verifyax/mcp-server)
(source: [verifyax/verifyax-mcp](https://github.com/verifyax/verifyax-mcp)). It runs the server via
`npx`, so Node ≥ 20 must be installed.

## Install

```
/plugin marketplace add verifyax/claude-plugins
/plugin install verifyax-mcp@verifyax-plugins
```

When you enable the plugin, Claude Code prompts for your **VerifyAX API key** (Settings → API Keys
in the [console](https://console.verifyax.com)). It is stored securely and passed to the server as
`VERIFYAX_API_KEY`.

## Use

Just describe the task — Claude picks the tool:

- _"List the skill tags I can use for an interview scenario on VerifyAX."_
- _"Register the A2A agent at https://my-agent.example.com and run a quick interview eval."_
- _"Generate an info_exchange scenario tagged empathy, then show me the scores."_

## verifyax-mcp vs. the verifyax-api skill

- **verifyax-mcp** (this plugin) — native MCP tools; best for conversational workflows where Claude
  executes the steps directly.
- **verifyax-api** skill — teaches Claude to drive the API via scripts; best for developers writing
  code.

## License

Apache-2.0.
