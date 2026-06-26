'use client'
import { useEffect, useState, useCallback } from 'react'
import {
  Bell, Plus, Trash2, Check, X, RefreshCw,
  Zap, Filter, ChevronDown, Eye, EyeOff, Settings
} from 'lucide-react'
import { api } from '../../lib/api'

// ── Types ─────────────────────────────────────────────────────
interface WorkflowRule {
  rule_id: string
  rule_code: string
  rule_name: string
  rule_description: string
  trigger_entity: string
  trigger_event: string
  trigger_status_from: string | null
  trigger_status_to: string | null
  filter_bu_name: string
  filter_customer_name: string
  filter_supplier_name: string
  filter_mode_code: string
  filter_country: string | null
  filter_priority: string | null
  filter_shipment_type: string | null
  action_type: string
  action_recipients: string[]
  notification_template: string
  priority_order: number
  status: string
  created_at: string
}

interface Notification {
  notification_id: string
  entity_type: string
  entity_number: string
  trigger_event: string
  trigger_status_from: string | null
  trigger_status_to: string | null
  title: string
  message: string
  is_read: boolean
  recipient_role: string | null
  created_at: string
  rule_name: string
}

// ── Constants ─────────────────────────────────────────────────
const ENTITY_COLORS: Record<string, string> = {
  SHIPMENT:       'bg-blue-100 text-blue-700',
  PURCHASE_ORDER: 'bg-indigo-100 text-indigo-700',
  ORDER_RELEASE:  'bg-purple-100 text-purple-700',
  CARRIER_INVOICE:'bg-orange-100 text-orange-700',
}

const STATUS_COLORS: Record<string, string> = {
  ACTIVE:   'bg-green-100 text-green-700',
  INACTIVE: 'bg-gray-100 text-gray-500',
}

function fmtDate(d: string) {
  return new Date(d).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
  })
}

function fmtRecipients(recs: string[] | string): string {
  const arr = typeof recs === 'string' ? JSON.parse(recs) : recs
  return arr.map((r: string) => r.replace('role:', '').replace('user:', 'User: ')).join(', ')
}

// ── Add rule form ─────────────────────────────────────────────
function AddRuleForm({ onAdd, onCancel }: { onAdd: () => void; onCancel: () => void }) {
  const [form, setForm] = useState({
    rule_code: '', rule_name: '', rule_description: '',
    trigger_entity: 'SHIPMENT', trigger_event: 'STATUS_CHANGE',
    trigger_status_from: '', trigger_status_to: '',
    filter_country: '', filter_priority: '', filter_shipment_type: '',
    notification_template: '', priority_order: '100', status: 'ACTIVE',
    action_recipients_raw: 'role:PLANNER',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const update = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const submit = async () => {
    if (!form.rule_code || !form.rule_name) { setError('Code and name are required'); return }
    setSaving(true); setError('')
    try {
      await api.workflows.createRule({
        ...form,
        trigger_status_from: form.trigger_status_from || null,
        trigger_status_to:   form.trigger_status_to   || null,
        filter_country:      form.filter_country      || null,
        filter_priority:     form.filter_priority     || null,
        filter_shipment_type:form.filter_shipment_type|| null,
        priority_order: parseInt(form.priority_order) || 100,
        action_recipients: form.action_recipients_raw.split(',').map(s => s.trim()).filter(Boolean),
        conditions: {},
      })
      onAdd()
    } catch (e: unknown) {
      setError((e as {response?: {data?: {detail?: string}}})?.response?.data?.detail || 'Failed')
    } finally { setSaving(false) }
  }

  const inp = 'w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500'

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-5 mb-4">
      <p className="text-sm font-semibold text-blue-800 mb-4">New Workflow Rule</p>
      {error && <p className="text-xs text-red-600 mb-3">{error}</p>}

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Rule Code *</label>
          <input value={form.rule_code} onChange={e => update('rule_code', e.target.value.toUpperCase())}
            placeholder="SHP-PICKUP" className={`${inp} font-mono`} />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Rule Name *</label>
          <input value={form.rule_name} onChange={e => update('rule_name', e.target.value)}
            placeholder="Shipment Picked Up" className={inp} />
        </div>
      </div>

      <div className="mb-3">
        <label className="text-xs text-gray-500 mb-1 block">Description</label>
        <input value={form.rule_description} onChange={e => update('rule_description', e.target.value)}
          placeholder="When does this trigger?" className={inp} />
      </div>

      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Trigger Entity</label>
          <select value={form.trigger_entity} onChange={e => update('trigger_entity', e.target.value)} className={inp}>
            <option value="SHIPMENT">Shipment</option>
            <option value="PURCHASE_ORDER">Purchase Order</option>
            <option value="ORDER_RELEASE">Order Release</option>
            <option value="CARRIER_INVOICE">Carrier Invoice</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Trigger Event</label>
          <select value={form.trigger_event} onChange={e => update('trigger_event', e.target.value)} className={inp}>
            <option value="STATUS_CHANGE">Status Change</option>
            <option value="CREATED">Created</option>
            <option value="UPDATED">Updated</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Priority Order</label>
          <input type="number" value={form.priority_order} onChange={e => update('priority_order', e.target.value)}
            className={inp} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Status From (blank = any)</label>
          <input value={form.trigger_status_from} onChange={e => update('trigger_status_from', e.target.value)}
            placeholder="PLANNED" className={`${inp} font-mono`} />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Status To (blank = any)</label>
          <input value={form.trigger_status_to} onChange={e => update('trigger_status_to', e.target.value)}
            placeholder="IN_TRANSIT" className={`${inp} font-mono`} />
        </div>
      </div>

      <div className="mb-3">
        <label className="text-xs text-gray-500 mb-1 block">
          Recipients (comma-separated: role:PLANNER, role:FINANCE, email:x@y.com)
        </label>
        <input value={form.action_recipients_raw}
          onChange={e => update('action_recipients_raw', e.target.value)}
          placeholder="role:PLANNER,role:FINANCE" className={inp} />
      </div>

      <div className="mb-4">
        <label className="text-xs text-gray-500 mb-1 block">
          Notification template (use {'{{entity_number}}'} for the reference number)
        </label>
        <textarea value={form.notification_template}
          onChange={e => update('notification_template', e.target.value)}
          placeholder="Shipment {{entity_number}} status changed to IN_TRANSIT."
          rows={2} className={`${inp} resize-none`} />
      </div>

      <div className="flex gap-2">
        <button onClick={submit} disabled={saving}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1.5">
          {saving ? <RefreshCw size={13} className="animate-spin" /> : <Check size={13} />} Create Rule
        </button>
        <button onClick={onCancel} className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700">Cancel</button>
      </div>
    </div>
  )
}

// ── Rule card ─────────────────────────────────────────────────
function RuleCard({ rule, onRefresh }: { rule: WorkflowRule; onRefresh: () => void }) {
  const [deleting, setDeleting] = useState(false)
  const [toggling, setToggling] = useState(false)

  const toggle = async () => {
    setToggling(true)
    await api.workflows.updateRule(rule.rule_id, {
      status: rule.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE'
    })
    onRefresh()
    setToggling(false)
  }

  const del = async () => {
    if (!confirm(`Delete rule "${rule.rule_name}"?`)) return
    setDeleting(true)
    await api.workflows.deleteRule(rule.rule_id)
    onRefresh()
  }

  const recipients = typeof rule.action_recipients === 'string'
    ? JSON.parse(rule.action_recipients)
    : rule.action_recipients

  return (
    <div className={`bg-white rounded-lg border p-4 ${rule.status === 'INACTIVE' ? 'opacity-60' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${ENTITY_COLORS[rule.trigger_entity] ?? 'bg-gray-100 text-gray-600'}`}>
              {rule.trigger_entity.replace('_', ' ')}
            </span>
            <span className="text-xs text-gray-400">{rule.trigger_event.replace('_', ' ')}</span>
            {(rule.trigger_status_from || rule.trigger_status_to) && (
              <span className="text-xs font-mono text-gray-500">
                {rule.trigger_status_from || '*'} → {rule.trigger_status_to || '*'}
              </span>
            )}
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[rule.status]}`}>
              {rule.status}
            </span>
          </div>

          <p className="text-sm font-semibold text-gray-800">{rule.rule_name}</p>
          <p className="font-mono text-xs text-gray-400 mb-1">{rule.rule_code}</p>
          {rule.rule_description && <p className="text-xs text-gray-500 mb-2">{rule.rule_description}</p>}

          {/* Filters */}
          {(rule.filter_bu_name || rule.filter_customer_name || rule.filter_supplier_name ||
            rule.filter_mode_code || rule.filter_country || rule.filter_priority) && (
            <div className="flex flex-wrap gap-2 mb-2">
              {rule.filter_bu_name      && <span className="flex items-center gap-1 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded"><Filter size={10} /> BU: {rule.filter_bu_name}</span>}
              {rule.filter_customer_name && <span className="flex items-center gap-1 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded"><Filter size={10} /> Customer: {rule.filter_customer_name}</span>}
              {rule.filter_supplier_name && <span className="flex items-center gap-1 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded"><Filter size={10} /> Supplier: {rule.filter_supplier_name}</span>}
              {rule.filter_mode_code    && <span className="flex items-center gap-1 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded"><Filter size={10} /> Mode: {rule.filter_mode_code}</span>}
              {rule.filter_country      && <span className="flex items-center gap-1 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded"><Filter size={10} /> Country: {rule.filter_country}</span>}
              {rule.filter_priority     && <span className="flex items-center gap-1 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded"><Filter size={10} /> Priority: {rule.filter_priority}</span>}
            </div>
          )}

          {/* Recipients */}
          <div className="flex flex-wrap gap-1">
            {recipients.map((r: string, i: number) => (
              <span key={i} className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-mono">
                {r}
              </span>
            ))}
          </div>

          {rule.notification_template && (
            <p className="text-xs text-gray-400 mt-2 italic truncate">"{rule.notification_template}"</p>
          )}
        </div>

        <div className="flex flex-col items-end gap-2 shrink-0">
          <span className="text-xs text-gray-400">#{rule.priority_order}</span>
          <div className="flex gap-1">
            <button onClick={toggle} disabled={toggling}
              className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-blue-600 transition-colors"
              title={rule.status === 'ACTIVE' ? 'Deactivate' : 'Activate'}>
              {toggling ? <RefreshCw size={14} className="animate-spin" /> :
                rule.status === 'ACTIVE' ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
            <button onClick={del} disabled={deleting}
              className="p-1.5 rounded hover:bg-gray-100 text-gray-300 hover:text-red-500 transition-colors">
              {deleting ? <RefreshCw size={14} className="animate-spin" /> : <Trash2 size={14} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Notification item ─────────────────────────────────────────
function NotificationItem({ n, onRead }: { n: Notification; onRead: (id: string) => void }) {
  const entityColor = ENTITY_COLORS[n.entity_type] ?? 'bg-gray-100 text-gray-600'
  return (
    <div className={`flex gap-3 p-4 border-b last:border-0 ${n.is_read ? 'opacity-60' : 'bg-blue-50/30'}`}>
      <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${n.is_read ? 'bg-gray-300' : 'bg-blue-500'}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
          <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${entityColor}`}>
            {n.entity_type.replace('_', ' ')}
          </span>
          {n.recipient_role && (
            <span className="text-xs text-gray-400 font-mono">{n.recipient_role}</span>
          )}
          <span className="text-xs text-gray-400 ml-auto">{fmtDate(n.created_at)}</span>
        </div>
        <p className="text-sm font-medium text-gray-800">{n.title}</p>
        <p className="text-xs text-gray-600 mt-0.5">{n.message}</p>
      </div>
      {!n.is_read && (
        <button onClick={() => onRead(n.notification_id)}
          className="text-gray-300 hover:text-blue-500 transition-colors shrink-0 p-1">
          <Check size={14} />
        </button>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────
export default function WorkflowsPage() {
  const [rules, setRules]           = useState<WorkflowRule[]>([])
  const [notifications, setNotifs]  = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [activeTab, setActiveTab]   = useState<'rules' | 'notifications'>('rules')
  const [entityFilter, setEntityFilter] = useState('')
  const [showAdd, setShowAdd]       = useState(false)
  const [loading, setLoading]       = useState(false)

  const loadRules = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (entityFilter) params.entity = entityFilter
      const res = await api.workflows.listRules(params)
      setRules(res.data)
    } finally { setLoading(false) }
  }, [entityFilter])

  const loadNotifications = useCallback(async () => {
    const res = await api.workflows.listNotifications()
    setNotifs(res.data)
    setUnreadCount(res.unread_count)
  }, [])

  useEffect(() => { loadRules() }, [loadRules])
  useEffect(() => { loadNotifications() }, [loadNotifications])

  const markRead = async (id: string) => {
    await api.workflows.markRead(id)
    loadNotifications()
  }

  const markAllRead = async () => {
    await api.workflows.markAllRead()
    loadNotifications()
  }

  const activeCount   = rules.filter(r => r.status === 'ACTIVE').length
  const inactiveCount = rules.filter(r => r.status === 'INACTIVE').length

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Zap className="text-blue-600" size={22} />
            <div>
              <h1 className="text-xl font-semibold text-gray-800">Workflow Rules</h1>
              <p className="text-xs text-gray-400">
                Configurable notifications by entity, status, BU, carrier, mode, and more
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => { loadRules(); loadNotifications() }}
              className="text-gray-400 hover:text-blue-600 p-1.5 rounded hover:bg-gray-100">
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            </button>
            {activeTab === 'rules' && (
              <button onClick={() => setShowAdd(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
                <Plus size={15} /> New Rule
              </button>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="flex gap-6 mt-3 text-xs text-gray-500">
          <span><span className="font-semibold text-gray-700">{rules.length}</span> total rules</span>
          <span><span className="font-semibold text-green-600">{activeCount}</span> active</span>
          <span><span className="font-semibold text-gray-400">{inactiveCount}</span> inactive</span>
          <span><span className="font-semibold text-blue-600">{unreadCount}</span> unread notifications</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b px-6 flex gap-0">
        {[
          { key: 'rules',         label: `Rules (${rules.length})`,                icon: Settings },
          { key: 'notifications', label: `Notifications (${unreadCount} unread)`,  icon: Bell    },
        ].map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setActiveTab(key as 'rules' | 'notifications')}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      <div className="px-6 py-5">
        {/* Rules tab */}
        {activeTab === 'rules' && (
          <>
            {showAdd && (
              <AddRuleForm
                onAdd={() => { setShowAdd(false); loadRules() }}
                onCancel={() => setShowAdd(false)}
              />
            )}

            {/* Entity filter */}
            <div className="flex gap-2 mb-4 flex-wrap">
              {['', 'SHIPMENT', 'PURCHASE_ORDER', 'ORDER_RELEASE', 'CARRIER_INVOICE'].map(e => (
                <button key={e} onClick={() => setEntityFilter(e)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                    entityFilter === e ? 'bg-blue-600 text-white' : 'bg-white border text-gray-600 hover:bg-gray-50'
                  }`}>
                  {e || 'All entities'}
                </button>
              ))}
            </div>

            {rules.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                <Zap size={40} className="mb-3 opacity-30" />
                <p className="text-sm">No workflow rules yet.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {rules.map(rule => (
                  <RuleCard key={rule.rule_id} rule={rule} onRefresh={loadRules} />
                ))}
              </div>
            )}
          </>
        )}

        {/* Notifications tab */}
        {activeTab === 'notifications' && (
          <>
            {unreadCount > 0 && (
              <div className="flex justify-end mb-3">
                <button onClick={markAllRead}
                  className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                  <Check size={12} /> Mark all read
                </button>
              </div>
            )}
            <div className="bg-white rounded-lg border overflow-hidden">
              {notifications.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                  <Bell size={40} className="mb-3 opacity-30" />
                  <p className="text-sm">No notifications yet.</p>
                  <p className="text-xs mt-1">Trigger workflow rules to generate notifications.</p>
                </div>
              ) : (
                notifications.map(n => (
                  <NotificationItem key={n.notification_id} n={n} onRead={markRead} />
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
