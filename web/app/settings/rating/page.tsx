"use client";

import { useEffect, useState, useCallback } from "react";

const API = "http://localhost:8001/api/v1/rating";

// ------------------------------------------------------------------ //
// Types
// ------------------------------------------------------------------ //
interface RateCard {
  rate_card_id: string;
  carrier_id: string;
  carrier_name?: string;
  name: string;
  mode: string;
  currency: string;
  effective_date: string;
  expiry_date?: string;
  status: string;
  notes?: string;
  lane_count?: number;
}

interface Lane {
  lane_id: string;
  rate_card_id: string;
  lane_name: string;
  origin_type: string;
  origin_value?: string;
  destination_type: string;
  destination_value?: string;
  min_weight_kg?: number;
  max_weight_kg?: number;
  priority: number;
  is_active: boolean;
  rate_line_count?: number;
}

interface RateLine {
  rate_line_id: string;
  lane_id: string;
  charge_type: string;
  charge_code: string;
  description?: string;
  rate_amount: number;
  currency: string;
  uom?: string;
  min_charge?: number;
  max_charge?: number;
  is_active: boolean;
  sort_order: number;
}

interface FuelSurcharge {
  fsc_id: string;
  carrier_id: string;
  name: string;
  mode?: string;
  effective_date: string;
  expiry_date?: string;
  rate_type: string;
  rate_value: number;
  basis: string;
  is_active: boolean;
}

interface Accessorial {
  accessorial_id: string;
  carrier_id: string;
  charge_code: string;
  description: string;
  charge_type: string;
  rate_amount: number;
  currency: string;
  applies_to_modes: string[];
  is_active: boolean;
}

// ------------------------------------------------------------------ //
// Constants
// ------------------------------------------------------------------ //
const MODES = ["FTL", "LTL", "Parcel", "Rail", "Ocean", "Air", "Intermodal"];
const CHARGE_TYPES = [
  "base_flat", "per_mile", "per_km", "per_kg",
  "per_lb", "per_pallet", "per_carton", "minimum", "maximum",
];
const LOC_TYPES = ["any", "zip", "state", "country", "region"];
const RATE_TYPES = ["percentage", "per_mile", "per_km", "flat"];
const ACC_CHARGE_TYPES = ["flat", "per_unit", "percentage", "per_mile", "per_km"];

// ------------------------------------------------------------------ //
// Helpers
// ------------------------------------------------------------------ //
const badge = (color: string, text: string) => (
  <span className={`px-2 py-0.5 rounded text-xs font-medium ${color}`}>{text}</span>
);

const statusBadge = (s: string) => {
  const map: Record<string, string> = {
    active: "bg-green-100 text-green-700",
    inactive: "bg-gray-100 text-gray-600",
    expired: "bg-red-100 text-red-700",
  };
  return badge(map[s] || "bg-gray-100 text-gray-600", s);
};

// ------------------------------------------------------------------ //
// Main Page
// ------------------------------------------------------------------ //
type Tab = "rate-cards" | "fuel-surcharges" | "accessorials";

export default function RatingPage() {
  const [activeTab, setActiveTab] = useState<Tab>("rate-cards");
  const [selectedCard, setSelectedCard] = useState<RateCard | null>(null);
  const [selectedLane, setSelectedLane] = useState<Lane | null>(null);

  const tabs: { id: Tab; label: string }[] = [
    { id: "rate-cards", label: "Rate Cards & Lanes" },
    { id: "fuel-surcharges", label: "Fuel Surcharges" },
    { id: "accessorials", label: "Accessorials" },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Rating & Cost Calculation</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage carrier rate cards, lane structures, rate lines, fuel surcharges, and accessorial charges.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => { setActiveTab(t.id); setSelectedCard(null); setSelectedLane(null); }}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${
              activeTab === t.id
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === "rate-cards" && (
        <RateCardsTab
          selectedCard={selectedCard}
          setSelectedCard={setSelectedCard}
          selectedLane={selectedLane}
          setSelectedLane={setSelectedLane}
        />
      )}
      {activeTab === "fuel-surcharges" && <FuelSurchargesTab />}
      {activeTab === "accessorials" && <AccessorialsTab />}
    </div>
  );
}

// ------------------------------------------------------------------ //
// Rate Cards Tab (3-pane: cards → lanes → rate lines)
// ------------------------------------------------------------------ //
function RateCardsTab({
  selectedCard, setSelectedCard, selectedLane, setSelectedLane,
}: {
  selectedCard: RateCard | null;
  setSelectedCard: (c: RateCard | null) => void;
  selectedLane: Lane | null;
  setSelectedLane: (l: Lane | null) => void;
}) {
  const [cards, setCards] = useState<RateCard[]>([]);
  const [lanes, setLanes] = useState<Lane[]>([]);
  const [rateLines, setRateLines] = useState<RateLine[]>([]);
  const [loading, setLoading] = useState(false);
  const [showCardModal, setShowCardModal] = useState(false);
  const [showLaneModal, setShowLaneModal] = useState(false);
  const [showLineModal, setShowLineModal] = useState(false);
  const [editingCard, setEditingCard] = useState<RateCard | null>(null);
  const [editingLane, setEditingLane] = useState<Lane | null>(null);
  const [editingLine, setEditingLine] = useState<RateLine | null>(null);

  const EMPTY_CARD = { carrier_id: "", name: "", mode: "FTL", currency: "USD", effective_date: "", expiry_date: "", status: "active", notes: "" };
  const EMPTY_LANE = { rate_card_id: selectedCard?.rate_card_id || "", lane_name: "", origin_type: "any", origin_value: "", destination_type: "any", destination_value: "", min_weight_kg: "", max_weight_kg: "", priority: 0, is_active: true };
  const EMPTY_LINE = { lane_id: selectedLane?.lane_id || "", charge_type: "base_flat", charge_code: "LINEHAUL", description: "", rate_amount: "", currency: "USD", uom: "", min_charge: "", max_charge: "", is_active: true, sort_order: 0 };

  const [cardForm, setCardForm] = useState<Record<string, unknown>>(EMPTY_CARD);
  const [laneForm, setLaneForm] = useState<Record<string, unknown>>(EMPTY_LANE);
  const [lineForm, setLineForm] = useState<Record<string, unknown>>(EMPTY_LINE);

  const fetchCards = useCallback(async () => {
    setLoading(true);
    const r = await fetch(`${API}/rate-cards`);
    const data = await r.json();
    setCards(Array.isArray(data) ? data : data.data ?? []);
    setLoading(false);
  }, []);

  const fetchLanes = useCallback(async (cardId: string) => {
    const r = await fetch(`${API}/rate-cards/${cardId}/lanes`);
    setLanes(await r.json());
    setRateLines([]);
    setSelectedLane(null);
  }, [setSelectedLane]);

  const fetchRateLines = useCallback(async (laneId: string) => {
    const r = await fetch(`${API}/lanes/${laneId}/rate-lines`);
    setRateLines(await r.json());
  }, []);

  useEffect(() => { fetchCards(); }, [fetchCards]);
  useEffect(() => { if (selectedCard) fetchLanes(selectedCard.rate_card_id); }, [selectedCard, fetchLanes]);
  useEffect(() => { if (selectedLane) fetchRateLines(selectedLane.lane_id); }, [selectedLane, fetchRateLines]);

  async function saveCard() {
    const url = editingCard ? `${API}/rate-cards/${editingCard.rate_card_id}` : `${API}/rate-cards`;
    const method = editingCard ? "PATCH" : "POST";
    await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(cardForm) });
    setShowCardModal(false);
    fetchCards();
  }

  async function saveLane() {
    const body = { ...laneForm, rate_card_id: selectedCard?.rate_card_id };
    const url = editingLane ? `${API}/lanes/${editingLane.lane_id}` : `${API}/lanes`;
    const method = editingLane ? "PATCH" : "POST";
    await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    setShowLaneModal(false);
    if (selectedCard) fetchLanes(selectedCard.rate_card_id);
  }

  async function saveLine() {
    const body = { ...lineForm, lane_id: selectedLane?.lane_id };
    const url = editingLine ? `${API}/rate-lines/${editingLine.rate_line_id}` : `${API}/rate-lines`;
    const method = editingLine ? "PATCH" : "POST";
    await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    setShowLineModal(false);
    if (selectedLane) fetchRateLines(selectedLane.lane_id);
  }

  async function deleteCard(id: string) {
    if (!confirm("Delete this rate card and all its lanes?")) return;
    await fetch(`${API}/rate-cards/${id}`, { method: "DELETE" });
    setSelectedCard(null);
    fetchCards();
  }

  async function deleteLane(id: string) {
    if (!confirm("Delete this lane?")) return;
    await fetch(`${API}/lanes/${id}`, { method: "DELETE" });
    if (selectedCard) fetchLanes(selectedCard.rate_card_id);
  }

  async function deleteLine(id: string) {
    if (!confirm("Delete this rate line?")) return;
    await fetch(`${API}/rate-lines/${id}`, { method: "DELETE" });
    if (selectedLane) fetchRateLines(selectedLane.lane_id);
  }

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* Pane 1: Rate Cards */}
      <div className="col-span-4 bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
          <span className="text-sm font-semibold text-gray-700">Rate Cards</span>
          <button
            onClick={() => { setEditingCard(null); setCardForm(EMPTY_CARD); setShowCardModal(true); }}
            className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
          >+ Add</button>
        </div>
        {loading ? (
          <div className="p-4 text-center text-gray-400 text-sm">Loading…</div>
        ) : (
          <div className="divide-y divide-gray-100 max-h-[70vh] overflow-y-auto">
            {cards.map((card) => (
              <div
                key={card.rate_card_id}
                onClick={() => setSelectedCard(card)}
                className={`px-4 py-3 cursor-pointer hover:bg-blue-50 transition ${selectedCard?.rate_card_id === card.rate_card_id ? "bg-blue-50 border-l-2 border-blue-500" : ""}`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{card.name}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{card.carrier_name || "—"}</p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded font-medium">{card.mode}</span>
                    {statusBadge(card.status)}
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-xs text-gray-400">{card.effective_date?.slice(0, 10)} → {card.expiry_date?.slice(0, 10) || "open"}</span>
                  <span className="text-xs text-gray-400">·</span>
                  <span className="text-xs text-gray-400">{card.lane_count ?? 0} lanes</span>
                </div>
                <div className="flex gap-1 mt-1.5">
                  <button onClick={(e) => { e.stopPropagation(); setEditingCard(card); setCardForm({ ...card }); setShowCardModal(true); }} className="text-xs text-blue-600 hover:underline">Edit</button>
                  <button onClick={(e) => { e.stopPropagation(); deleteCard(card.rate_card_id); }} className="text-xs text-red-500 hover:underline">Delete</button>
                </div>
              </div>
            ))}
            {cards.length === 0 && <div className="p-4 text-center text-gray-400 text-sm">No rate cards yet.</div>}
          </div>
        )}
      </div>

      {/* Pane 2: Lanes */}
      <div className="col-span-4 bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
          <span className="text-sm font-semibold text-gray-700">
            Lanes {selectedCard ? `— ${selectedCard.name}` : ""}
          </span>
          {selectedCard && (
            <button
              onClick={() => { setEditingLane(null); setLaneForm({ ...EMPTY_LANE, rate_card_id: selectedCard.rate_card_id }); setShowLaneModal(true); }}
              className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
            >+ Add</button>
          )}
        </div>
        <div className="divide-y divide-gray-100 max-h-[70vh] overflow-y-auto">
          {!selectedCard && <div className="p-4 text-center text-gray-400 text-sm">Select a rate card.</div>}
          {selectedCard && lanes.length === 0 && <div className="p-4 text-center text-gray-400 text-sm">No lanes. Add one.</div>}
          {lanes.map((lane) => (
            <div
              key={lane.lane_id}
              onClick={() => setSelectedLane(lane)}
              className={`px-4 py-3 cursor-pointer hover:bg-blue-50 transition ${selectedLane?.lane_id === lane.lane_id ? "bg-blue-50 border-l-2 border-blue-500" : ""}`}
            >
              <div className="flex items-start justify-between">
                <p className="text-sm font-medium text-gray-800">{lane.lane_name}</p>
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">P:{lane.priority}</span>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                {lane.origin_type === "any" ? "Any Origin" : `${lane.origin_type}: ${lane.origin_value}`}
                {" → "}
                {lane.destination_type === "any" ? "Any Destination" : `${lane.destination_type}: ${lane.destination_value}`}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">{lane.rate_line_count ?? 0} rate lines</p>
              <div className="flex gap-1 mt-1">
                <button onClick={(e) => { e.stopPropagation(); setEditingLane(lane); setLaneForm({ ...lane }); setShowLaneModal(true); }} className="text-xs text-blue-600 hover:underline">Edit</button>
                <button onClick={(e) => { e.stopPropagation(); deleteLane(lane.lane_id); }} className="text-xs text-red-500 hover:underline">Delete</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Pane 3: Rate Lines */}
      <div className="col-span-4 bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
          <span className="text-sm font-semibold text-gray-700">
            Rate Lines {selectedLane ? `— ${selectedLane.lane_name}` : ""}
          </span>
          {selectedLane && (
            <button
              onClick={() => { setEditingLine(null); setLineForm({ ...EMPTY_LINE, lane_id: selectedLane.lane_id }); setShowLineModal(true); }}
              className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
            >+ Add</button>
          )}
        </div>
        <div className="divide-y divide-gray-100 max-h-[70vh] overflow-y-auto">
          {!selectedLane && <div className="p-4 text-center text-gray-400 text-sm">Select a lane.</div>}
          {selectedLane && rateLines.length === 0 && <div className="p-4 text-center text-gray-400 text-sm">No rate lines. Add one.</div>}
          {rateLines.map((line) => (
            <div key={line.rate_line_id} className="px-4 py-3">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-800">{line.charge_code}</p>
                  <p className="text-xs text-gray-500">{line.description || line.charge_type}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-gray-800">
                    {line.currency} {Number(line.rate_amount).toFixed(4)}
                    {line.uom ? ` / ${line.uom}` : ""}
                  </p>
                  <span className="text-xs bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded">{line.charge_type}</span>
                </div>
              </div>
              {(line.min_charge || line.max_charge) && (
                <p className="text-xs text-gray-400 mt-0.5">
                  {line.min_charge ? `Min: ${line.min_charge}` : ""}
                  {line.min_charge && line.max_charge ? " · " : ""}
                  {line.max_charge ? `Max: ${line.max_charge}` : ""}
                </p>
              )}
              <div className="flex gap-1 mt-1">
                <button onClick={() => { setEditingLine(line); setLineForm({ ...line }); setShowLineModal(true); }} className="text-xs text-blue-600 hover:underline">Edit</button>
                <button onClick={() => deleteLine(line.rate_line_id)} className="text-xs text-red-500 hover:underline">Delete</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Rate Card Modal */}
      {showCardModal && (
        <Modal title={editingCard ? "Edit Rate Card" : "New Rate Card"} onClose={() => setShowCardModal(false)} onSave={saveCard}>
          <Field label="Name"><input className={inp} value={String(cardForm.name || "")} onChange={e => setCardForm({ ...cardForm, name: e.target.value })} /></Field>
          <Field label="Carrier ID"><input className={inp} value={String(cardForm.carrier_id || "")} onChange={e => setCardForm({ ...cardForm, carrier_id: e.target.value })} placeholder="UUID" /></Field>
          <Field label="Mode">
            <select className={inp} value={String(cardForm.mode || "")} onChange={e => setCardForm({ ...cardForm, mode: e.target.value })}>
              {MODES.map(m => <option key={m}>{m}</option>)}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Effective Date"><input type="date" className={inp} value={String(cardForm.effective_date || "").slice(0,10)} onChange={e => setCardForm({ ...cardForm, effective_date: e.target.value })} /></Field>
            <Field label="Expiry Date"><input type="date" className={inp} value={String(cardForm.expiry_date || "").slice(0,10)} onChange={e => setCardForm({ ...cardForm, expiry_date: e.target.value })} /></Field>
          </div>
          <Field label="Currency"><input className={inp} value={String(cardForm.currency || "")} onChange={e => setCardForm({ ...cardForm, currency: e.target.value })} /></Field>
          <Field label="Status">
            <select className={inp} value={String(cardForm.status || "")} onChange={e => setCardForm({ ...cardForm, status: e.target.value })}>
              {["active","inactive","expired"].map(s => <option key={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Notes"><textarea className={inp} rows={2} value={String(cardForm.notes || "")} onChange={e => setCardForm({ ...cardForm, notes: e.target.value })} /></Field>
        </Modal>
      )}

      {/* Lane Modal */}
      {showLaneModal && (
        <Modal title={editingLane ? "Edit Lane" : "New Lane"} onClose={() => setShowLaneModal(false)} onSave={saveLane}>
          <Field label="Lane Name"><input className={inp} value={String(laneForm.lane_name || "")} onChange={e => setLaneForm({ ...laneForm, lane_name: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Origin Type">
              <select className={inp} value={String(laneForm.origin_type || "")} onChange={e => setLaneForm({ ...laneForm, origin_type: e.target.value })}>
                {LOC_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Origin Value"><input className={inp} value={String(laneForm.origin_value || "")} onChange={e => setLaneForm({ ...laneForm, origin_value: e.target.value })} placeholder="e.g. ON, M5V, CA" /></Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Destination Type">
              <select className={inp} value={String(laneForm.destination_type || "")} onChange={e => setLaneForm({ ...laneForm, destination_type: e.target.value })}>
                {LOC_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Destination Value"><input className={inp} value={String(laneForm.destination_value || "")} onChange={e => setLaneForm({ ...laneForm, destination_value: e.target.value })} placeholder="e.g. NY, 10001, US" /></Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Min Weight (kg)"><input type="number" className={inp} value={String(laneForm.min_weight_kg || "")} onChange={e => setLaneForm({ ...laneForm, min_weight_kg: e.target.value })} /></Field>
            <Field label="Max Weight (kg)"><input type="number" className={inp} value={String(laneForm.max_weight_kg || "")} onChange={e => setLaneForm({ ...laneForm, max_weight_kg: e.target.value })} /></Field>
          </div>
          <Field label="Priority (higher = more specific)"><input type="number" className={inp} value={String(laneForm.priority || 0)} onChange={e => setLaneForm({ ...laneForm, priority: Number(e.target.value) })} /></Field>
          <Toggle label="Active" checked={Boolean(laneForm.is_active)} onChange={v => setLaneForm({ ...laneForm, is_active: v })} />
        </Modal>
      )}

      {/* Rate Line Modal */}
      {showLineModal && (
        <Modal title={editingLine ? "Edit Rate Line" : "New Rate Line"} onClose={() => setShowLineModal(false)} onSave={saveLine}>
          <Field label="Charge Type">
            <select className={inp} value={String(lineForm.charge_type || "")} onChange={e => setLineForm({ ...lineForm, charge_type: e.target.value })}>
              {CHARGE_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Charge Code"><input className={inp} value={String(lineForm.charge_code || "")} onChange={e => setLineForm({ ...lineForm, charge_code: e.target.value })} /></Field>
            <Field label="UOM"><input className={inp} value={String(lineForm.uom || "")} onChange={e => setLineForm({ ...lineForm, uom: e.target.value })} placeholder="km, mi, kg, lb…" /></Field>
          </div>
          <Field label="Description"><input className={inp} value={String(lineForm.description || "")} onChange={e => setLineForm({ ...lineForm, description: e.target.value })} /></Field>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Rate Amount"><input type="number" step="0.0001" className={inp} value={String(lineForm.rate_amount || "")} onChange={e => setLineForm({ ...lineForm, rate_amount: e.target.value })} /></Field>
            <Field label="Min Charge"><input type="number" className={inp} value={String(lineForm.min_charge || "")} onChange={e => setLineForm({ ...lineForm, min_charge: e.target.value })} /></Field>
            <Field label="Max Charge"><input type="number" className={inp} value={String(lineForm.max_charge || "")} onChange={e => setLineForm({ ...lineForm, max_charge: e.target.value })} /></Field>
          </div>
          <Field label="Sort Order"><input type="number" className={inp} value={String(lineForm.sort_order || 0)} onChange={e => setLineForm({ ...lineForm, sort_order: Number(e.target.value) })} /></Field>
          <Toggle label="Active" checked={Boolean(lineForm.is_active)} onChange={v => setLineForm({ ...lineForm, is_active: v })} />
        </Modal>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ //
// Fuel Surcharges Tab
// ------------------------------------------------------------------ //
function FuelSurchargesTab() {
  const [rows, setRows] = useState<FuelSurcharge[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<FuelSurcharge | null>(null);
  const EMPTY = { carrier_id: "", name: "", mode: "", effective_date: "", expiry_date: "", rate_type: "percentage", rate_value: "", basis: "linehaul", is_active: true };
  const [form, setForm] = useState<Record<string, unknown>>(EMPTY);

  const fetch_ = async () => { const r = await fetch(`${API}/fuel-surcharges`); setRows(await r.json()); };
  useEffect(() => { fetch_(); }, []);

  const save = async () => {
    const url = editing ? `${API}/fuel-surcharges/${editing.fsc_id}` : `${API}/fuel-surcharges`;
    await fetch(url, { method: editing ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    setShowModal(false); fetch_();
  };
  const del = async (id: string) => { if (!confirm("Delete?")) return; await fetch(`${API}/fuel-surcharges/${id}`, { method: "DELETE" }); fetch_(); };

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
        <span className="text-sm font-semibold text-gray-700">Fuel Surcharge Schedules</span>
        <button onClick={() => { setEditing(null); setForm(EMPTY); setShowModal(true); }} className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700">+ Add Schedule</button>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            {["Name","Mode","Rate Type","Rate","Basis","Effective","Expiry","Active",""].map(h => (
              <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-gray-600">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map(row => (
            <tr key={row.fsc_id} className="hover:bg-gray-50">
              <td className="px-4 py-2.5 font-medium text-gray-800">{row.name}</td>
              <td className="px-4 py-2.5 text-gray-600">{row.mode || "All"}</td>
              <td className="px-4 py-2.5"><span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded">{row.rate_type}</span></td>
              <td className="px-4 py-2.5 font-mono text-gray-800">{row.rate_value}{row.rate_type === "percentage" ? "%" : ""}</td>
              <td className="px-4 py-2.5 text-gray-600">{row.basis}</td>
              <td className="px-4 py-2.5 text-gray-500 text-xs">{row.effective_date?.slice(0,10)}</td>
              <td className="px-4 py-2.5 text-gray-500 text-xs">{row.expiry_date?.slice(0,10) || "open"}</td>
              <td className="px-4 py-2.5">{row.is_active ? badge("bg-green-100 text-green-700","Yes") : badge("bg-gray-100 text-gray-500","No")}</td>
              <td className="px-4 py-2.5">
                <div className="flex gap-2">
                  <button onClick={() => { setEditing(row); setForm({ ...row }); setShowModal(true); }} className="text-xs text-blue-600 hover:underline">Edit</button>
                  <button onClick={() => del(row.fsc_id)} className="text-xs text-red-500 hover:underline">Delete</button>
                </div>
              </td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={9} className="text-center py-8 text-gray-400 text-sm">No fuel surcharge schedules.</td></tr>}
        </tbody>
      </table>
      {showModal && (
        <Modal title={editing ? "Edit Schedule" : "New Schedule"} onClose={() => setShowModal(false)} onSave={save}>
          <Field label="Name"><input className={inp} value={String(form.name || "")} onChange={e => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Carrier ID"><input className={inp} value={String(form.carrier_id || "")} onChange={e => setForm({ ...form, carrier_id: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Mode (blank = all)">
              <select className={inp} value={String(form.mode || "")} onChange={e => setForm({ ...form, mode: e.target.value })}>
                <option value="">All Modes</option>
                {MODES.map(m => <option key={m}>{m}</option>)}
              </select>
            </Field>
            <Field label="Basis">
              <select className={inp} value={String(form.basis || "")} onChange={e => setForm({ ...form, basis: e.target.value })}>
                {["linehaul","gross","distance"].map(b => <option key={b}>{b}</option>)}
              </select>
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Rate Type">
              <select className={inp} value={String(form.rate_type || "")} onChange={e => setForm({ ...form, rate_type: e.target.value })}>
                {RATE_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Rate Value"><input type="number" step="0.01" className={inp} value={String(form.rate_value || "")} onChange={e => setForm({ ...form, rate_value: e.target.value })} /></Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Effective Date"><input type="date" className={inp} value={String(form.effective_date || "").slice(0,10)} onChange={e => setForm({ ...form, effective_date: e.target.value })} /></Field>
            <Field label="Expiry Date"><input type="date" className={inp} value={String(form.expiry_date || "").slice(0,10)} onChange={e => setForm({ ...form, expiry_date: e.target.value })} /></Field>
          </div>
          <Toggle label="Active" checked={Boolean(form.is_active)} onChange={v => setForm({ ...form, is_active: v })} />
        </Modal>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ //
// Accessorials Tab
// ------------------------------------------------------------------ //
function AccessorialsTab() {
  const [rows, setRows] = useState<Accessorial[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Accessorial | null>(null);
  const EMPTY = { carrier_id: "", charge_code: "", description: "", charge_type: "flat", rate_amount: "", currency: "USD", applies_to_modes: ["FTL","LTL","Parcel"], is_active: true };
  const [form, setForm] = useState<Record<string, unknown>>(EMPTY);

  const fetch_ = async () => { const r = await fetch(`${API}/accessorials`); setRows(await r.json()); };
  useEffect(() => { fetch_(); }, []);

  const save = async () => {
    const url = editing ? `${API}/accessorials/${editing.accessorial_id}` : `${API}/accessorials`;
    await fetch(url, { method: editing ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
    setShowModal(false); fetch_();
  };
  const del = async (id: string) => { if (!confirm("Delete?")) return; await fetch(`${API}/accessorials/${id}`, { method: "DELETE" }); fetch_(); };

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
        <span className="text-sm font-semibold text-gray-700">Accessorial Charges</span>
        <button onClick={() => { setEditing(null); setForm(EMPTY); setShowModal(true); }} className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700">+ Add Accessorial</button>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            {["Code","Description","Type","Rate","Modes","Active",""].map(h => (
              <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-gray-600">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map(row => (
            <tr key={row.accessorial_id} className="hover:bg-gray-50">
              <td className="px-4 py-2.5 font-mono font-medium text-gray-800">{row.charge_code}</td>
              <td className="px-4 py-2.5 text-gray-700">{row.description}</td>
              <td className="px-4 py-2.5"><span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded">{row.charge_type}</span></td>
              <td className="px-4 py-2.5 font-mono text-gray-800">{row.currency} {Number(row.rate_amount).toFixed(2)}</td>
              <td className="px-4 py-2.5 text-gray-500 text-xs">{(row.applies_to_modes || []).join(", ")}</td>
              <td className="px-4 py-2.5">{row.is_active ? badge("bg-green-100 text-green-700","Yes") : badge("bg-gray-100 text-gray-500","No")}</td>
              <td className="px-4 py-2.5">
                <div className="flex gap-2">
                  <button onClick={() => { setEditing(row); setForm({ ...row }); setShowModal(true); }} className="text-xs text-blue-600 hover:underline">Edit</button>
                  <button onClick={() => del(row.accessorial_id)} className="text-xs text-red-500 hover:underline">Delete</button>
                </div>
              </td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-gray-400 text-sm">No accessorial charges.</td></tr>}
        </tbody>
      </table>
      {showModal && (
        <Modal title={editing ? "Edit Accessorial" : "New Accessorial"} onClose={() => setShowModal(false)} onSave={save}>
          <Field label="Carrier ID"><input className={inp} value={String(form.carrier_id || "")} onChange={e => setForm({ ...form, carrier_id: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Charge Code"><input className={inp} value={String(form.charge_code || "")} onChange={e => setForm({ ...form, charge_code: e.target.value })} /></Field>
            <Field label="Charge Type">
              <select className={inp} value={String(form.charge_type || "")} onChange={e => setForm({ ...form, charge_type: e.target.value })}>
                {ACC_CHARGE_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
            </Field>
          </div>
          <Field label="Description"><input className={inp} value={String(form.description || "")} onChange={e => setForm({ ...form, description: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Rate Amount"><input type="number" step="0.01" className={inp} value={String(form.rate_amount || "")} onChange={e => setForm({ ...form, rate_amount: e.target.value })} /></Field>
            <Field label="Currency"><input className={inp} value={String(form.currency || "")} onChange={e => setForm({ ...form, currency: e.target.value })} /></Field>
          </div>
          <Toggle label="Active" checked={Boolean(form.is_active)} onChange={v => setForm({ ...form, is_active: v })} />
        </Modal>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ //
// Shared UI primitives
// ------------------------------------------------------------------ //
const inp = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center gap-3">
      <button
        onClick={() => onChange(!checked)}
        className={`w-10 h-5 rounded-full transition-colors ${checked ? "bg-blue-500" : "bg-gray-300"}`}
      >
        <span className={`block w-4 h-4 bg-white rounded-full shadow transform transition-transform mx-0.5 ${checked ? "translate-x-5" : "translate-x-0"}`} />
      </button>
      <span className="text-sm text-gray-600">{label}</span>
    </div>
  );
}

function Modal({ title, onClose, onSave, children }: { title: string; onClose: () => void; onSave: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
        </div>
        <div className="px-6 py-4 space-y-4">{children}</div>
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 font-medium">Cancel</button>
          <button onClick={onSave} className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700">Save</button>
        </div>
      </div>
    </div>
  );
}
