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
  asset_type: "UNIQUE_PHYSICAL_ASSET" | "DIGITAL_ASSET";
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

export type InventoryStock = {
  id: string;
  variant: string;
  location: string;
  sku: string;
  item_name: string;
  variant_name: string;
  asset_type: "STOCK_ITEM" | "UNIQUE_PHYSICAL_ASSET" | "DIGITAL_ASSET" | "SOFTWARE_LICENSE";
  category: string;
  location_code: string;
  location_name: string;
  department_code: string | null;
  quantity_on_hand: number;
  quantity_reserved: number;
  quantity_issued: number;
  quantity_available: number;
  reorder_threshold: number;
  low_stock: boolean;
};

export type InventoryRequest = {
  id: string;
  requested_by: number;
  requested_by_username: string;
  variant: string;
  stock: string;
  sku: string;
  item_name: string;
  location_code: string;
  department: string | null;
  quantity: number;
  status: string;
  reason: string;
  reviewed_by_username: string | null;
  review_notes: string;
  created_at: string;
};

export type Transfer = {
  id: string;
  asset: string;
  asset_name: string;
  token_id: number | null;
  sender: string;
  sender_username: string;
  sender_did: string;
  recipient: string;
  recipient_username: string;
  recipient_did: string;
  state: string;
  approved_by_username: string | null;
  created_at: string;
};
