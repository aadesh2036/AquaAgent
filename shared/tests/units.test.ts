import { test } from "node:test";
import assert from "node:assert/strict";
import * as u from "../units.ts";

const close = (a: number, b: number, tol = 1e-9) => assert.ok(Math.abs(a - b) <= tol, `${a} != ${b}`);

test("flow", () => {
  close(u.m3sToLps(0.00946), 9.46);
  close(u.lpsToLpm(1), 60);
  close(u.gpmToLps(150), 9.4635, 1e-3);
});

test("length", () => {
  close(u.ftToM(700), 213.36);
  close(u.inToM(14), 0.3556);
});

test("clock", () => {
  assert.equal(u.clockLabel(43200), "12:00");
  assert.equal(u.clockLabel(86400 + 3660), "01:01");
});

test("fmt", () => {
  assert.equal(u.fmt(9.456, "L/s"), "9.5 L/s");
  assert.equal(u.fmt(null, "m"), "— m");
});
