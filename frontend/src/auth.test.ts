import { beforeEach, describe, expect, it, vi } from "vitest";

const user = {
  id: 7,
  username: "user",
  email: "user@example.test",
  first_name: "",
  last_name: "",
  department: "GOVERNANCE",
  roles: ["USER"],
  permissions: ["asset.view"],
};

describe("browser refresh session", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.resetModules();
    vi.doMock("./wallet", () => ({
      useWallet: { getState: () => ({ configure: vi.fn(), lock: vi.fn(), signMessage: vi.fn() }) },
    }));
  });

  it("restores the authenticated user and tokens from session storage", async () => {
    sessionStorage.setItem("chaincontrol.auth.session", JSON.stringify({
      accessToken: "access-token",
      refreshToken: "refresh-token",
      user,
    }));

    const { useAuth } = await import("./auth");

    expect(useAuth.getState().accessToken).toBe("access-token");
    expect(useAuth.getState().refreshToken).toBe("refresh-token");
    expect(useAuth.getState().user?.username).toBe("user");
  });
});
