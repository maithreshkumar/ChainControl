export type UserContext = {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  department: string | null;
  roles: string[];
  permissions: string[];
};

export type Asset = {
  id: string;
  name: string;
  kind: "DIGITAL" | "PHYSICAL";
  classification: number;
  state: string;
  token_id: number | null;
  owner_did: string | null;
  created_at: string;
};

export type Identity = {
  id: string;
  user: number;
  username: string;
  did: string;
  controller_address: string;
  state: string;
  key_version: number;
  registration_tx_hash: string;
  created_at: string;
};

export type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type Validator = { validator: number; rpc: string; healthy: boolean; block_height: number | null };
export type NetworkHealth = { chain_id: number; healthy: boolean; validators: Validator[] };

export type WalletProvisionStatus = {
  issued: boolean;
  claimed: boolean;
  controller_address: string | null;
};

export type WalletProvisionClaim = {
  encrypted_wallet: unknown;
  controller_address: string;
};
