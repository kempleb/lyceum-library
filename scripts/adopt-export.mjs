#!/usr/bin/env node

import { copyFileSync, existsSync, readFileSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";
import { loadYaml, REPO_ROOT } from "./lib/load-yaml.mjs";

function fail(message) {
  console.error(`adopt-export: ${message}`);
  process.exit(1);
}

function parseArgs(argv) {
  let source = null;
  const workIds = [];
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--source") {
      source = argv[index + 1] ?? null;
      index += 1;
    } else if (arg.startsWith("--source=")) {
      source = arg.slice("--source=".length);
    } else if (arg.startsWith("--")) {
      fail(`unknown option ${arg}`);
    } else {
      workIds.push(arg);
    }
  }
  if (!source) fail("usage: adopt-export.mjs --source <tree> <work> [<work> ...]");
  if (workIds.length === 0) fail("at least one work id is required");
  if (new Set(workIds).size !== workIds.length) fail("work ids must not be repeated");
  const sourceRoot = path.resolve(source);
  if (!existsSync(sourceRoot) || !statSync(sourceRoot).isDirectory()) {
    fail(`source tree is not a directory: ${sourceRoot}`);
  }
  return { sourceRoot, workIds };
}

function exportRelativePath(manifest, manifestPath) {
  const work = manifest?.work;
  if (!work || typeof work !== "object") fail(`${manifestPath}: missing work block`);
  const hasTlg = typeof work.tlg_author === "string" && typeof work.tlg_work === "string";
  const hasPhi = typeof work.phi_author === "string" && typeof work.phi_work === "string";
  if (hasTlg === hasPhi) {
    fail(`${manifestPath}: work must declare exactly one tlg or phi author/work pair`);
  }
  return hasTlg
    ? path.join("Diogenes-Resources", "xml", "tlg", `tlg${work.tlg_author}${work.tlg_work}.xml`)
    : path.join("Diogenes-Resources", "xml", "phi", `phi${work.phi_author}${work.phi_work}.xml`);
}

function sha256(file) {
  return createHash("sha256").update(readFileSync(file)).digest("hex");
}

const { sourceRoot, workIds } = parseArgs(process.argv.slice(2));
const yaml = await loadYaml();
const operations = workIds.map((workId) => {
  const manifestPath = path.join(REPO_ROOT, "manifests", `${workId}.yaml`);
  if (!existsSync(manifestPath)) fail(`manifest is missing for ${workId}: ${manifestPath}`);
  let manifest;
  try {
    manifest = yaml.load(readFileSync(manifestPath, "utf8"));
  } catch (error) {
    fail(`${manifestPath}: ${error instanceof Error ? error.message : String(error)}`);
  }
  if (manifest?.work?.id !== workId) {
    fail(`${manifestPath}: work.id ${JSON.stringify(manifest?.work?.id)} does not match ${workId}`);
  }
  const relative = exportRelativePath(manifest, manifestPath);
  return {
    workId,
    source: path.join(sourceRoot, relative),
    destination: path.join(REPO_ROOT, "build", "export", relative),
  };
});

const missing = operations.flatMap(({ workId, source, destination }) => [
  ...(!existsSync(source) || !statSync(source).isFile() ? [`${workId}: source file missing: ${source}`] : []),
  ...(!existsSync(destination) || !statSync(destination).isFile()
    ? [`${workId}: destination file missing: ${destination}`]
    : []),
]);
if (missing.length > 0) fail(`refusing to copy because required files are missing:\n${missing.join("\n")}`);

const reports = operations.map((operation) => ({
  ...operation,
  oldHash: sha256(operation.destination),
  newHash: sha256(operation.source),
}));
const overwritten = [];
try {
  for (const operation of reports) {
    copyFileSync(operation.source, operation.destination);
    overwritten.push(operation.destination);
  }
} catch (error) {
  console.error(`adopt-export: copy failed: ${error instanceof Error ? error.message : String(error)}`);
  console.error("adopt-export: destinations already overwritten:");
  console.error(overwritten.length > 0 ? overwritten.map((destination) => `  ${destination}`).join("\n") : "  (none)");
  process.exit(1);
}
for (const { workId, oldHash, newHash } of reports) {
  console.log(`${workId}: sha256 ${oldHash} -> ${newHash}`);
}
