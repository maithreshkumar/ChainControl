import { describe, expect, it } from "vitest";

import { isAccessTokenFailure } from "./api";


describe("API authentication failure classification", () => {
  it("does not sign the user out for an invalid DID signature", () => {
    expect(isAccessTokenFailure({
      response: {
        status: 401,
        data: { error: { code: "SIGNATURE_INVALID", details: {} } },
        headers: {},
      },
    })).toBe(false);
  });

  it("recognizes an expired JWT access token", () => {
    expect(isAccessTokenFailure({
      response: {
        status: 401,
        data: { error: { details: { code: "token_not_valid" } } },
        headers: { "www-authenticate": "Bearer realm=\"api\"" },
      },
    })).toBe(true);
  });
});
