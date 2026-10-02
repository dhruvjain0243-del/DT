import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

test("scanner client exposes device scan and key lifecycle calls", async () => {
  const api = await readFile(new URL("../src/api.ts", import.meta.url), "utf8");
  const main = await readFile(new URL("../src/main.ts", import.meta.url), "utf8");
  assert.match(api, /scannerScan/);
  assert.match(api, /revokeScanner/);
  assert.match(api, /regenerateScanner/);
  assert.match(main, /scanner-console-form/);
  assert.match(main, /Save this one-time scanner key securely/);
});
