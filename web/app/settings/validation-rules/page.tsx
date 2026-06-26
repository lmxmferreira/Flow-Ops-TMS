"use client";

import { useEffect, useState } from "react";

// ------------------------------------------------------------------ //
// Types
// ------------------------------------------------------------------ //
type TransactionType = "purchase_order" | "order_release" | "shipment";
type RuleType = "required" | "default_value" | "allowed_values" | "min_value" | "max_value" | "regex" | "custom";
type Severity = "error" | "warning";

interface ValidationRule {
  id: number;
  transaction_type: TransactionType;
  field_name: string;
  rule_type: RuleType;
  parameters: Record<string, unknown>;
  error_message: string;
  severity: Severity;
  is_active: boolean;
  sort_order: number;
  rule_set_id: number | null;
}

const API = "http://localhost:8001/api/v1/validation-rules";

const TX_LABELS: Record<TransactionType, string> = {
  purchase_order: "Purchase Orders",
  order_release: "Order Releases",
  shipment: "Shipments",
};

const RULE_TYPE_LABELS: Record<RuleType, string> = {
  required: "Required",
  default_value: "Default Value",
  allowed_values: "Allowed Values",
  min_value: "Min Value",
  max_value: "Max Value",
  regex: "Regex",
  custom: "Custom",
};

const TX_TYPES: TransactionType[] = ["purchase_order", "order_release", "shipment"];

const EMPTY_RULE: Omit<ValidationRule, "id"> = {
  transaction_type: "purchase_order",
  field_name: "",
  rule_type: "required",
  parameters: {},
  error_message: "",
  severity: "error",
  is_active: true,
  sort_order: 0,
  rule_set_id: null,
};

// ------------------------------------------------------------------ //
// Component
// ------------------------------------------------------------------ //
export default function ValidationRulesPage() {
  const [rules, setRules] = useState<ValidationRule[]>([]);
  const [activeTx, setActiveTx] = useState<TransactionType>("purchase_order");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<ValidationRule | null>(null);
  const [form, setForm] = useState(EMPTY_RULE);
  const [saving, setSaving] = useState(false);
  const [paramText, setParamText] = useState("{}");
  const [paramError, setParamError] = useState<string | null>(null);
  const [activeOnly, setActiveOnly] = useState(false);

  useEffect(() => {
    fetchRules();
  }, [activeOnly]);

  async function fetchRules() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}?active_only=${activeOnly}`);
      if (!res.ok) throw new Error("Failed to load rules");
      setRules(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  function openCreate() {
    setEditing(null);
    setForm({ ...EMPTY_RULE, transaction_type: activeTx });
    setParamText("{}");
    setParamError(null);
    setShowModal(true);
  }

  function openEdit(rule: ValidationRule) {
    setEditing(rule);
    setForm({ ...rule });
    setParamText(JSON.stringify(rule.parameters, null, 2));
    setParamError(null);
    setShowModal(true);
  }

  function handleParamChange(val: string) {
    setParamText(val);
    try {
      JSON.parse(val);
      setParamError(null);
    } catch {
      setParamError("Invalid JSON");
    }
  }

  async function handleSave() {
    if (paramError) return;
    setSaving(true);
    try {
      const body = { ...form, parameters: JSON.parse(paramText) };
      const url = editing ? `${API}/${editing.id}` : API;
      const method = editing ? "PATCH" : "POST";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const detail = await res.json();
        throw new Error(detail?.detail ?? "Save failed");
      }
      setShowModal(false);
      await fetchRules();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(rule: ValidationRule) {
    await fetch(`${API}/${rule.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !rule.is_active }),
    });
    await fetchRules();
  }

  async function handleDelete(rule: ValidationRule) {
    if (!confirm(`Delete rule for "${rule.field_name}"?`)) return;
    await fetch(`${API}/${rule.id}`, { method: "DELETE" });
    await fetchRules();
  }

  const displayed = rules.filter((r) => r.transaction_type === activeTx);

  // ---------------------------------------------------------------- //
  // Render
  // ---------------------------------------------------------------- //
  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Validation Rules</h1>
          <p className="text-sm text-gray-500 mt-1">
            Configure mandatory fields, default values, and business rules by transaction type.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition"
        >
          + Add Rule
        </button>
      </div>

      {/* Transaction type tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        {TX_TYPES.map((tx) => {
          const count = rules.filter((r) => r.transaction_type === tx).length;
          return (
            <button
              key={tx}
              onClick={() => setActiveTx(tx)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition -mb-px ${
                activeTx === tx
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {TX_LABELS[tx]}
              <span className="ml-2 text-xs bg-gray-100 text-gray-600 rounded-full px-2 py-0.5">
                {count}
              </span>
            </button>
          );
        })}
        <div className="ml-auto flex items-center gap-2 pb-2">
          <label className="flex items-center gap-1.5 text-sm text-gray-500 cursor-pointer">
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={(e) => setActiveOnly(e.target.checked)}
              className="rounded"
            />
            Active only
          </label>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading rules…</div>
      ) : error ? (
        <div className="text-center py-12 text-red-500">{error}</div>
      ) : displayed.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          No rules configured for {TX_LABELS[activeTx]}.
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600 w-8">#</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Field</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Rule Type</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Parameters</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Error Message</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Severity</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Active</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {displayed
                .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
                .map((rule) => (
                  <tr key={rule.id} className={`hover:bg-gray-50 ${!rule.is_active ? "opacity-40" : ""}`}>
                    <td className="px-4 py-3 text-gray-400">{rule.sort_order}</td>
                    <td className="px-4 py-3 font-mono text-gray-800">{rule.field_name}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded text-xs font-medium">
                        {RULE_TYPE_LABELS[rule.rule_type]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs max-w-xs truncate">
                      {Object.keys(rule.parameters).length > 0
                        ? JSON.stringify(rule.parameters)
                        : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-600 max-w-xs truncate">{rule.error_message}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          rule.severity === "error"
                            ? "bg-red-50 text-red-700"
                            : "bg-yellow-50 text-yellow-700"
                        }`}
                      >
                        {rule.severity}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleActive(rule)}
                        className={`w-10 h-5 rounded-full transition-colors ${
                          rule.is_active ? "bg-blue-500" : "bg-gray-300"
                        }`}
                      >
                        <span
                          className={`block w-4 h-4 bg-white rounded-full shadow transform transition-transform mx-0.5 ${
                            rule.is_active ? "translate-x-5" : "translate-x-0"
                          }`}
                        />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button
                          onClick={() => openEdit(rule)}
                          className="text-blue-600 hover:text-blue-800 text-xs font-medium"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(rule)}
                          className="text-red-500 hover:text-red-700 text-xs font-medium"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">
                {editing ? "Edit Rule" : "New Rule"}
              </h2>
            </div>

            <div className="px-6 py-4 space-y-4">
              {/* Transaction type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Transaction Type</label>
                <select
                  value={form.transaction_type}
                  onChange={(e) => setForm({ ...form, transaction_type: e.target.value as TransactionType })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {TX_TYPES.map((tx) => (
                    <option key={tx} value={tx}>{TX_LABELS[tx]}</option>
                  ))}
                </select>
              </div>

              {/* Field name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Field Name</label>
                <input
                  type="text"
                  value={form.field_name}
                  onChange={(e) => setForm({ ...form, field_name: e.target.value })}
                  placeholder="e.g. supplier_id"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Rule type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Rule Type</label>
                <select
                  value={form.rule_type}
                  onChange={(e) => setForm({ ...form, rule_type: e.target.value as RuleType })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {Object.entries(RULE_TYPE_LABELS).map(([val, label]) => (
                    <option key={val} value={val}>{label}</option>
                  ))}
                </select>
              </div>

              {/* Parameters */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Parameters <span className="text-gray-400 font-normal">(JSON)</span>
                </label>
                <textarea
                  value={paramText}
                  onChange={(e) => handleParamChange(e.target.value)}
                  rows={3}
                  className={`w-full border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    paramError ? "border-red-400" : "border-gray-300"
                  }`}
                  placeholder={'{"values": ["draft", "active"]}'}
                />
                {paramError && <p className="text-xs text-red-500 mt-1">{paramError}</p>}
                <p className="text-xs text-gray-400 mt-1">
                  required: {"{}"} · allowed_values: {`{"values":[]}`} · default_value: {`{"value":"x"}`} · min/max_value: {`{"value":0}`} · regex: {`{"pattern":"^..."}`}
                </p>
              </div>

              {/* Error message */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Error Message</label>
                <input
                  type="text"
                  value={form.error_message}
                  onChange={(e) => setForm({ ...form, error_message: e.target.value })}
                  placeholder="e.g. Supplier is required."
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Severity + Sort order */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
                  <select
                    value={form.severity}
                    onChange={(e) => setForm({ ...form, severity: e.target.value as Severity })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="error">Error</option>
                    <option value="warning">Warning</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Sort Order</label>
                  <input
                    type="number"
                    value={form.sort_order}
                    onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Active toggle */}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setForm({ ...form, is_active: !form.is_active })}
                  className={`w-10 h-5 rounded-full transition-colors ${form.is_active ? "bg-blue-500" : "bg-gray-300"}`}
                >
                  <span
                    className={`block w-4 h-4 bg-white rounded-full shadow transform transition-transform mx-0.5 ${
                      form.is_active ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
                <span className="text-sm text-gray-600">Active</span>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !!paramError}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
              >
                {saving ? "Saving…" : editing ? "Save Changes" : "Create Rule"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
