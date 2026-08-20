import { describe, expect, it } from "vitest";

import { LOCALES, languageHref, resolveLocale, translate, type MessageKey } from "./i18n";

describe("resolveLocale", () => {
  it("prefers an explicit query parameter over storage and the browser", () => {
    expect(resolveLocale({ search: "en", stored: "wo", languages: ["fr-FR", "en"] })).toBe("en");
  });

  it("uses the stored preference when the query is missing or unknown", () => {
    expect(resolveLocale({ search: "pt", stored: "wo", languages: ["en-US"] })).toBe("wo");
    expect(resolveLocale({ stored: "en" })).toBe("en");
  });

  it("falls back to the browser language, then to French", () => {
    expect(resolveLocale({ languages: ["en-GB", "fr"] })).toBe("en");
    expect(resolveLocale({ languages: ["wo"] })).toBe("wo");
    expect(resolveLocale({ languages: ["pt-BR", "es"] })).toBe("fr");
    expect(resolveLocale({})).toBe("fr");
  });

  it("only accepts the three locales of the cahier des charges", () => {
    expect(LOCALES).toEqual(["fr", "wo", "en"]);
    expect(resolveLocale({ search: "FR" })).toBe("fr");
  });
});

describe("translate", () => {
  it("returns the French wording as the functional reference", () => {
    expect(translate("fr", "connect_free")).toBe("Se connecter gratuitement");
  });

  it("returns English and short Wolof for the same key", () => {
    expect(translate("en", "connect_free")).toBe("Connect for free");
    expect(translate("wo", "connect_free")).toBe("Jàpp ci neen");
  });

  it("interpolates named placeholders", () => {
    expect(translate("fr", "buy_offer", { name: "Pass 1 h" })).toBe("Acheter Pass 1 h");
    expect(translate("en", "buy_offer", { name: "Pass 1 h" })).toBe("Buy Pass 1 h");
  });

  it("falls back to French, then to the key, when a string is missing", () => {
    expect(translate("wo", "not_a_real_key" as MessageKey)).toBe("not_a_real_key");
  });

  it("covers every French key in English", () => {
    expect(translate("en", "connect_free")).not.toBe(translate("fr", "connect_free"));
    expect(translate("wo", "connect_free")).not.toBe(translate("fr", "connect_free"));
  });
});

describe("languageHref", () => {
  it("keeps the gateway identifier when switching language", () => {
    expect(languageHref("?nas_id=demo-nas-001", "en")).toBe("?nas_id=demo-nas-001&lang=en");
  });
});
