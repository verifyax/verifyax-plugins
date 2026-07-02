#!/usr/bin/env node
// Validate the marketplace + plugin manifests and assert versions are consistent.
// There is no official published JSON Schema for these files yet, so this is a
// structural check: required fields are present, and each marketplace entry's
// version matches the plugin's own plugin.json (the drift the review flagged).
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = (rel) => JSON.parse(readFileSync(join(root, rel), 'utf8'));

const errors = [];
const check = (cond, msg) => {
  if (!cond) errors.push(msg);
};

const marketplace = read('.claude-plugin/marketplace.json');
check(typeof marketplace.name === 'string', 'marketplace.json: missing "name"');
check(
  Array.isArray(marketplace.plugins) && marketplace.plugins.length > 0,
  'marketplace.json: missing non-empty "plugins"'
);

for (const entry of marketplace.plugins ?? []) {
  const label = entry.name ?? '(unnamed)';
  check(typeof entry.name === 'string', 'marketplace plugin entry missing "name"');
  check(typeof entry.source === 'string', `${label}: missing "source"`);
  check(typeof entry.version === 'string', `${label}: missing "version"`);
  if (typeof entry.source !== 'string') continue;

  const manifestPath = join(entry.source, '.claude-plugin', 'plugin.json');
  let plugin;
  try {
    plugin = read(manifestPath);
  } catch {
    errors.push(`${label}: cannot read ${manifestPath}`);
    continue;
  }
  check(typeof plugin.name === 'string', `${manifestPath}: missing "name"`);
  check(typeof plugin.version === 'string', `${manifestPath}: missing "version"`);
  check(
    plugin.name === entry.name,
    `${label}: name mismatch — marketplace "${entry.name}" vs plugin.json "${plugin.name}"`
  );
  check(
    plugin.version === entry.version,
    `${label}: version mismatch — marketplace "${entry.version}" vs plugin.json "${plugin.version}"`
  );
}

if (errors.length > 0) {
  console.error('Manifest validation failed:');
  for (const e of errors) console.error(`  - ${e}`);
  process.exit(1);
}
console.error('OK: manifests are structurally valid and versions are consistent.');
