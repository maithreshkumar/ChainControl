import { describe, expect, it } from "vitest";

import { useWallet } from "./wallet";


describe("controller wallet policy", () => {
  it("does not expose user-controlled create, import, replace, or remove operations", () => {
    const wallet = useWallet.getState() as unknown as Record<string, unknown>;

    expect(wallet).not.toHaveProperty("createWallet");
    expect(wallet).not.toHaveProperty("importWallet");
    expect(wallet).not.toHaveProperty("remove");
    expect(wallet).toHaveProperty("installProvisionedWallet");
  });
});
