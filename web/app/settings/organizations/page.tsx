'use client'
import { useEffect, useState, useCallback } from 'react'
import {
  Building2, Plus, ChevronDown, ChevronRight, Pencil,
  Trash2, Check, X, AlertTriangle, RefreshCw, Layers,
  List, GitBranch, MapPin, Warehouse, Users
} from 'lucide-react'
import { api } from '../../lib/api'

// ── Types ─────────────────────────────────────────────────────
interface Org {
  organization_id: string
  organization_code: string
  organization_name: string
  organization_type: string
  default_currency: string
  country: string
  status: string
  parent_name: string
  parent_organization_id: string | null
  bu_count: number
  created_at: string
}

interface BU {
  business_unit_id: string
  business_unit_code: string
  business_unit_name: string
  organization_id: string
  parent_business_unit_id: string | null
  parent_name: string
  status: string
}

// Tree node types
type NodeType = 'org' | 'bu' | 'department' | 'facility' | 'warehouse'

interface TreeNode {
  id: string
  code: string
  name: string
  type: NodeType
  status: string
  children: TreeNode[]
  meta?: string
}

// ── Constants ─────────────────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
  ACTIVE:    'bg-green-100 text-green-700',
  INACTIVE:  'bg-gray-100 text-gray-500',
  SUSPENDED: 'bg-red-100 text-red-700',
}
const sc = (s: string) => STATUS_COLORS[s] ?? STATUS_COLORS.INACTIVE

const NODE_ICONS: Record<NodeType, React.ElementType> = {
  org:        Building2,
  bu:         Layers,
  department: Users,
  facility:   MapPin,
  warehouse:  Warehouse,
}

const NODE_COLORS: Record<NodeType, string> = {
  org:        'text-blue-600',
  bu:         'text-indigo-500',
  department: 'text-purple-500',
  facility:   'text-orange-500',
  warehouse:  'text-teal-500',
}

const NODE_LABELS: Record<NodeType, string> = {
  org:        'Organization',
  bu:         'Business Unit',
  department: 'Department',
  facility:   'Facility',
  warehouse:  'Warehouse',
}

function fmtDate(d: string) {
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

// ── Inline edit field ─────────────────────────────────────────
function EditField({ value, onSave }: { value: string; onSave: (v: string) => Promise<void> }) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(value)
  const [saving, setSaving] = useState(false)

  const save = async () => {
    if (!val.trim() || val === value) { setEditing(false); setVal(value); return }
    setSaving(true)
    await onSave(val.trim())
    setSaving(false)
    setEditing(false)
  }

  if (!editing) return (
    <span className="group flex items-center gap-1 cursor-pointer" onClick={() => setEditing(true)}>
      {value}
      <Pencil size={11} className="text-gray-300 group-hover:text-blue-400 shrink-0" />
    </span>
  )
  return (
    <span className="flex items-center gap-1">
      <input autoFocus value={val} onChange={e => setVal(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') { setEditing(false); setVal(value) } }}
        className="border rounded px-1.5 py-0.5 text-sm w-44 focus:outline-none focus:ring-1 focus:ring-blue-500" />
      <button onClick={save} disabled={saving} className="text-green-600 hover:text-green-700">
        {saving ? <RefreshCw size={13} className="animate-spin" /> : <Check size={13} />}
      </button>
      <button onClick={() => { setEditing(false); setVal(value) }} className="text-gray-400 hover:text-red-500">
        <X size={13} />
      </button>
    </span>
  )
}

// ── Add form ──────────────────────────────────────────────────
function AddForm({ label, onAdd, onCancel, parentLabel }: {
  label: string; parentLabel?: string; onAdd: (code: string, name: string) => Promise<void>; onCancel: () => void
}) {
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    if (!code.trim() || !name.trim()) { setError('Code and name are required'); return }
    setSaving(true); setError('')
    try { await onAdd(code.trim().toUpperCase(), name.trim()) }
    catch (e: unknown) {
      setError((e as {response?: {data?: {detail?: string}}})?.response?.data?.detail || 'Failed')
    } finally { setSaving(false) }
  }

  return (
    <div className="mt-2 bg-blue-50 border border-blue-200 rounded-lg p-3">
      {parentLabel && <p className="text-xs text-blue-600 mb-2">Adding {label} under {parentLabel}</p>}
      {error && <p className="text-xs text-red-600 mb-1">{error}</p>}
      <div className="flex gap-2 mb-2">
        <input value={code} onChange={e => setCode(e.target.value.toUpperCase())}
          placeholder="Code" maxLength={20}
          className="w-28 border rounded px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-blue-500" />
        <input value={name} onChange={e => setName(e.target.value)}
          placeholder={`${label} name`}
          className="flex-1 border rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
      </div>
      <div className="flex gap-2">
        <button onClick={submit} disabled={saving}
          className="px-2.5 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1">
          {saving ? <RefreshCw size={11} className="animate-spin" /> : <Check size={11} />} Add
        </button>
        <button onClick={onCancel} className="px-2.5 py-1 text-xs text-gray-500 hover:text-gray-700">Cancel</button>
      </div>
    </div>
  )
}

// ── Tree node ─────────────────────────────────────────────────
function TreeNodeRow({ node, depth, orgId, allBUs, onRefresh }: {
  node: TreeNode
  depth: number
  orgId: string
  allBUs: BU[]
  onRefresh: () => void
}) {
  const [open, setOpen] = useState(depth < 2)
  const [adding, setAdding] = useState<NodeType | null>(null)
  const Icon = NODE_ICONS[node.type]
  const hasChildren = node.children.length > 0

  // What can be added under each type
  const addableChild: Record<NodeType, NodeType | null> = {
    org:        'bu',
    bu:         'department',
    department: 'facility',
    facility:   'warehouse',
    warehouse:  null,
  }
  const childType = addableChild[node.type]
  const childLabel = childType ? NODE_LABELS[childType] : null

  const handleAdd = async (code: string, name: string) => {
    if (node.type === 'org') {
      await api.organizations.createBU(node.id, {
        organization_id: node.id,
        business_unit_code: code,
        business_unit_name: name,
        parent_business_unit_id: null,
      })
    } else if (node.type === 'bu') {
      // departments are child BUs
      await api.organizations.createBU(orgId, {
        organization_id: orgId,
        business_unit_code: code,
        business_unit_name: name,
        parent_business_unit_id: node.id,
      })
    } else {
      // facilities and warehouses stored as child BUs for now
      await api.organizations.createBU(orgId, {
        organization_id: orgId,
        business_unit_code: code,
        business_unit_name: name,
        parent_business_unit_id: node.id,
      })
    }
    setAdding(null)
    onRefresh()
  }

  const handleDelete = async () => {
    if (node.children.length > 0) {
      alert(`Cannot delete: ${node.children.length} child node(s) still attached`)
      return
    }
    if (!confirm(`Delete "${node.name}"?`)) return
    if (node.type === 'org') {
      await api.organizations.delete(node.id)
    } else {
      await api.organizations.deleteBU(orgId, node.id)
    }
    onRefresh()
  }

  const handleRename = async (name: string) => {
    if (node.type === 'org') {
      await api.organizations.update(node.id, { organization_name: name })
    } else {
      await api.organizations.updateBU(orgId, node.id, { business_unit_name: name })
    }
    onRefresh()
  }

  const indentPx = depth * 24

  return (
    <div>
      <div className="group flex items-center gap-2 py-2 px-3 hover:bg-gray-50 rounded-lg transition-colors"
        style={{ paddingLeft: `${12 + indentPx}px` }}>
        {/* Expand toggle */}
        <button onClick={() => setOpen(o => !o)}
          className={`shrink-0 text-gray-400 hover:text-gray-600 transition-colors ${!hasChildren && !adding ? 'invisible' : ''}`}>
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>

        {/* Icon */}
        <Icon size={15} className={`shrink-0 ${NODE_COLORS[node.type]}`} />

        {/* Name + code */}
        <div className="flex-1 flex items-center gap-2 min-w-0">
          <EditField value={node.name} onSave={handleRename} />
          <span className="font-mono text-xs text-gray-400">{node.code}</span>
          <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${sc(node.status)}`}>{node.status}</span>
          <span className="text-xs text-gray-300 hidden group-hover:inline">{NODE_LABELS[node.type]}</span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {childLabel && (
            <button onClick={() => { setAdding(childType); setOpen(true) }}
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 px-2 py-1 rounded hover:bg-blue-50">
              <Plus size={11} /> {childLabel}
            </button>
          )}
          <button onClick={handleDelete} className="text-gray-300 hover:text-red-500 p-1">
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {/* Add form */}
      {adding && open && (
        <div style={{ paddingLeft: `${36 + indentPx}px`, paddingRight: '12px' }}>
          <AddForm
            label={NODE_LABELS[adding]}
            parentLabel={node.name}
            onAdd={handleAdd}
            onCancel={() => setAdding(null)}
          />
        </div>
      )}

      {/* Children */}
      {open && node.children.map(child => (
        <TreeNodeRow key={child.id} node={child} depth={depth + 1}
          orgId={orgId} allBUs={allBUs} onRefresh={onRefresh} />
      ))}
    </div>
  )
}

// ── Build tree from flat BU list ──────────────────────────────
function buildTree(org: Org, bus: BU[]): TreeNode {
  // Determine node type by depth
  const getType = (bu: BU, allBUs: BU[]): NodeType => {
    let depth = 0
    let current: BU | undefined = bu
    while (current?.parent_business_unit_id) {
      depth++
      current = allBUs.find(b => b.business_unit_id === current!.parent_business_unit_id)
    }
    if (depth === 0) return 'bu'
    if (depth === 1) return 'department'
    if (depth === 2) return 'facility'
    return 'warehouse'
  }

  const makeNode = (bu: BU): TreeNode => ({
    id: bu.business_unit_id,
    code: bu.business_unit_code,
    name: bu.business_unit_name,
    type: getType(bu, bus),
    status: bu.status,
    children: bus
      .filter(b => b.parent_business_unit_id === bu.business_unit_id)
      .map(makeNode),
  })

  return {
    id: org.organization_id,
    code: org.organization_code,
    name: org.organization_name,
    type: 'org',
    status: org.status,
    children: bus
      .filter(b => !b.parent_business_unit_id)
      .map(makeNode),
  }
}

// ── Add org form ──────────────────────────────────────────────
function AddOrgForm({ orgs, onAdd, onCancel }: {
  orgs: Org[]; onAdd: () => void; onCancel: () => void
}) {
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [currency, setCurrency] = useState('USD')
  const [parentId, setParentId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    if (!code.trim() || !name.trim()) { setError('Code and name are required'); return }
    setSaving(true); setError('')
    try {
      await api.organizations.create({
        organization_code: code.trim(),
        organization_name: name.trim(),
        default_currency: currency,
        parent_organization_id: parentId || null,
      })
      onAdd()
    } catch (e: unknown) {
      setError((e as {response?: {data?: {detail?: string}}})?.response?.data?.detail || 'Failed')
    } finally { setSaving(false) }
  }

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
      <p className="text-sm font-medium text-blue-800 mb-3">New organization</p>
      {error && <p className="text-xs text-red-600 mb-2">{error}</p>}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Code *</label>
          <input value={code} onChange={e => setCode(e.target.value.toUpperCase())} placeholder="FLOWOPS"
            className="w-full border rounded px-2 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Name *</label>
          <input value={name} onChange={e => setName(e.target.value)} placeholder="Flow Ops Global LLC"
            className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Currency</label>
          <select value={currency} onChange={e => setCurrency(e.target.value)}
            className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            {['USD','EUR','GBP','CAD','MXN','BRL','AUD'].map(c => <option key={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Parent organization</label>
          <select value={parentId} onChange={e => setParentId(e.target.value)}
            className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">— None (top level) —</option>
            {orgs.map(o => <option key={o.organization_id} value={o.organization_id}>{o.organization_name}</option>)}
          </select>
        </div>
      </div>
      <div className="flex gap-2">
        <button onClick={submit} disabled={saving}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1.5">
          {saving ? <RefreshCw size={13} className="animate-spin" /> : <Check size={13} />} Create
        </button>
        <button onClick={onCancel} className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700">Cancel</button>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────
export default function OrganizationsPage() {
  const [orgs, setOrgs]       = useState<Org[]>([])
  const [busMap, setBusMap]   = useState<Record<string, BU[]>>({})
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [view, setView]       = useState<'tree' | 'list'>('tree')
  const [error, setError]     = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const res = await api.organizations.list()
      setOrgs(res.data)
      // Load BUs for all orgs
      const map: Record<string, BU[]> = {}
      await Promise.all(res.data.map(async (org: Org) => {
        const buRes = await api.organizations.listBUs(org.organization_id)
        map[org.organization_id] = buRes.data
      }))
      setBusMap(map)
    } catch { setError('Failed to load organizations') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  // Count nodes by type across all orgs
  const totalBUs = Object.values(busMap).flat().length
  const totalDepts = Object.values(busMap).flat()
    .filter(b => b.parent_business_unit_id !== null).length

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Building2 className="text-blue-600" size={22} />
            <div>
              <h1 className="text-xl font-semibold text-gray-800">Organizations</h1>
              <p className="text-xs text-gray-400">
                Legal entities · Business units · Departments · Facilities · Warehouses
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* View toggle */}
            <div className="flex border rounded-lg overflow-hidden">
              <button onClick={() => setView('tree')}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors ${
                  view === 'tree' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-50'
                }`}>
                <GitBranch size={13} /> Tree
              </button>
              <button onClick={() => setView('list')}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors ${
                  view === 'list' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-50'
                }`}>
                <List size={13} /> List
              </button>
            </div>
            <button onClick={load}
              className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-blue-600 transition-colors px-2 py-1.5">
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            </button>
            <button onClick={() => setShowAdd(true)}
              className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
              <Plus size={15} /> New organization
            </button>
          </div>
        </div>

        {/* Stats strip */}
        <div className="flex gap-6 mt-3 text-xs text-gray-500">
          {[
            { icon: Building2, label: 'Organizations', val: orgs.length, color: 'text-blue-600' },
            { icon: Layers,    label: 'Business Units', val: totalBUs - totalDepts, color: 'text-indigo-500' },
            { icon: Users,     label: 'Departments+',   val: totalDepts, color: 'text-purple-500' },
          ].map(({ icon: Icon, label, val, color }) => (
            <div key={label} className="flex items-center gap-1.5">
              <Icon size={13} className={color} />
              <span className="font-semibold text-gray-700">{val}</span>
              <span>{label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="px-6 py-5">
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-600">{error}</div>
        )}

        {showAdd && (
          <AddOrgForm orgs={orgs} onAdd={() => { setShowAdd(false); load() }} onCancel={() => setShowAdd(false)} />
        )}

        {loading && orgs.length === 0 ? (
          <div className="flex items-center justify-center py-16 text-gray-400 text-sm">
            <RefreshCw size={18} className="animate-spin mr-2" /> Loading…
          </div>
        ) : orgs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400">
            <Building2 size={40} className="mb-3 opacity-30" />
            <p className="text-sm">No organizations yet.</p>
            <button onClick={() => setShowAdd(true)}
              className="mt-3 text-sm text-blue-600 hover:underline flex items-center gap-1">
              <Plus size={14} /> Create your first organization
            </button>
          </div>
        ) : view === 'tree' ? (
          /* ── Tree view ── */
          <div className="space-y-3">
            {orgs.map(org => {
              const bus = busMap[org.organization_id] || []
              const tree = buildTree(org, bus)
              return (
                <div key={org.organization_id} className="bg-white rounded-lg border p-3">
                  <TreeNodeRow
                    node={tree}
                    depth={0}
                    orgId={org.organization_id}
                    allBUs={bus}
                    onRefresh={load}
                  />
                </div>
              )
            })}

            {/* Legend */}
            <div className="flex flex-wrap gap-4 pt-2 px-1">
              {(Object.entries(NODE_LABELS) as [NodeType, string][]).map(([type, label]) => {
                const Icon = NODE_ICONS[type]
                return (
                  <div key={type} className="flex items-center gap-1.5 text-xs text-gray-400">
                    <Icon size={12} className={NODE_COLORS[type]} /> {label}
                  </div>
                )
              })}
            </div>
          </div>
        ) : (
          /* ── List view ── */
          <div className="bg-white rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b text-left">
                  <th className="px-4 py-3 text-xs font-medium text-gray-500">Code</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500">Name</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500">Type</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500">Parent</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500">Status</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500">BUs</th>
                  <th className="px-4 py-3 text-xs font-medium text-gray-500">Created</th>
                </tr>
              </thead>
              <tbody>
                {orgs.map((org, i) => (
                  <tr key={org.organization_id}
                    className={`border-b last:border-0 ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}`}>
                    <td className="px-4 py-3 font-mono text-xs text-blue-700">{org.organization_code}</td>
                    <td className="px-4 py-3 font-medium text-gray-800">{org.organization_name}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{org.organization_type || 'Organization'}</td>
                    <td className="px-4 py-3 text-xs text-gray-400">{org.parent_name || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${sc(org.status)}`}>{org.status}</span>
                    </td>
                    <td className="px-4 py-3 text-center text-xs text-gray-500">{org.bu_count}</td>
                    <td className="px-4 py-3 text-xs text-gray-400">{fmtDate(org.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
