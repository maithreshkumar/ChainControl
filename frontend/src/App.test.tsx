import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { useAuth } from "./auth";
import { useWallet } from "./wallet";

const walletProvisionMock = vi.hoisted(() => ({ claimed: false }));

vi.mock("./api", () => ({
  default: {
    get: vi.fn((endpoint: string) => {
      if (endpoint === "/identities/me/") return Promise.resolve({ data: { controller_address: "0x1111111111111111111111111111111111111111" } });
      if (endpoint === "/wallet-provision/") return Promise.resolve({ data: { issued: true, claimed: walletProvisionMock.claimed, controller_address: "0x1111111111111111111111111111111111111111" } });
      return new Promise(() => undefined);
    }),
    post: vi.fn(() => new Promise(() => undefined)),
  },
}));

describe("role-aware application", () => {
  beforeEach(() => {
    walletProvisionMock.claimed = false;
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

  it("shows the user asset registration form with digital and physical details", () => {
    useAuth.setState({ accessToken: "token", user: { id: 1, username: "user", email: "user@example.test", first_name: "", last_name: "", department: "RADAR", roles: ["USER"], permissions: ["asset.view", "asset.mint"] } });

    render(<MemoryRouter initialEntries={["/assets"]}><App /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /register asset/i }));

    expect(screen.getByRole("heading", { name: /anchor an encrypted asset/i })).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toBeVisible();
    expect(screen.getByRole("option", { name: "Digital" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Physical" })).toBeInTheDocument();
    expect(screen.getByLabelText("File")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "PHYSICAL" } });
    expect(screen.getByLabelText("Serial number")).toBeVisible();
    expect(screen.getByLabelText("Custody reference")).toBeVisible();
    expect(screen.getByRole("button", { name: /verify did & submit/i })).toBeInTheDocument();
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

  it.each([
    ["USER", "user"],
    ["VALIDATOR", "validator"],
  ])("shows the wallet password field when a %s wallet is locked", async (role, username) => {
    useAuth.setState({ accessToken: "token", user: { id: 1, username, email: `${username}@example.test`, first_name: "", last_name: "", department: "RADAR", roles: [role], permissions: ["asset.view"] } });
    useWallet.setState({ userId: 1, address: "0x1111111111111111111111111111111111111111", configured: true, unlocked: false });

    render(<MemoryRouter initialEntries={["/wallet"]}><App /></MemoryRouter>);

    expect(await screen.findByLabelText(/wallet password \/ access code/i)).toBeVisible();
    expect(screen.getByPlaceholderText(/enter your wallet password/i)).toHaveAttribute("type", "password");
    expect(screen.getByRole("button", { name: /^unlock wallet$/i })).toBeInTheDocument();
  });

  it.each([
    ["USER", "user"],
    ["VALIDATOR", "validator"],
  ])("shows the wallet recovery password field when a %s wallet was claimed in another browser", async (role, username) => {
    walletProvisionMock.claimed = true;
    useAuth.setState({ accessToken: "token", user: { id: 1, username, email: `${username}@example.test`, first_name: "", last_name: "", department: "RADAR", roles: [role], permissions: ["asset.view"] } });
    useWallet.setState({ userId: 1, address: null, configured: false, unlocked: false });

    render(<MemoryRouter initialEntries={["/wallet"]}><App /></MemoryRouter>);

    expect(await screen.findByLabelText(/wallet password \/ access code/i)).toBeVisible();
    expect(screen.getByPlaceholderText(/enter your wallet password/i)).toHaveAttribute("type", "password");
    expect(screen.getByRole("button", { name: /restore & unlock wallet/i })).toBeInTheDocument();
  });
});
