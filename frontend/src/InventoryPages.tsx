import { useEffect, useMemo, useState, type FormEvent } from "react";
import { AlertTriangle, CheckCircle2, PackageCheck, RefreshCw, Search, Send } from "lucide-react";

import api from "./api";
import { useAuth } from "./auth";
import { formatIstDateTime } from "./format";
import type { InventoryRequest, InventoryStock, Paginated } from "./types";
import { Empty, Page, Status, errorMessage } from "./ui";


export function InventoryPage() {
  const [stocks, setStocks] = useState<InventoryStock[]>([]);
  const [search, setSearch] = useState("");
  const [assetType, setAssetType] = useState("");
  const [selected, setSelected] = useState<InventoryStock | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setError("");
    try {
      const response = await api.get<Paginated<InventoryStock>>("/inventory/stocks/", { params: { search: search || undefined, asset_type: assetType || undefined } });
      setStocks(response.data.results);
    } catch (value) {
      setError(errorMessage(value));
    } finally {
      setLoaded(true);
    }
  };
  useEffect(() => { void load(); }, []);

  const totals = useMemo(() => ({
    available: stocks.reduce((sum, stock) => sum + stock.quantity_available, 0),
    reserved: stocks.reduce((sum, stock) => sum + stock.quantity_reserved, 0),
    issued: stocks.reduce((sum, stock) => sum + stock.quantity_issued, 0),
    low: stocks.filter((stock) => stock.low_stock).length,
  }), [stocks]);

  async function requestItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const form = new FormData(event.currentTarget);
      await api.post("/inventory/requests/", {
        stock: selected.id,
        quantity: Number(form.get("quantity")),
        reason: String(form.get("reason") ?? ""),
      });
      setNotice(`Request submitted for ${selected.sku}.`);
      setSelected(null);
    } catch (value) {
      setError(errorMessage(value));
    } finally {
      setBusy(false);
    }
  }

  const actions = <div className="inventory-filters">
    <div className="search-control"><Search size={15} /><input aria-label="Search inventory" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name or SKU" /></div>
    <select aria-label="Inventory type" value={assetType} onChange={(event) => setAssetType(event.target.value)}>
      <option value="">All inventory</option><option value="STOCK_ITEM">Stock items</option><option value="SOFTWARE_LICENSE">Software licenses</option><option value="UNIQUE_PHYSICAL_ASSET">Unique equipment</option><option value="DIGITAL_ASSET">Digital assets</option>
    </select>
    <button className="secondary compact" onClick={() => void load()}><RefreshCw size={14} />Apply</button>
  </div>;

  return <Page title="Inventory" subtitle="Browse real organization stock, availability, locations and requestable items." action={actions}>
    <div className="stats"><article className="stat"><span>Available</span><strong>{totals.available}</strong><small>requestable units</small></article><article className="stat"><span>Reserved</span><strong>{totals.reserved}</strong><small>approved requests</small></article><article className="stat"><span>Issued</span><strong>{totals.issued}</strong><small>currently allocated</small></article><article className="stat"><span>Low stock</span><strong>{totals.low}</strong><small>at or below threshold</small></article></div>
    {error && <div className="error"><AlertTriangle size={16} />{error}</div>}
    {notice && <div className="notice"><CheckCircle2 size={16} />{notice}</div>}
    {selected && <form className="panel inventory-request-form" onSubmit={requestItem}>
      <div><p className="eyebrow">Request inventory</p><h3>{selected.item_name}</h3><small className="mono">{selected.sku} · {selected.location_code}</small></div>
      <label>Quantity<input name="quantity" type="number" min="1" max={selected.quantity_available} defaultValue="1" required /></label>
      <label>Business reason<input name="reason" maxLength={2000} /></label>
      <button className="primary compact" disabled={busy}><Send size={14} />{busy ? "Submitting…" : "Submit request"}</button>
      <button className="secondary compact" type="button" onClick={() => setSelected(null)}>Cancel</button>
    </form>}
    <section className="panel table-wrap inventory-table"><table><thead><tr><th>Item</th><th>Category</th><th>Location</th><th>Available</th><th>Reserved</th><th>Issued</th><th>Status</th><th /></tr></thead><tbody>
      {stocks.map((stock) => <tr key={stock.id}><td><strong>{stock.item_name}</strong><small>{stock.variant_name} · <span className="mono">{stock.sku}</span></small></td><td>{stock.category}<small>{stock.asset_type.replaceAll("_", " ")}</small></td><td>{stock.location_name}<small>{stock.department_code ?? "Shared"}</small></td><td>{stock.quantity_available}</td><td>{stock.quantity_reserved}</td><td>{stock.quantity_issued}</td><td><Status value={stock.low_stock ? "LOW_STOCK" : stock.quantity_available ? "AVAILABLE" : "UNAVAILABLE"} /></td><td><button className="secondary compact" disabled={stock.quantity_available < 1} onClick={() => setSelected(stock)}>Request</button></td></tr>)}
    </tbody></table>{loaded && stocks.length === 0 && <Empty text="No inventory matches the current filters." />}</section>
  </Page>;
}


export function InventoryRequestsPage() {
  const user = useAuth((state) => state.user)!;
  const [requests, setRequests] = useState<InventoryRequest[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const canApprove = user.permissions.includes("inventory.request.approve");
  const canIssue = user.permissions.includes("inventory.issue");

  const load = async () => {
    setError("");
    try {
      const response = await api.get<Paginated<InventoryRequest>>("/inventory/requests/");
      setRequests(response.data.results);
    } catch (value) { setError(errorMessage(value)); } finally { setLoaded(true); }
  };
  useEffect(() => { void load(); }, []);

  async function act(item: InventoryRequest, action: "approve" | "reject" | "issue" | "return" | "cancel") {
    setBusy(item.id); setError(""); setNotice("");
    try {
      await api.post(`/inventory/requests/${item.id}/${action}/`, {});
      setNotice(`${item.sku} request updated.`);
      await load();
    } catch (value) { setError(errorMessage(value)); } finally { setBusy(null); }
  }

  return <Page title={canApprove || canIssue ? "Inventory requests" : "My requests"} subtitle="Track approval, reservation, issue and return without losing stock history." action={<button className="secondary compact" onClick={() => void load()}><RefreshCw size={14} />Refresh</button>}>
    {error && <div className="error"><AlertTriangle size={16} />{error}</div>}
    {notice && <div className="notice"><PackageCheck size={16} />{notice}</div>}
    <section className="request-grid">
      {requests.map((item) => <article className="panel request-card" key={item.id}>
        <div className="request-card-head"><div><p className="eyebrow">{item.sku}</p><h3>{item.item_name}</h3></div><Status value={item.status} /></div>
        <dl><div><dt>Quantity</dt><dd>{item.quantity}</dd></div><div><dt>Requester</dt><dd>{item.requested_by_username}</dd></div><div><dt>Location</dt><dd>{item.location_code}</dd></div><div><dt>Created</dt><dd>{formatIstDateTime(item.created_at)}</dd></div></dl>
        {item.reason && <p className="request-reason">{item.reason}</p>}
        <div className="request-actions">
          {canApprove && ["REQUESTED", "PENDING_APPROVAL"].includes(item.status) && <><button className="primary compact" disabled={busy === item.id} onClick={() => void act(item, "approve")}>Approve & reserve</button><button className="secondary compact" disabled={busy === item.id} onClick={() => void act(item, "reject")}>Reject</button></>}
          {canIssue && item.status === "RESERVED" && <button className="primary compact" disabled={busy === item.id} onClick={() => void act(item, "issue")}>Issue item</button>}
          {canIssue && item.status === "ISSUED" && <button className="secondary compact" disabled={busy === item.id} onClick={() => void act(item, "return")}>Record return</button>}
          {item.requested_by === user.id && ["REQUESTED", "PENDING_APPROVAL", "RESERVED"].includes(item.status) && <button className="secondary compact" disabled={busy === item.id} onClick={() => void act(item, "cancel")}>Cancel request</button>}
        </div>
      </article>)}
      {loaded && requests.length === 0 && <section className="panel"><Empty text="No inventory requests are visible in your scope." /></section>}
    </section>
  </Page>;
}
