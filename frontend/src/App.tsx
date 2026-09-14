import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Navigate, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { Activity, AlertTriangle, Boxes, CheckCircle2, ChevronRight, Eye, EyeOff, Fingerprint, KeyRound, LayoutDashboard, LockKeyhole, LogOut, Network, RefreshCw, Search, ShieldCheck, WalletCards } from "lucide-react";
import axios from "axios";
import api from "./api";
import { login, obtainDidProof, useAuth } from "./auth";
import { useWallet } from "./wallet";
import { formatIstDateTime } from "./format";
import type { Asset, Identity as IdentityRecord, NetworkHealth, Paginated, WalletProvisionClaim, WalletProvisionStatus } from "./types";

const nav: Array<{ to: string; label: string; icon: typeof LayoutDashboard; permission?: string; role?: string }> = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/identity", label: "Identity", icon: Fingerprint },
  { to: "/assets", label: "Assets", icon: Boxes },
  { to: "/validator", label: "Validator", icon: CheckCircle2, role: "VALIDATOR" },
  { to: "/wallet", label: "Wallet", icon: WalletCards },
  { to: "/transfers", label: "Transfers", icon: Activity },
  { to: "/audit", label: "Audit trail", icon: Search, permission: "audit.view" },
  { to: "/security", label: "Security", icon: ShieldCheck, permission: "security.view" },
  { to: "/network", label: "Blockchain", icon: Network, permission: "blockchain.health" },
];

function errorMessage(error: unknown) {
  if (axios.isAxiosError(error)) return error.response?.data?.error?.message ?? error.message;
  return error instanceof Error ? error.message : "The operation failed.";
}

function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const user = await login(username, password);
      navigate(user.roles.includes("VALIDATOR") ? "/validator" : "/");
    } catch (value) { setError(errorMessage(value)); } finally { setBusy(false); }
  }
  return <main className="login-shell">
    <section className="login-story">
      <div className="brand"><span className="brand-mark"><LockKeyhole size={20} /></span>CHAINCONTROL</div>
      <div className="story-copy"><p className="eyebrow">Sovereign asset governance</p><h1>Identity is the control plane.</h1><p>Cryptographic identity, governed access, and verifiable asset custody—anchored to a private permissioned ledger.</p></div>
      <div className="trust-row"><span>QBFT CONSENSUS</span><span>AES-256-GCM</span><span>ERC-721 PROVENANCE</span></div>
    </section>
    <section className="login-panel"><form onSubmit={submit} className="login-card" autoComplete="off">
      <p className="eyebrow">Authorized personnel</p><h2>Sign in to ChainControl</h2><p className="muted">Use your organization-issued credentials.</p>
      <label>Username<input name="chaincontrol-username" autoComplete="off" value={username} onChange={(e) => setUsername(e.target.value)} required /></label>
      <label>
        Password
        <div className="password-input-wrapper">
          <input
            type={showPassword ? "text" : "password"}
            name="chaincontrol-password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button
            type="button"
            className="password-toggle-btn"
            onClick={() => setShowPassword(!showPassword)}
            aria-label={showPassword ? "Hide password" : "Show password"}
          >
            {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
      </label>
      {error && <div className="error"><AlertTriangle size={16} />{error}</div>}
      <button className="primary" disabled={busy}>{busy ? "Verifying…" : "Continue securely"}<ChevronRight size={18} /></button>
      <p className="fine-print">Sensitive actions require a separate one-time DID signature.</p>
    </form></section>
  </main>;
}

function Shell({ children }: { children: ReactNode }) {
  const { user, clear } = useAuth();
  const wallet = useWallet();
  const navigate = useNavigate();
  const links = nav.filter((item) => (!item.permission || user?.permissions.includes(item.permission)) && (!item.role || user?.roles.includes(item.role)));
  return <div className="app-shell">
    <aside><div className="brand"><span className="brand-mark"><LockKeyhole size={18} /></span>CHAINCONTROL</div>
      <nav>{links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === "/"}><Icon size={18} />{label}</NavLink>)}</nav>
      <div className="operator"><span className="avatar">{user?.username.slice(0, 2).toUpperCase()}</span><div><strong>{user?.first_name || user?.username}</strong><span>{user?.roles.join(" · ") || "No role"}</span></div><button aria-label="Sign out" onClick={() => { clear(); navigate("/"); }}><LogOut size={17} /></button></div>
    </aside>
    <div className="workspace"><header><div><p className="eyebrow">Governance console</p><span className="crumb">{user?.department ?? "Organization-wide"}</span></div><NavLink className="status-pill" to="/wallet"><i className={wallet.unlocked ? "" : "locked"} />Wallet {wallet.unlocked ? "unlocked" : "locked"}</NavLink></header>{children}</div>
  </div>;
}

function Stat({ label, value, meta }: { label: string; value: string | number; meta: string }) {
  return <article className="stat"><span>{label}</span><strong>{value}</strong><small>{meta}</small></article>;
}

function Overview() {
  const user = useAuth((s) => s.user)!;
  const [assets, setAssets] = useState<Paginated<Asset> | null>(null);
  useEffect(() => { api.get("/assets/").then((r) => setAssets(r.data)).catch(() => setAssets({ count: 0, next: null, previous: null, results: [] })); }, []);
  const active = assets?.results.filter((a) => a.state === "ACTIVE").length ?? 0;
  return <Page title="Operational overview" subtitle="Live governance state from ChainControl services.">
    <div className="stats"><Stat label="Visible assets" value={assets?.count ?? "—"} meta="scope-filtered" /><Stat label="Active custody" value={active} meta="confirmed projection" /><Stat label="Permissions" value={user.permissions.length} meta="effective grants" /><Stat label="Identity assurance" value="DID" meta="challenge ready" /></div>
    <section className="panel split"><div><p className="eyebrow">Security posture</p><h3>Authority remains explicit</h3><p className="muted">Application permissions and smart-contract roles are checked independently. No Django superuser receives ledger authority automatically.</p></div><div className="assurance"><div><ShieldCheck /><span><strong>Fail closed</strong><small>Ledger-sensitive operations stop if verification is unavailable.</small></span></div><div><Fingerprint /><span><strong>Step-up verification</strong><small>High-risk actions consume one-time DID challenges.</small></span></div></div></section>
  </Page>;
}

function Assets() {
  const user = useAuth((s) => s.user)!;
  const [data, setData] = useState<Paginated<Asset> | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const load = () => api.get<Paginated<Asset>>("/assets/").then((r) => setData(r.data)).catch((e) => setError(errorMessage(e)));
  useEffect(() => { void load(); }, []);
  async function refreshBlockchain() {
    setRefreshing(true); setError(""); setNotice("");
    try {
      await api.post("/assets/refresh-blockchain/");
      await new Promise((resolve) => setTimeout(resolve, 1800));
      await load();
      setNotice("Blockchain receipts refreshed. Confirmed submissions remain pending until a validator activates them.");
    } catch (value) { setError(errorMessage(value)); } finally { setRefreshing(false); }
  }
  const actions = <div className="page-actions"><button className="secondary compact" disabled={refreshing} onClick={() => void refreshBlockchain()}><RefreshCw className={refreshing ? "spinning" : ""} size={15} />{refreshing ? "Refreshing…" : "Refresh blockchain"}</button>{user.permissions.includes("asset.mint") && <button className="primary compact" onClick={() => setShowCreate(!showCreate)}>Register asset</button>}</div>;
  return <Page title="Asset registry" subtitle="Custody, integrity, and ownership are confirmed against the authoritative ledger." action={actions}>
    {showCreate && <AssetForm onDone={() => { setShowCreate(false); load(); }} />}
    {error && <div className="error">{error}</div>}
    {notice && <div className="notice"><CheckCircle2 size={16} />{notice}</div>}
    <section className="panel table-wrap"><table><thead><tr><th>Asset</th><th>Type</th><th>State</th><th>Token</th><th>Owner</th></tr></thead><tbody>
      {data?.results.map((asset) => <tr key={asset.id}><td><strong>{asset.name}</strong><small>{asset.id}</small></td><td>{asset.kind}</td><td><Status value={asset.state} /></td><td>{asset.token_id ?? "Pending"}</td><td className="mono">{asset.owner_did ? `${asset.owner_did.slice(0, 24)}…` : "Unassigned"}</td></tr>)}
    </tbody></table>{data && data.count === 0 && <Empty text="No assets are visible in your current scope." />}</section>
  </Page>;
}

function AssetForm({ onDone }: { onDone: () => void }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const [kind, setKind] = useState("DIGITAL");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const form = new FormData(event.currentTarget);
      const proof = await obtainDidProof("ASSET_MINT");
      await api.post("/assets/", form, { headers: { "X-DID-Proof-Token": proof } });
      onDone();
    } catch (value) { setError(errorMessage(value)); } finally { setBusy(false); }
  }
  return <form className="panel asset-form" onSubmit={submit}><div><p className="eyebrow">New registration</p><h3>Anchor an encrypted asset</h3></div><label>Name<input name="name" required /></label><label>Type<select name="kind" value={kind} onChange={(event) => setKind(event.target.value)}><option value="DIGITAL">Digital</option><option value="PHYSICAL">Physical</option></select></label><label>Classification<select name="classification"><option value="10">Internal</option><option value="20">Confidential</option><option value="30">Restricted</option></select></label>{kind === "DIGITAL" ? <label>File<input name="file" type="file" required /></label> : <><label>Serial number<input name="serial_number" required /></label><label>Custody reference<input name="custody_identifier" /></label></>}{error && <div className="error">{error}</div>}<button className="primary compact" disabled={busy}>{busy ? "Authorizing…" : "Verify DID & submit"}</button></form>;
}

function Identity() {
  const [identity, setIdentity] = useState<any>(null);
  useEffect(() => { api.get("/identities/me/").then((r) => setIdentity(r.data)); }, []);
  return <Page title="My identity" subtitle="Your organization-issued decentralized identity and controller status."><section className="panel identity-card"><div className="identity-seal"><Fingerprint size={38} /></div><div><p className="eyebrow">Decentralized identity</p><h3>{identity?.did ?? "No identity enrolled"}</h3><p className="mono muted">{identity?.controller_address ?? "Controller unavailable"}</p></div><Status value={identity?.state ?? "NOT ENROLLED"} /></section></Page>;
}

function ValidatorWorkspace() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [identities, setIdentities] = useState<IdentityRecord[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const load = async () => {
    setError("");
    try {
      const [assetResponse, identityResponse] = await Promise.all([
        api.get<Paginated<Asset>>("/assets/"),
        api.get<Paginated<IdentityRecord>>("/identities/"),
      ]);
      setAssets(assetResponse.data.results.filter((asset) => asset.state === "BLOCKCHAIN_PENDING"));
      setIdentities(identityResponse.data.results.filter((identity) => ["INVITED", "VALIDATION_PENDING"].includes(identity.state)));
    } catch (value) { setError(errorMessage(value)); } finally { setLoaded(true); }
  };
  useEffect(() => { void load(); }, []);
  async function validateAsset(assetId: string) {
    setBusy(assetId); setError("");
    try {
      const proof = await obtainDidProof("ASSET_ACTIVATE");
      await api.post(`/assets/${assetId}/activate/`, {}, { headers: { "X-DID-Proof-Token": proof } });
      await load();
    } catch (value) { setError(errorMessage(value)); } finally { setBusy(null); }
  }
  async function validateIdentity(identityId: string) {
    setBusy(identityId); setError("");
    try {
      const proof = await obtainDidProof("IDENTITY_VALIDATE");
      await api.post(`/identities/${identityId}/validate/`, {}, { headers: { "X-DID-Proof-Token": proof } });
      await load();
    } catch (value) { setError(errorMessage(value)); } finally { setBusy(null); }
  }
  return <Page title="Validator workspace" subtitle="Independent review queues for submitted identities and blockchain-pending assets." action={<button className="secondary compact" onClick={() => void load()}><RefreshCw size={15} />Refresh queues</button>}>
    <div className="validator-summary">
      <Stat label="Pending identities" value={identities.length} meta="awaiting validator approval" />
      <Stat label="Pending assets" value={assets.length} meta="awaiting integrity validation" />
      <section className="panel validator-policy"><ShieldCheck size={24} /><div><strong>Separation of duties</strong><small>You cannot approve a record that you submitted.</small></div></section>
    </div>
    {error && <div className="error"><AlertTriangle size={16} />{error}</div>}
    <section className="queue-section"><div className="section-heading"><div><p className="eyebrow">Identity queue</p><h3>DID submissions</h3></div><span>{identities.length} waiting</span></div>
      <div className="review-grid">{identities.map((identity) => <article className="panel review-card" key={identity.id}><div className="review-icon"><Fingerprint size={22} /></div><div className="review-content"><div><strong>{identity.username}</strong><Status value={identity.state} /></div><p className="mono">{identity.did}</p><small>Controller {identity.controller_address}</small><small>Submitted {formatIstDateTime(identity.created_at)}</small></div><button className="primary compact" disabled={busy === identity.id} onClick={() => void validateIdentity(identity.id)}>{busy === identity.id ? "Submitting…" : "Validate DID"}</button></article>)}</div>
      {loaded && identities.length === 0 && <section className="panel"><Empty text="No DID submissions are waiting for validation." /></section>}
    </section>
    <section className="queue-section"><div className="section-heading"><div><p className="eyebrow">Asset queue</p><h3>Registration validation</h3></div><span>{assets.length} waiting</span></div>
      <div className="review-grid">{assets.map((asset) => <article className="panel review-card" key={asset.id}><div className="review-icon"><Boxes size={22} /></div><div className="review-content"><div><strong>{asset.name}</strong><Status value={asset.state} /></div><p>{asset.kind} · classification {asset.classification}</p><small className="mono">{asset.id}</small><small>{asset.token_id === null ? "Mint confirmation is still being indexed" : `Token ${asset.token_id} confirmed`}</small></div><button className="primary compact" disabled={busy === asset.id} onClick={() => void validateAsset(asset.id)}>{busy === asset.id ? "Verifying…" : "Validate & activate"}</button></article>)}</div>
      {loaded && assets.length === 0 && <section className="panel"><Empty text="No assets are waiting for validation." /></section>}
    </section>
  </Page>;
}

function WalletPage() {
  const wallet = useWallet();
  const [identity, setIdentity] = useState<IdentityRecord | null>(null);
  const [provision, setProvision] = useState<WalletProvisionStatus | null>(null);
  const [accessCode, setAccessCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    Promise.all([
      api.get<IdentityRecord>("/identities/me/"),
      api.get<WalletProvisionStatus>("/wallet-provision/"),
    ]).then(([identityResponse, provisionResponse]) => {
      setIdentity(identityResponse.data);
      setProvision(provisionResponse.data);
    }).catch((value) => setError(errorMessage(value)));
  }, []);
  const addressMatches = Boolean(wallet.address && identity?.controller_address && wallet.address.toLowerCase() === identity.controller_address.toLowerCase());
  async function claim(event: FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      const response = await api.post<WalletProvisionClaim>("/wallet-provision/", { access_code: accessCode });
      await wallet.installProvisionedWallet(response.data.encrypted_wallet, accessCode);
      setProvision({ issued: true, claimed: true, controller_address: response.data.controller_address });
      setAccessCode("");
    } catch (value) { setError(errorMessage(value)); } finally { setBusy(false); }
  }
  async function unlock(event: FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try { await wallet.unlock(accessCode); setAccessCode(""); } catch (value) { setError(errorMessage(value)); } finally { setBusy(false); }
  }
  return <Page title="ChainControl Wallet" subtitle="Controller wallets are issued exclusively by Django administration.">
    <div className="wallet-layout">
      <section className="panel wallet-card"><div className="wallet-orb"><KeyRound size={30} /></div><div><p className="eyebrow">Organization-issued encrypted vault</p><h3>{wallet.address ?? provision?.controller_address ?? "Awaiting administration"}</h3><p className="muted">{wallet.configured ? wallet.unlocked ? "Unlocked for this session" : "Locked" : provision?.issued ? "Enter the one-time code issued by Django administration." : "Django administration has not issued a controller wallet for this account."}</p></div>{wallet.configured && <Status value={wallet.unlocked ? "UNLOCKED" : "LOCKED"} />}</section>
      {identity && <section className={`panel controller-check ${addressMatches ? "match" : "mismatch"}`}><div>{addressMatches ? <CheckCircle2 /> : <AlertTriangle />}</div><span><strong>{addressMatches ? "Controller verified" : "Controller unavailable"}</strong><small>Identity controller: <span className="mono">{identity.controller_address}</span></small></span></section>}
    </div>
    {error && <div className="error"><AlertTriangle size={16} />{error}</div>}
    {!wallet.configured && provision?.issued && !provision.claimed && <section className="panel wallet-setup"><div><p className="eyebrow">Administrative provisioning</p><h3>Claim the issued controller wallet</h3><p className="muted">Enter the one-time access code provided by Django administration. Users and validators cannot create, import, or replace controller keys.</p></div><form onSubmit={claim} autoComplete="off"><label>Wallet access code<input type="password" value={accessCode} onChange={(event) => setAccessCode(event.target.value)} autoComplete="new-password" minLength={12} required /></label><button className="primary compact" disabled={busy}>{busy ? "Claiming…" : "Claim admin-issued wallet"}</button></form><p className="wallet-note"><LockKeyhole size={15} />The server returns only an encrypted keystore after validating the one-time code.</p></section>}
    {!wallet.configured && provision && !provision.issued && <section className="panel wallet-setup"><div><p className="eyebrow">Administrative action required</p><h3>No controller wallet has been issued</h3><p className="muted">Contact Django administration. This account cannot generate or import its own controller key.</p></div></section>}
    {!wallet.configured && provision?.claimed && <section className="panel wallet-setup"><div><p className="eyebrow">Reissue required</p><h3>The issued wallet was already claimed</h3><p className="muted">This browser does not have the encrypted wallet. Ask Django administration to reissue a new one-time access code.</p></div></section>}
    {wallet.configured && !wallet.unlocked && <form className="panel wallet-unlock" onSubmit={unlock} autoComplete="off"><div><p className="eyebrow">Unlock vault</p><h3>Authorize DID signatures</h3><p className="muted">Use the wallet access code supplied by Django administration.</p></div><label>Wallet access code<input type="password" value={accessCode} onChange={(event) => setAccessCode(event.target.value)} autoComplete="current-password" required /></label><button className="primary compact" disabled={busy}>{busy ? "Decrypting…" : "Unlock admin-issued wallet"}</button></form>}
    {wallet.configured && wallet.unlocked && <section className="panel wallet-actions"><div><p className="eyebrow">Session controls</p><h3>Wallet is ready to sign</h3><p className="muted">Every sensitive action still creates a one-time, purpose-bound DID challenge.</p></div><button className="secondary compact" onClick={wallet.lock}><LockKeyhole size={15} />Lock now</button></section>}
  </Page>;
}

function ValidatorRoute() {
  const user = useAuth((state) => state.user)!;
  return user.roles.includes("VALIDATOR") ? <ValidatorWorkspace /> : <Navigate to="/" replace />;
}

function GenericList({ title, subtitle, endpoint }: { title: string; subtitle: string; endpoint: string }) {
  const [items, setItems] = useState<any[]>([]); const [loaded, setLoaded] = useState(false);
  useEffect(() => { api.get(endpoint).then((r) => setItems(r.data.results ?? r.data)).finally(() => setLoaded(true)); }, [endpoint]);
  return <Page title={title} subtitle={subtitle}><section className="panel event-list">{items.map((item) => <div key={item.id}><Status value={item.severity ?? item.state ?? item.outcome ?? "RECORDED"} /><span><strong>{item.title ?? item.action ?? item.id}</strong><small>{item.created_at ? formatIstDateTime(item.created_at) : ""}</small></span></div>)}{loaded && items.length === 0 && <Empty text="No records in your current scope." />}</section></Page>;
}

function NetworkPage() {
  const [health, setHealth] = useState<NetworkHealth | null>(null);
  useEffect(() => { api.get("/blockchain/health/").then((r) => setHealth(r.data)); }, []);
  return <Page title="Blockchain health" subtitle="Live RPC checks across the four validators maintaining one QBFT ledger."><div className="validator-grid">{health?.validators.map((v) => <article className="panel validator" key={v.validator}><div className={v.healthy ? "node healthy" : "node"}><Network /></div><span>Validator {v.validator}</span><strong>{v.healthy ? "Operational" : "Unavailable"}</strong><small>Block {v.block_height ?? "—"}</small></article>) ?? <Empty text="Checking validator health…" />}</div></Page>;
}

function Page({ title, subtitle, action, children }: { title: string; subtitle: string; action?: ReactNode; children: ReactNode }) {
  return <main className="page"><div className="page-title"><div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>{children}</main>;
}
function Status({ value }: { value: string }) { return <span className={`badge ${value.toLowerCase().replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>; }
function Empty({ text }: { text: string }) { return <div className="empty"><Boxes size={26} /><p>{text}</p></div>; }

export default function App() {
  const user = useAuth((s) => s.user);
  if (!user) return <Login />;
  return <Shell><Routes><Route path="/" element={<Overview />} /><Route path="/identity" element={<Identity />} /><Route path="/assets" element={<Assets />} /><Route path="/validator" element={<ValidatorRoute />} /><Route path="/wallet" element={<WalletPage />} /><Route path="/transfers" element={<GenericList title="Transfers" subtitle="Recipient acceptance and scoped approval precede ledger execution." endpoint="/transfers/" />} /><Route path="/audit" element={<GenericList title="Audit trail" subtitle="Searchable operational evidence linked to immutable security events." endpoint="/audit/" />} /><Route path="/security" element={<GenericList title="Security alerts" subtitle="Integrity, authorization, and reconciliation findings." endpoint="/security-alerts/" />} /><Route path="/network" element={<NetworkPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes></Shell>;
}
