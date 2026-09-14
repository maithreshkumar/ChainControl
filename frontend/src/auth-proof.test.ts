import { beforeEach, describe, expect, it, vi } from "vitest";


describe("DID proof authorization", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.resetModules();
  });

  it("stops before creating a challenge when the wallet is not the DID controller", async () => {
    const get = vi.fn().mockResolvedValue({
      data: { controller_address: "0x1111111111111111111111111111111111111111" },
    });
    const post = vi.fn();
    const signMessage = vi.fn();
    vi.doMock("./api", () => ({ default: { get, post } }));
    vi.doMock("./wallet", () => ({
      useWallet: {
        getState: () => ({
          configured: true,
          unlocked: true,
          address: "0x2222222222222222222222222222222222222222",
          signMessage,
          configure: vi.fn(),
          lock: vi.fn(),
        }),
      },
    }));

    const { obtainDidProof } = await import("./auth");

    await expect(obtainDidProof("ASSET_MINT")).rejects.toThrow(/does not control this account's DID/i);
    expect(post).not.toHaveBeenCalled();
    expect(signMessage).not.toHaveBeenCalled();
  });

  it("creates, signs, and verifies a challenge for the matching controller", async () => {
    const controller = "0x1111111111111111111111111111111111111111";
    const get = vi.fn().mockResolvedValue({ data: { controller_address: controller } });
    const post = vi.fn()
      .mockResolvedValueOnce({ data: { challenge_id: "challenge-id", nonce: "nonce", message: "message" } })
      .mockResolvedValueOnce({ data: { proof_token: "proof-token" } });
    const signMessage = vi.fn().mockResolvedValue("signature");
    vi.doMock("./api", () => ({ default: { get, post } }));
    vi.doMock("./wallet", () => ({
      useWallet: {
        getState: () => ({
          configured: true,
          unlocked: true,
          address: controller.toLowerCase(),
          signMessage,
          configure: vi.fn(),
          lock: vi.fn(),
        }),
      },
    }));

    const { obtainDidProof } = await import("./auth");

    await expect(obtainDidProof("ASSET_MINT")).resolves.toBe("proof-token");
    expect(signMessage).toHaveBeenCalledWith("message");
    expect(post).toHaveBeenNthCalledWith(1, "/auth/challenges/", { purpose: "ASSET_MINT" });
    expect(post).toHaveBeenNthCalledWith(2, "/auth/challenges/verify/", {
      challenge_id: "challenge-id",
      nonce: "nonce",
      signature: "signature",
    });
  });
});
