'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, ArrowLeft, BellRing, Database, HardDrive, Search, ShieldCheck, Users } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { FormEvent, useEffect, useState } from 'react'

import { useAuth } from '@/components/providers'
import { ThemeToggle } from '@/components/theme-toggle'
import { request } from '@/lib/api'

type AdminUser={id:string;email:string;name:string;is_active:boolean;is_admin:boolean;created_at:string}
type AdminOverview={
  users:{total:number;active:number;suspended:number;recent_signups_7d:number}
  sessions:{active:number}
  workspaces:number
  projects:number
  tasks:{total:number;completed:number;completion_percentage:number}
  storage:{bytes:number;attachments:number}
  notification_deliveries:Record<string,number>
  push_subscriptions:Record<string,number>
  recent_users:AdminUser[]
}
type AuditLog={id:string;actor_id:string|null;workspace_id:string|null;action:string;ip_address:string|null;metadata:Record<string,unknown>;created_at:string}

function bytes(value:number){if(value>=1024**3)return`${(value/1024**3).toFixed(1)} GB`;if(value>=1024**2)return`${(value/1024**2).toFixed(1)} MB`;if(value>=1024)return`${(value/1024).toFixed(1)} KB`;return`${value} B`}

export default function AdminPage(){
  const {user,token,loading}=useAuth();const router=useRouter();const queryClient=useQueryClient();const [search,setSearch]=useState('')
  useEffect(()=>{if(!loading&&!token)router.replace('/login')},[loading,token,router])
  const overview=useQuery({queryKey:['admin','overview'],queryFn:()=>request<AdminOverview>('/api/v1/admin/overview',{},token),enabled:!!token&&!!user?.is_admin,refetchInterval:30_000})
  const users=useQuery({queryKey:['admin','users',search],queryFn:()=>request<AdminUser[]>(`/api/v1/admin/users${search?`?q=${encodeURIComponent(search)}`:''}`,{},token),enabled:!!token&&!!user?.is_admin})
  const audits=useQuery({queryKey:['admin','audit'],queryFn:()=>request<AuditLog[]>('/api/v1/admin/audit-logs?limit=60',{},token),enabled:!!token&&!!user?.is_admin})
  const accountMutation=useMutation({mutationFn:({id,active}:{id:string;active:boolean})=>request<{id:string;is_active:boolean}>(`/api/v1/admin/users/${id}/${active?'reactivate':'suspend'}`,{method:'POST'},token),onSuccess:async()=>{await Promise.all([queryClient.invalidateQueries({queryKey:['admin','users']}),queryClient.invalidateQueries({queryKey:['admin','overview']}),queryClient.invalidateQueries({queryKey:['admin','audit']})])}})
  function submitSearch(e:FormEvent){e.preventDefault();void users.refetch()}
  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading TaskPilot…</div>
  if(!user?.is_admin)return <main className="grid min-h-screen place-items-center p-6"><div className="panel max-w-md rounded-3xl p-8 text-center"><ShieldCheck className="mx-auto text-indigo-600" size={40}/><h1 className="mt-4 text-xl font-semibold">Administrator access required</h1><p className="mt-2 text-sm muted">This area is restricted to TaskPilot administrators.</p><Link href="/app" className="mt-6 inline-block rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white">Back to TaskPilot</Link></div></main>
  const o=overview.data
  const deliveryTotal=Object.values(o?.notification_deliveries??{}).reduce((a,b)=>a+b,0)
  const deliveryFailed=(o?.notification_deliveries.failed??0)+(o?.notification_deliveries.exhausted??0)
  return <main className="min-h-screen bg-[var(--bg)]">
    <header className="sticky top-0 z-20 border-b border-[var(--line)] bg-[var(--panel)]/95 backdrop-blur"><div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6"><div className="flex items-center gap-3"><Link href="/app" className="rounded-xl border border-[var(--line)] p-2" aria-label="Back"><ArrowLeft size={18}/></Link><div><p className="text-xs muted">Operations</p><h1 className="font-semibold">Admin dashboard</h1></div></div><div className="flex items-center gap-2"><span className="hidden rounded-full bg-indigo-500/10 px-3 py-1.5 text-xs font-semibold text-indigo-600 sm:inline">Administrator</span><ThemeToggle/></div></div></header>
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6">
      {overview.isError&&<div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-600">Could not load operational metrics.</div>}
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={<Users size={19}/>} label="Users" value={o?String(o.users.total):'—'} note={o?`${o.users.active} active · ${o.users.suspended} suspended`:'Loading…'}/>
        <Metric icon={<Database size={19}/>} label="Workspaces / projects" value={o?`${o.workspaces} / ${o.projects}`:'—'} note={o?`${o.users.recent_signups_7d} new users in 7d`:'Loading…'}/>
        <Metric icon={<Activity size={19}/>} label="Tasks" value={o?String(o.tasks.total):'—'} note={o?`${o.tasks.completion_percentage}% completed · ${o.sessions.active} active sessions`:'Loading…'}/>
        <Metric icon={<HardDrive size={19}/>} label="Storage" value={o?bytes(o.storage.bytes):'—'} note={o?`${o.storage.attachments} attachments`:'Loading…'}/>
      </section>
      <section className="grid gap-4 lg:grid-cols-3">
        <div className="panel rounded-2xl p-5 lg:col-span-2"><div className="flex items-center justify-between"><div><p className="text-xs uppercase tracking-wider muted">Notification infrastructure</p><h2 className="mt-1 font-semibold">Delivery health</h2></div><BellRing size={20} className="text-indigo-600"/></div><div className="mt-5 grid gap-3 sm:grid-cols-3"><SmallStat label="Deliveries" value={deliveryTotal}/><SmallStat label="Failed / exhausted" value={deliveryFailed}/><SmallStat label="Push endpoints" value={Object.values(o?.push_subscriptions??{}).reduce((a,b)=>a+b,0)}/></div><div className="mt-4 flex flex-wrap gap-2">{Object.entries(o?.notification_deliveries??{}).map(([key,value])=><span key={key} className="rounded-full border border-[var(--line)] px-3 py-1 text-xs"><b>{value}</b> {key}</span>)}{Object.entries(o?.push_subscriptions??{}).map(([key,value])=><span key={key} className="rounded-full bg-indigo-500/10 px-3 py-1 text-xs text-indigo-600"><b>{value}</b> {key}</span>)}</div></div>
        <div className="panel rounded-2xl p-5"><p className="text-xs uppercase tracking-wider muted">Recent signups</p><div className="mt-3 space-y-3">{o?.recent_users.slice(0,6).map(item=><div key={item.id} className="flex items-center gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-indigo-500/10 text-xs font-semibold text-indigo-600">{item.name.slice(0,2).toUpperCase()}</span><div className="min-w-0"><p className="truncate text-sm font-medium">{item.name}</p><p className="truncate text-xs muted">{item.email}</p></div></div>)}{!o&&<p className="text-sm muted">Loading…</p>}</div></div>
      </section>
      <section className="panel overflow-hidden rounded-2xl"><div className="flex flex-col gap-3 border-b border-[var(--line)] p-5 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-xs uppercase tracking-wider muted">Accounts</p><h2 className="mt-1 font-semibold">User management</h2></div><form onSubmit={submitSearch} className="flex gap-2"><div className="relative"><Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 muted"/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Name or email" className="w-64 max-w-full rounded-xl border border-[var(--line)] bg-transparent py-2 pl-9 pr-3 text-sm"/></div><button className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-medium">Search</button></form></div><div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm"><thead className="bg-black/[.025] dark:bg-white/[.025]"><tr><th className="px-5 py-3">User</th><th className="px-5 py-3">Created</th><th className="px-5 py-3">Role</th><th className="px-5 py-3">Status</th><th className="px-5 py-3 text-right">Action</th></tr></thead><tbody>{users.data?.map(item=><tr key={item.id} className="border-t border-[var(--line)]"><td className="px-5 py-4"><p className="font-medium">{item.name}</p><p className="text-xs muted">{item.email}</p></td><td className="px-5 py-4 muted">{new Date(item.created_at).toLocaleDateString()}</td><td className="px-5 py-4">{item.is_admin?<span className="rounded-full bg-indigo-500/10 px-2.5 py-1 text-xs font-semibold text-indigo-600">Admin</span>:<span className="text-xs muted">User</span>}</td><td className="px-5 py-4"><span className={`rounded-full px-2.5 py-1 text-xs font-medium ${item.is_active?'bg-emerald-500/10 text-emerald-600':'bg-red-500/10 text-red-600'}`}>{item.is_active?'Active':'Suspended'}</span></td><td className="px-5 py-4 text-right">{item.id!==user.id&&<button disabled={accountMutation.isPending} onClick={()=>{const verb=item.is_active?'suspend':'reactivate';if(window.confirm(`${verb[0].toUpperCase()+verb.slice(1)} ${item.email}?`))accountMutation.mutate({id:item.id,active:!item.is_active})}} className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${item.is_active?'border-red-500/30 text-red-600':'border-emerald-500/30 text-emerald-600'}`}>{item.is_active?'Suspend':'Reactivate'}</button>}</td></tr>)}{users.isLoading&&<tr><td colSpan={5} className="px-5 py-10 text-center muted">Loading users…</td></tr>}{users.data?.length===0&&<tr><td colSpan={5} className="px-5 py-10 text-center muted">No matching users.</td></tr>}</tbody></table></div></section>
      <section className="panel overflow-hidden rounded-2xl"><div className="border-b border-[var(--line)] p-5"><p className="text-xs uppercase tracking-wider muted">Security & governance</p><h2 className="mt-1 font-semibold">Audit log</h2></div><div className="max-h-[560px] overflow-auto divide-y divide-[var(--line)]">{audits.data?.map(item=><div key={item.id} className="grid gap-2 px-5 py-4 sm:grid-cols-[1fr_auto]"><div><p className="text-sm font-medium">{item.action}</p><p className="mt-1 text-xs muted">Actor {item.actor_id??'system'}{item.ip_address?` · ${item.ip_address}`:''}</p><p className="mt-2 break-all text-xs muted">{Object.keys(item.metadata).length?JSON.stringify(item.metadata):'No metadata'}</p></div><time className="text-xs muted">{new Date(item.created_at).toLocaleString()}</time></div>)}{audits.isLoading&&<p className="p-8 text-center text-sm muted">Loading audit log…</p>}{audits.data?.length===0&&<p className="p-8 text-center text-sm muted">No audit events yet.</p>}</div></section>
    </div>
  </main>
}

function Metric({icon,label,value,note}:{icon:React.ReactNode;label:string;value:string;note:string}){return <div className="panel rounded-2xl p-5"><div className="flex items-center gap-2 text-indigo-600">{icon}<p className="text-xs font-semibold uppercase tracking-wider">{label}</p></div><p className="mt-4 text-3xl font-semibold tracking-tight">{value}</p><p className="mt-1 text-xs muted">{note}</p></div>}
function SmallStat({label,value}:{label:string;value:number}){return <div className="rounded-xl border border-[var(--line)] p-3"><p className="text-xs muted">{label}</p><p className="mt-1 text-xl font-semibold">{value}</p></div>}
