import { describe, expect, it } from "vitest";

import { formatDuration, formatPrice, formatVolume } from "./format";

describe("formatPrice", () => {
  it("marks a zero price as free rather than showing 0", () => {
    expect(formatPrice(0)).toBe("Gratuit");
  });

  it("groups thousands so a price stays readable at a glance", () => {
    expect(formatPrice(1500)).toBe("1 500 FCFA");
    expect(formatPrice(500)).toBe("500 FCFA");
  });
});

describe("formatDuration", () => {
  it("returns null when the offer sets no time limit", () => {
    expect(formatDuration(null)).toBeNull();
  });

  it("expresses whole hours and days in words", () => {
    expect(formatDuration(3600)).toBe("1 heure");
    expect(formatDuration(7200)).toBe("2 heures");
    expect(formatDuration(86400)).toBe("1 jour");
    expect(formatDuration(604800)).toBe("7 jours");
  });

  it("falls back to minutes below an hour", () => {
    expect(formatDuration(1800)).toBe("30 minutes");
    expect(formatDuration(60)).toBe("1 minute");
  });

  it("keeps a leftover part rather than rounding it away", () => {
    expect(formatDuration(5400)).toBe("1 h 30 min");
  });
});

describe("formatVolume", () => {
  it("returns null when the offer sets no volume limit", () => {
    expect(formatVolume(null)).toBeNull();
  });

  it("uses the unit that keeps the number small", () => {
    expect(formatVolume(300_000_000)).toBe("300 Mo");
    expect(formatVolume(1_000_000_000)).toBe("1 Go");
    expect(formatVolume(3_000_000_000)).toBe("3 Go");
  });

  it("keeps one decimal only when it carries information", () => {
    expect(formatVolume(1_500_000_000)).toBe("1,5 Go");
  });

  it("uses English units and a decimal point", () => {
    expect(formatVolume(1_500_000_000, "en")).toBe("1.5 GB");
    expect(formatPrice(0, "en")).toBe("Free");
    expect(formatDuration(3600, "en")).toBe("1 hour");
  });
});
