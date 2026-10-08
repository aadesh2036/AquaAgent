// TS side of `make contracts-test`: enum parity with Python + units tests.
// Run: node --test shared/tests/   (Node ≥ 22.6 strips types natively)
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { ENUMS, NODE_FEATURES_V1, EDGE_FEATURES_V1, CONTRACT_VERSION } from "../contracts/contracts.ts";

const generated = JSON.parse(
  readFileSync(new URL("../contracts/generated/enums.json", import.meta.url), "utf-8"),
) as Record<string, string[]>;

test("every Python enum has an identical TS twin", () => {
  for (const [name, values] of Object.entries(generated)) {
    assert.ok(name in ENUMS, `${name} missing from ENUMS in contracts.ts`);
    assert.deepEqual([...ENUMS[name]], values, `${name} differs`);
  }
  assert.equal(Object.keys(ENUMS).length, Object.keys(generated).length);
});

test("frozen feature orders", () => {
  assert.equal(NODE_FEATURES_V1.length, 15);
  assert.equal(EDGE_FEATURES_V1.length, 7);
});

test("contract version", () => {
  assert.equal(CONTRACT_VERSION, "backbone/1.1.0");
});
