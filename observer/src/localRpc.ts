import axios from "axios";
import { Interface } from "ethers";

export const localNodeMode = Boolean(import.meta.env.VITE_LOCAL_RPC_URL);
const rpcUrl = import.meta.env.VITE_LOCAL_RPC_URL || "/rpc/";

let requestId = 1;
async function rpc<T>(method: string, params: unknown[] = []): Promise<T> {
  const response = await axios.post(rpcUrl, { jsonrpc: "2.0", method, params, id: requestId++ }, { timeout: 12000 });
  if (response.data.error) throw new Error(response.data.error.message || `${method} failed`);
  return response.data.result as T;
}

const number = (value?: string | number | null) => value == null ? 0 : typeof value === "number" ? value : Number.parseInt(value, 16);
const iso = (timestamp: string) => new Date(number(timestamp) * 1000).toISOString();

type Deployment = { name: string; address: string; abi: any[]; iface: Interface };
let deploymentCache: Promise<Map<string, Deployment>> | null = null;

function jsonValue(value: any): any {
  if (typeof value === "bigint") return value.toString();
  if (Array.isArray(value)) return value.map(jsonValue);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, jsonValue(item)]));
  return value;
}

async function deployments(): Promise<Map<string, Deployment>> {
  if (!deploymentCache) deploymentCache = fetch("/deployments/1337.json", { cache: "no-store" })
    .then(response => {
      if (!response.ok) throw new Error("ABI bundle unavailable");
      return response.json();
    })
    .then(document => new Map<string, Deployment>(Object.entries(document.contracts ?? {}).map(([name, value]: [string, any]) => {
      const deployment = { name, address: value.address, abi: value.abi, iface: new Interface(value.abi) };
      return [value.address.toLowerCase(), deployment];
    })))
    .catch(() => new Map<string, Deployment>());
  return deploymentCache;
}

function decodeCall(tx: Record<string, any>, known: Map<string, Deployment>) {
  const deployment = tx.to ? known.get(tx.to.toLowerCase()) : undefined;
  if (!deployment || !tx.input || tx.input === "0x") return { contract: deployment?.name ?? null, function: null, parameters: {} };
  try {
    const parsed = deployment.iface.parseTransaction({ data: tx.input, value: tx.value });
    const parameters = parsed ? Object.fromEntries(parsed.fragment.inputs.map((input, index) => [input.name || String(index), jsonValue(parsed.args[index])])) : {};
    return { contract: deployment.name, function: parsed?.name ?? null, parameters };
  } catch {
    return { contract: deployment.name, function: null, parameters: {} };
  }
}

function decodeEvents(receipt: Record<string, any>, known: Map<string, Deployment>) {
  return (receipt.logs ?? []).flatMap((log: Record<string, any>) => {
    const deployment = known.get((log.address ?? "").toLowerCase());
    if (!deployment) return [];
    try {
      const parsed = deployment.iface.parseLog({ topics: log.topics, data: log.data });
      if (!parsed) return [];
      return [{
        contract: deployment.name,
        event: parsed.name,
        parameters: Object.fromEntries(parsed.fragment.inputs.map((input, index) => [input.name || String(index), jsonValue(parsed.args[index])])),
        log_index: number(log.logIndex),
      }];
    } catch {
      return [];
    }
  });
}

function transactionSummary(tx: Record<string, any>, known: Map<string, Deployment>) {
  const decoded = decodeCall(tx, known);
  return {
    hash: tx.hash,
    index: number(tx.transactionIndex),
    from: tx.from,
    to: tx.to ?? null,
    operation: decoded.function || "Blockchain transaction",
    contract: decoded.contract,
    function: decoded.function,
  };
}

export async function localBlock(identifier: string | number, includeAll = false) {
  const tag = typeof identifier === "number" ? `0x${identifier.toString(16)}` : identifier;
  const [block, head, known] = await Promise.all([
    rpc<Record<string, any>>("eth_getBlockByNumber", [tag, true]),
    rpc<string>("eth_blockNumber"),
    deployments(),
  ]);
  if (!block) throw new Error("Blockchain block was not found on this node.");
  const transactions = (block.transactions ?? []).map((tx: Record<string, any>) => transactionSummary(tx, known));
  const shown = includeAll ? transactions : transactions.slice(0, 8);
  return {
    number: number(block.number),
    hash: block.hash,
    parent_hash: block.parentHash,
    timestamp: iso(block.timestamp),
    miner: block.miner,
    gas_limit: number(block.gasLimit),
    gas_used: number(block.gasUsed),
    size: number(block.size),
    transaction_count: transactions.length,
    transactions: shown,
    transactions_truncated: shown.length < transactions.length,
    finalized: number(block.number) < number(head),
  };
}

export async function localBlocks(limit = 12, before?: number | null) {
  const head = number(await rpc<string>("eth_blockNumber"));
  const start = Math.min(before ?? head, head);
  const blockNumbers = Array.from({ length: Math.min(limit, start + 1) }, (_, index) => start - index);
  const results = await Promise.all(blockNumbers.map(value => localBlock(value)));
  return { latest: head, count: results.length, next_before: results.length && results.at(-1)!.number > 0 ? results.at(-1)!.number - 1 : null, results };
}

export async function localTransaction(hash: string) {
  const [tx, receipt, known] = await Promise.all([
    rpc<Record<string, any>>("eth_getTransactionByHash", [hash]),
    rpc<Record<string, any>>("eth_getTransactionReceipt", [hash]),
    deployments(),
  ]);
  if (!tx || !receipt) throw new Error("Transaction was not found on this node.");
  const block = await rpc<Record<string, any>>("eth_getBlockByNumber", [tx.blockNumber, false]);
  return {
    ...transactionSummary(tx, known),
    block_number: number(tx.blockNumber),
    block_hash: tx.blockHash,
    transaction_index: number(tx.transactionIndex),
    timestamp: iso(block.timestamp),
    nonce: number(tx.nonce),
    value: number(tx.value),
    gas: number(tx.gas),
    gas_price: number(tx.gasPrice),
    gas_used: number(receipt.gasUsed),
    status: number(receipt.status) === 1 ? "SUCCESS" : "REVERTED",
    contract_address: receipt.contractAddress ?? null,
    decoded: decodeCall(tx, known),
    events: decodeEvents(receipt, known),
    business: null,
    raw_input: tx.input,
    metadata_available: false,
  };
}

export type LocalNodeConfiguration = {
  node_name?: string;
  node_uuid?: string;
  role?: string;
  status?: string;
  enode?: string;
  network_latest_block?: number;
};

async function nodeConfiguration(): Promise<LocalNodeConfiguration> {
  try {
    const response = await fetch("/node-config.json", { cache: "no-store" });
    return response.ok ? await response.json() : {};
  } catch {
    return {};
  }
}

export async function localHealth() {
  const [chainHex, headHex, peerHex, syncing, validators, nodeInfo, peers, configuration] = await Promise.all([
    rpc<string>("eth_chainId"),
    rpc<string>("eth_blockNumber"),
    rpc<string>("net_peerCount"),
    rpc<false | { currentBlock: string; highestBlock: string }>("eth_syncing"),
    rpc<string[]>("qbft_getValidatorsByBlockNumber", ["latest"]),
    rpc<Record<string, any>>("admin_nodeInfo").catch((): Record<string, any> => ({})),
    rpc<Record<string, any>[]>("admin_peers").catch(() => []),
    nodeConfiguration(),
  ]);
  const head = number(headHex);
  const highest = syncing ? Math.max(number(syncing.highestBlock), head) : Math.max(configuration.network_latest_block ?? head, head);
  const syncPercentage = highest === 0 ? 100 : Math.min(100, Number(((head / highest) * 100).toFixed(2)));
  return {
    chain_id: number(chainHex),
    healthy: true,
    consensus_healthy: validators.length > 0,
    latest_block: head,
    validator_count: validators.length,
    validator_addresses: validators,
    nodes: [{ validator: configuration.node_name || "This node", healthy: true, block_height: head, peer_count: number(peerHex), validator_count: validators.length, validator_addresses: validators }],
    validators: [{ validator: configuration.node_name || "This node", healthy: true, block_height: head, peer_count: number(peerHex), validator_count: validators.length, validator_addresses: validators }],
    this_node: {
      node_name: configuration.node_name || "Local ChainControl node",
      node_uuid: configuration.node_uuid || "Not enrolled",
      role: configuration.role || "FULL_NODE",
      status: configuration.status || (syncing ? "SYNCING" : "ONLINE"),
      sync_percentage: syncPercentage,
      local_block: head,
      network_block: highest,
      peer_count: peers.length || number(peerHex),
      enode: configuration.enode || nodeInfo.enode || "Unavailable",
    },
  };
}
