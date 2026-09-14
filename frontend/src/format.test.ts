import { describe, expect, it } from "vitest";

import { formatIstDateTime } from "./format";


describe("IST date formatting", () => {
  it("converts UTC values to IST and labels the timezone", () => {
    const displayed = formatIstDateTime("2026-08-31T12:00:00Z");

    expect(displayed).toContain("5:30");
    expect(displayed).toMatch(/PM IST$/i);
  });
});
