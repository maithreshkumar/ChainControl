import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { useAuth } from "./auth";
import { useWallet } from "./wallet";

vi.mock("./api", () => ({
  default: {
    get: vi.fn((endpoint: string) => {
      if (endpoint === "/identities/me/") return Promise.resolve({ data: { controller_address: "0x1111111111111111111111111111111111111111" } });
      if (endpoint === "/wallet-provision/") return Promise.resolve({ data: { issued: true, claimed: false, controller_address: "0x1111111111111111111111111111111111111111" } });
      return new Promise(() => undefined);
    }),
    post: vi.fn(() => new Promise(() => undefined)),
  },
}));

describe("role-aware application", () => {
  beforeEach(() => {
    useAuth.setState({ accessToken: null, refreshToken: null, user: null });
    useWallet.setState({ userId: null, address: null, configured: false, unlocked: false });
  });
  afterEach(() => cleanup());

  it("shows controlled sign in when unauthenticated", () => {
    render(<MemoryRouter><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: /sign in to chaincontrol/i })).toBeInTheDocument();
  });

  it("does not show audit navigation without its permission", () => {
    useAuth.setState({ accessToken: "token", user: { id: 1, username: "alice", email: "a@example.test", first_name: "Alice", last_name: "", department: "RADAR", roles: ["USER"], permissions: ["asset.view"] } });
    render(<MemoryRouter><App /></MemoryRouter>);
    expect(screen.queryByRole("link", { name: /audit trail/i })).not.toBeInTheDocument();
  });

  it("offers only the admin-issued wallet claim flow", async () => {
    useAuth.setState({ accessToken: "token", user: { id: 1, username: "alice", email: "a@example.test", first_name: "Alice", last_name: "", department: "RADAR", roles: ["USER"], permissions: ["asset.view"] } });
    useWallet.setState({ userId: 1, address: null, configured: false, unlocked: false });

    render(<MemoryRouter initialEntries={["/wallet"]}><App /></MemoryRouter>);

    expect(await screen.findByRole("button", { name: /claim admin-issued wallet/i })).toBeInTheDocument();
    expect(screen.queryByText(/create new wallet/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/import existing key/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /change controller wallet/i })).not.toBeInTheDocument();
  });
});
