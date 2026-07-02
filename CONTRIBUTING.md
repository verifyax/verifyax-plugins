# Contributing

Thanks for your interest in the VerifyAX Claude plugins.

## Contribution model

This is an **Apache-2.0** project, but it's **maintained internally by Conscium**. To keep the
marketplace and the VerifyAX API contract in sync, the maintainers handle changes — so **external
pull requests are not accepted**.

**The best way to help is to [open an issue](https://github.com/verifyax/verifyax-plugins/issues):**
a bug, an outdated endpoint, a broken install, or an idea for a new plugin. We triage from there.

For **security issues**, follow [`SECURITY.md`](SECURITY.md) — report privately, not via a public issue.

## For maintainers

- **Formatting:** an [`.editorconfig`](.editorconfig) sets the baseline (UTF-8, LF, 2-space indent,
  final newline). Keep JSON and Markdown consistent with it.
- **Manifests & versions:** `node scripts/check-manifests.mjs` validates the manifests and asserts
  each marketplace entry's version matches the plugin's `plugin.json`. CI runs this on every push/PR.
- **Skill bundle:** `scripts/build-skill.sh <plugin>` builds `dist/<skill>.skill`; CI builds and
  verifies its layout. Attach the built bundle to the GitHub Release after a version bump.
- **Server pairing:** the `verifyax-mcp` plugin pins an exact `@verifyax/mcp-server` version in its
  `plugin.json`. Bump it deliberately at release and record the pairing in [`CHANGELOG.md`](CHANGELOG.md).
