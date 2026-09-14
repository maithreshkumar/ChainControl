import { Wallet, type HDNodeWallet } from "ethers";
import { create } from "zustand";

const storageKey = (userId: number) => `chaincontrol.admin-wallet.${userId}`;
type LocalWallet = Wallet | HDNodeWallet;
let activeWallet: LocalWallet | null = null;

type WalletState = {
  userId: number | null;
  address: string | null;
  configured: boolean;
  unlocked: boolean;
  configure: (userId: number) => void;
  installProvisionedWallet: (encryptedWallet: unknown, accessCode: string) => Promise<void>;
  unlock: (password: string) => Promise<void>;
  lock: () => void;
  signMessage: (message: string) => Promise<string>;
};

function encryptedAddress(encryptedJson: string) {
  const parsed = JSON.parse(encryptedJson) as { address?: string };
  if (!parsed.address) throw new Error("The local wallet file is invalid.");
  return `0x${parsed.address.replace(/^0x/, "")}`;
}

function requireUserId() {
  const userId = useWallet.getState().userId;
  if (userId === null) throw new Error("Sign in before configuring ChainControl Wallet.");
  return userId;
}

export const useWallet = create<WalletState>((set) => ({
  userId: null,
  address: null,
  configured: false,
  unlocked: false,
  configure: (userId) => {
    activeWallet = null;
    const encryptedJson = localStorage.getItem(storageKey(userId));
    set({
      userId,
      address: encryptedJson ? encryptedAddress(encryptedJson) : null,
      configured: Boolean(encryptedJson),
      unlocked: false,
    });
  },
  installProvisionedWallet: async (encryptedWallet, accessCode) => {
    const userId = requireUserId();
    const encryptedJson = JSON.stringify(encryptedWallet);
    const wallet = await Wallet.fromEncryptedJson(encryptedJson, accessCode);
    localStorage.setItem(storageKey(userId), encryptedJson);
    activeWallet = wallet;
    set({ address: wallet.address, configured: true, unlocked: true });
  },
  unlock: async (password) => {
    const userId = requireUserId();
    const encryptedJson = localStorage.getItem(storageKey(userId));
    if (!encryptedJson) throw new Error("No ChainControl Wallet exists for this account.");
    const wallet = await Wallet.fromEncryptedJson(encryptedJson, password);
    activeWallet = wallet;
    set({ address: wallet.address, configured: true, unlocked: true });
  },
  lock: () => {
    activeWallet = null;
    set({ unlocked: false });
  },
  signMessage: async (message) => {
    if (!activeWallet) throw new Error("Unlock ChainControl Wallet before authorizing this action.");
    return activeWallet.signMessage(message);
  },
}));
