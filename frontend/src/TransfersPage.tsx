import { useEffect, useState, type FormEvent } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw, Send, ShieldCheck } from "lucide-react";

import api from "./api";
import { obtainDidProof, useAuth } from "./auth";
import { formatIstDateTime } from "./format";
import type { Asset, Identity, Paginated, Transfer } from "./types";
import { Empty, Page, Status, errorMessage } from "./ui";

export function TransfersPage() {
  const user = useAuth((state) => state.user)!;
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [myIdentity, setMyIdentity] = useState<Identity | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loaded, setLoaded] = useState(false);

  const load = async () => {
    setError("");
    try {
      const [transferResponse, assetResponse, identityResponse, meResponse] = await Promise.all([
        api.get<Paginated<Transfer>>("/transfers/"), api.get<Paginated<Asset>>("/assets/"),
        api.get<Paginated<Identity>>("/identities/"), api.get<Identity>("/identities/me/"),
      ]);
      setTransfers(transferResponse.data.results);
      setAssets(assetResponse.data.results.filter((asset) => asset.state === "ACTIVE" && asset.owner_did === meResponse.data.did));
      setIdentities(identityResponse.data.results.filter((identity) => identity.state === "ACTIVE" && identity.id !== meResponse.data.id));
      setMyIdentity(meResponse.data);
    } catch (value) { setError(errorMessage(value)); } finally { setLoaded(true); }
  };
  useEffect(() => { void load(); }, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy("create"); setError(""); setNotice("");
    try {
      const form = new FormData(event.currentTarget);
      const proof = await obtainDidProof("ASSET_TRANSFER");
      await api.post("/transfers/", { asset: form.get("asset"), recipient: form.get("recipient") }, { headers: { "X-DID-Proof-Token": proof } });
      setShowCreate(false); setNotice("Transfer request sent to the recipient for acceptance."); await load();
    } catch (value) { setError(errorMessage(value)); } finally { setBusy(null); }
  }

  async function act(transfer: Transfer, action: "accept" | "reject" | "approve" | "cancel") {
    setBusy(transfer.id); setError(""); setNotice("");
    try {
      const proof = await obtainDidProof("ASSET_TRANSFER");
      await api.post(`/transfers/${transfer.id}/${action}/`, {}, { headers: { "X-DID-Proof-Token": proof } });
      setNotice(action === "approve" ? "Governed blockchain transfer queued. Ownership changes only after confirmation." : `Transfer ${action} recorded.`);
      await load();
    } catch (value) { setError(errorMessage(value)); } finally { setBusy(null); }
  }

  const canApprove = user.permissions.includes("transfer.approve");
  const actions = <div className="page-actions"><button className="secondary compact" onClick={() => void load()}><RefreshCw size={14}/>Refresh</button>{assets.length > 0 && identities.length > 0 && <button className="primary compact" onClick={() => setShowCreate(value => !value)}><Send size={14}/>Request transfer</button>}</div>;
  return <Page title="Governed transfers" subtitle="Recipient consent and independent approval precede every on-chain ownership change." action={actions}>
    {showCreate && <form className="panel transfer-form" onSubmit={create}><div><p className="eyebrow">New transfer</p><h3>Choose asset and recipient</h3></div><label>Owned asset<select name="asset" required>{assets.map(asset => <option value={asset.id} key={asset.id}>{asset.name} · NFT #{asset.token_id}</option>)}</select></label><label>Recipient<select name="recipient" required>{identities.map(identity => <option value={identity.id} key={identity.id}>{identity.username} · {identity.did.slice(0, 25)}…</option>)}</select></label><button className="primary compact" disabled={busy === "create"}><ShieldCheck size={14}/>Sign & request</button></form>}
    {error && <div className="error"><AlertTriangle size={16}/>{error}</div>}{notice && <div className="notice"><CheckCircle2 size={16}/>{notice}</div>}
    <section className="transfer-grid">{transfers.map(transfer => <article className="panel transfer-card" key={transfer.id}><div className="request-card-head"><div><p className="eyebrow">NFT #{transfer.token_id ?? "pending"}</p><h3>{transfer.asset_name}</h3></div><Status value={transfer.state}/></div><div className="transfer-parties"><span><small>FROM</small><b>{transfer.sender_username}</b><code>{transfer.sender_did}</code></span><i>→</i><span><small>TO</small><b>{transfer.recipient_username}</b><code>{transfer.recipient_did}</code></span></div><p className="muted">Requested {formatIstDateTime(transfer.created_at)}{transfer.approved_by_username ? ` · approved by ${transfer.approved_by_username}` : ""}</p><div className="request-actions">{transfer.recipient_username === user.username && transfer.state === "PENDING_RECIPIENT" && <><button className="primary compact" disabled={busy === transfer.id} onClick={() => void act(transfer, "accept")}>Accept</button><button className="secondary compact" disabled={busy === transfer.id} onClick={() => void act(transfer, "reject")}>Reject</button></>}{transfer.sender_username === user.username && ["PENDING_RECIPIENT", "PENDING_APPROVAL"].includes(transfer.state) && <button className="secondary compact" disabled={busy === transfer.id} onClick={() => void act(transfer, "cancel")}>Cancel</button>}{canApprove && transfer.state === "PENDING_APPROVAL" && ![transfer.sender_username, transfer.recipient_username].includes(user.username) && <button className="primary compact" disabled={busy === transfer.id} onClick={() => void act(transfer, "approve")}>Approve & submit</button>}</div></article>)}{loaded && transfers.length === 0 && <section className="panel"><Empty text="No transfer requests are visible in your scope."/></section>}</section>
    {myIdentity && assets.length === 0 && <p className="muted transfer-help">A transfer can be requested after you own an ACTIVE NFT-backed asset.</p>}
  </Page>;
}
