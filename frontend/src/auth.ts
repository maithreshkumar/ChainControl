import { create } from "zustand";
import api from "./api";
import type { Identity, UserContext } from "./types";
import { useWallet } from "./wallet";

type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserContext | null;
  setSession: (accessToken: string, refreshToken: string, user: UserContext) => void;
  updateTokens: (accessToken: string, refreshToken?: string) => void;
  clear: () => void;
};

const sessionKey = "chaincontrol.auth.session";
type StoredSession = Pick<AuthState, "accessToken" | "refreshToken" | "user">;

function loadSession(): StoredSession {
  try {
    const stored = sessionStorage.getItem(sessionKey);
    if (stored) return JSON.parse(stored) as StoredSession;
  } catch { /* A blocked session store should behave like a signed-out browser. */ }
  return { accessToken: null, refreshToken: null, user: null };
}

function saveSession(session: StoredSession) {
  try { sessionStorage.setItem(sessionKey, JSON.stringify(session)); } catch { /* Keep the in-memory session usable. */ }
}

const initialSession = loadSession();

export const useAuth = create<AuthState>((set) => ({
  ...initialSession,
  setSession: (accessToken, refreshToken, user) => {
    saveSession({ accessToken, refreshToken, user });
    set({ accessToken, refreshToken, user });
  },
  updateTokens: (accessToken, refreshToken) => set((state) => {
    const next = { accessToken, refreshToken: refreshToken ?? state.refreshToken, user: state.user };
    saveSession(next);
    return next;
  }),
  clear: () => {
    useWallet.getState().lock();
    try { sessionStorage.removeItem(sessionKey); } catch { /* The in-memory session is still cleared. */ }
    set({ accessToken: null, refreshToken: null, user: null });
  },
}));

if (initialSession.user) useWallet.getState().configure(initialSession.user.id);

export async function login(username: string, password: string) {
  const { data } = await api.post<{ access: string; refresh: string }>("/auth/token/", { username, password });
  const user = (await api.get<UserContext>("/me/", { headers: { Authorization: `Bearer ${data.access}` } })).data;
  useWallet.getState().configure(user.id);
  useAuth.getState().setSession(data.access, data.refresh, user);
  return user;
}

export async function obtainDidProof(purpose: string) {
  const wallet = useWallet.getState();
  if (!wallet.configured) throw new Error("Claim the controller wallet issued by Django administration before authorizing this action.");
  if (!wallet.unlocked || !wallet.address) throw new Error("Unlock the admin-issued controller wallet before authorizing this action.");

  const identity = (await api.get<Identity>("/identities/me/")).data;
  if (wallet.address.toLowerCase() !== identity.controller_address.toLowerCase()) {
    throw new Error(`The admin-issued wallet does not control this account's DID. Ask Django administration to reissue the controller wallet for ${identity.controller_address}.`);
  }

  const { data: challenge } = await api.post("/auth/challenges/", { purpose });
  const signature = await wallet.signMessage(challenge.message);
  const { data } = await api.post("/auth/challenges/verify/", {
    challenge_id: challenge.challenge_id,
    nonce: challenge.nonce,
    signature,
  });
  return data.proof_token as string;
}
