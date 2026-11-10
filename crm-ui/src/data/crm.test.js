import test from "node:test";
import assert from "node:assert/strict";
import { divisionLabel, divisions } from "./crm.js";
import { defaultSettings } from "../lib/runtimeSettings.js";

test("all six CRM divisions have settings defaults and display labels", () => {
  assert.deepEqual(divisions, ["MMC", "nemilink", "ClearCode Labs", "ENGEN", "Visotonics", "Overview"]);
  assert.equal(divisionLabel("nemilink"), "Nemilink");
  assert.deepEqual(Object.keys(defaultSettings().divisions), divisions);
  assert.deepEqual(Object.fromEntries(divisions.map((name) => [name, defaultSettings().divisions[name].prefix])), {
    MMC: "MMC", nemilink: "NEM", "ClearCode Labs": "CCL", ENGEN: "ENG", Visotonics: "VIS", Overview: "OVW",
  });
});
