import { describe, expect, it } from "vitest";

import { toE164 } from "./phone";

describe("toE164", () => {
  it("prefixes a local Senegalese mobile with +221", () => {
    expect(toE164("770972908")).toBe("+221770972908");
    expect(toE164("77 097 29 08")).toBe("+221770972908");
  });

  it("keeps a number already in international format", () => {
    expect(toE164("+221771234567")).toBe("+221771234567");
    expect(toE164("00221770972908")).toBe("+221770972908");
  });

  it("accepts 221 without the plus sign", () => {
    expect(toE164("221770972908")).toBe("+221770972908");
  });

  it("rejects a number too short to be a mobile", () => {
    expect(toE164("77 123")).toBeNull();
    expect(toE164("")).toBeNull();
  });
});
