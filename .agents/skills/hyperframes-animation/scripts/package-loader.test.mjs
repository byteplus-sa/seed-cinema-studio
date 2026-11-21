import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { resolveNpmSpawnCommand } from "./package-loader.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ENV = "HYPERFRAMES_SKILL_PKG_VERSION";

test("resolveNpmSpawnCommand routes Windows npm through node and npm-cli.js", () => {
  const npmCli = "C:\\Program Files\\nodejs\\node_modules\\npm\\bin\\npm-cli.js";
  const node = "C:\\Program Files\\nodejs\\node.exe";
  const resolved = resolveNpmSpawnCommand(
    ["install", "@hyperframes/producer@0.7.55", "value & calc"],
    "win32",
    { npm_execpath: npmCli, npm_node_execpath: node },
    node,
    (path) => path === npmCli,
  );

  assert.deepEqual(resolved, {
    cmd: node,
    args: [npmCli, "install", "@hyperframes/producer@0.7.55", "value & calc"],
    opts: { stdio: "inherit", windowsHide: true },
  });
  assert.equal(resolved.opts.shell, undefined);
});

test("resolveNpmSpawnCommand finds npm-cli.js beside node for direct Windows runs", () => {
  const node = "C:\\Program Files\\nodejs\\node.exe";
  const npmCli = "C:\\Program Files\\nodejs\\node_modules\\npm\\bin\\npm-cli.js";
  const resolved = resolveNpmSpawnCommand(
    ["install", "@hyperframes/producer@0.7.55"],
    "win32",
    {},
    node,
    (path) => path === npmCli,
  );

  assert.equal(resolved?.cmd, node);
  assert.deepEqual(resolved?.args, [npmCli, "install", "@hyperframes/producer@0.7.55"]);
});

test(
  "resolveNpmSpawnCommand launches the installed npm CLI on Windows",
  { skip: process.platform !== "win32" },
  () => {
    const resolved = resolveNpmSpawnCommand(["--version"]);
    assert.ok(resolved);

    const result = spawnSync(resolved.cmd, resolved.args, {
      encoding: "utf8",
      windowsHide: true,
    });

    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout.trim(), /^\d+\./);
  },
);

test("portable helpers use the Cinema pin and reject differing or floating overrides", async () => {
  const previous = process.env[ENV];
  const { hyperframesPackageSpec } = await import("./package-loader.mjs");
  try {
    delete process.env[ENV];
    assert.equal(hyperframesPackageSpec("@hyperframes/core"), "@hyperframes/core@0.8.141");
    for (const version of ["latest", "^0.8.141", "9.9.9"]) {
      process.env[ENV] = version;
      assert.throws(() => hyperframesPackageSpec("@hyperframes/core"), /0.8.141/);
    }
  } finally {
    if (previous === undefined) delete process.env[ENV];
    else process.env[ENV] = previous;
  }
});

test("installed packages must match the pin before import", async () => {
  const dir = mkdtempSync(join(tmpdir(), "hf-cinema-"));
  try {
    const pkg = join(dir, "node_modules", "@hyperframes", "core");
    mkdirSync(pkg, { recursive: true });
    writeFileSync(join(pkg, "package.json"), JSON.stringify({ name: "@hyperframes/core", version: "1.0.0", main: "index.js" }));
    writeFileSync(join(pkg, "index.js"), "throw Error('unexpected import')");
    const loader = join(HERE, "package-loader.mjs");
    const probe = join(dir, "check.mjs");
    writeFileSync(probe, `import { importPackagesOrBootstrap } from ${JSON.stringify(loader)}; await importPackagesOrBootstrap(["@hyperframes/core"]);`);
    const result = spawnSync(process.execPath, [probe], {cwd: dir, encoding: "utf8"});
    assert.equal(result.status, 1);
    assert.match(result.stderr, /expected 0.8.141/);
    assert.doesNotMatch(result.stderr, /unexpected import/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
