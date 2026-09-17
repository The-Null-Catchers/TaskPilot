'use client'

import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, CalendarDays, Filter, ListTodo, Plus, Save, X } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { FormEvent, useEffect, useMemo, useState } from 'react'

import { useAuth } from '@/components/providers'
import { ThemeToggle } from '@/components/theme-toggle'
import { request, SavedView, TaskPage, Workspace } from '@/lib/api'

type Scope = 'assigned'|'created'|'watching'|'all'
const priorities = ['all','urgent','high','medium','low','none'] as const
const statuses = ['all','open','in_progress','review','done'] as const

function nice(value:string) {
  return value.replaceAll('_',' ').replace(/\b\w/g, match=>match.toUpperCase())
}

export default function MyTasksPage() {
  const {token,loading}=useAuth()
  const router=useRouter()
  const [workspaceId,setWorkspaceId]=useState('')
  const [scope,setScope]=useState<Scope>('assigned')
  const [priority,setPriority]=useState<(typeof priorities)[number]>('all')
  const [status,setStatus]=useState<(typeof statuses)[number]>('all')
  const [sortBy,setSortBy]=useState<'due_date'|'priority'|'created_at'|'updated_at'>('due_date')
  const [sortDirection,setSortDirection]=useState<'asc'|'desc'>('asc')
  const [nextSevenDays,setNextSevenDays]=useState(false)
  const [saveOpen,setSaveOpen]=useState(false)

  useEffect(()=>{if(!loading&&!token)router.replace('/login')},[loading,token,router])

  const workspaces=useQuery({
    queryKey:['workspaces'],
    queryFn:()=>request<Workspace[]>('/api/v1/workspaces',{},token),
    enabled:!!token,
  })
  const savedViews=useQuery({
    queryKey:['saved-views',workspaceId],
    queryFn:()=>request<SavedView[]>(`/api/v1/saved-views${workspaceId?`?workspace_id=${workspaceId}`:''}`,{},token),
    enabled:!!token,
  })

  const queryString=useMemo(()=>{
    const params=new URLSearchParams({scope,sort_by:sortBy,sort_direction:sortDirection,limit:'100'})
    if(workspaceId)params.set('workspace_id',workspaceId)
    if(priority!=='all')params.set('priority',priority)
    if(status!=='all')params.set('status',status)
    if(nextSevenDays){
      const date=new Date()
      date.setDate(date.getDate()+7)
      params.set('due_before',date.toISOString())
    }
    return params.toString()
  },[workspaceId,scope,priority,status,sortBy,sortDirection,nextSevenDays])

  const tasks=useQuery({
    queryKey:['my-tasks',queryString],
    queryFn:()=>request<TaskPage>(`/api/v1/my-tasks?${queryString}`,{},token),
    enabled:!!token,
  })

  function applySavedView(view:SavedView) {
    const filters=view.filters as Record<string,unknown>
    if(typeof filters.scope==='string'&&['assigned','created','watching','all'].includes(filters.scope))setScope(filters.scope as Scope)
    if(typeof filters.priority==='string'&&priorities.includes(filters.priority as (typeof priorities)[number]))setPriority(filters.priority as (typeof priorities)[number])
    if(typeof filters.status==='string'&&statuses.includes(filters.status as (typeof statuses)[number]))setStatus(filters.status as (typeof statuses)[number])
    if(typeof filters.nextSevenDays==='boolean')setNextSevenDays(filters.nextSevenDays)
    setSortBy(view.sort_by)
    setSortDirection(view.sort_direction)
  }

  async function saveView(e:FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if(!token||!workspaceId)return
    const form=e.currentTarget
    const data=new FormData(form)
    await request<SavedView>('/api/v1/saved-views',{
      method:'POST',
      body:JSON.stringify({
        workspace_id:workspaceId,
        name:String(data.get('name')??'').trim(),
        filters:{scope,priority,status,nextSevenDays},
        sort_by:sortBy,
        sort_direction:sortDirection,
        display_mode:'list',
      }),
    },token)
    form.reset()
    setSaveOpen(false)
    await savedViews.refetch()
  }

  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading TaskPilot…</div>

  return <main className="min-h-screen bg-[var(--bg)]">
    <header className="sticky top-0 z-20 border-b border-[var(--line)] bg-[var(--panel)]/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/app" aria-label="Back to projects" className="rounded-xl border border-[var(--line)] p-2"><ArrowLeft size={18}/></Link>
          <div className="min-w-0"><p className="text-xs muted">Personal workspace</p><h1 className="truncate font-semibold">My Tasks</h1></div>
        </div>
        <div className="flex items-center gap-2"><ThemeToggle/><button onClick={()=>setSaveOpen(true)} disabled={!workspaceId} className="flex items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-40"><Save size={16}/>Save view</button></div>
      </div>
    </header>

    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <section className="panel rounded-2xl p-4">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold"><Filter size={17}/>Filters</div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <label className="text-xs font-medium muted">Workspace<select value={workspaceId} onChange={e=>setWorkspaceId(e.target.value)} className="mt-1.5 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5 text-sm text-[var(--fg)]"><option value="">All workspaces</option>{workspaces.data?.map(workspace=><option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}</select></label>
          <label className="text-xs font-medium muted">Scope<select value={scope} onChange={e=>setScope(e.target.value as Scope)} className="mt-1.5 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5 text-sm text-[var(--fg)]"><option value="assigned">Assigned to me</option><option value="created">Created by me</option><option value="watching">Watching</option><option value="all">All accessible</option></select></label>
          <label className="text-xs font-medium muted">Status<select value={status} onChange={e=>setStatus(e.target.value as (typeof statuses)[number])} className="mt-1.5 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5 text-sm text-[var(--fg)]">{statuses.map(item=><option key={item} value={item}>{nice(item)}</option>)}</select></label>
          <label className="text-xs font-medium muted">Priority<select value={priority} onChange={e=>setPriority(e.target.value as (typeof priorities)[number])} className="mt-1.5 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5 text-sm text-[var(--fg)]">{priorities.map(item=><option key={item} value={item}>{nice(item)}</option>)}</select></label>
          <label className="text-xs font-medium muted">Sort<select value={sortBy} onChange={e=>setSortBy(e.target.value as typeof sortBy)} className="mt-1.5 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5 text-sm text-[var(--fg)]"><option value="due_date">Due date</option><option value="priority">Priority</option><option value="created_at">Created</option><option value="updated_at">Updated</option></select></label>
          <label className="text-xs font-medium muted">Direction<select value={sortDirection} onChange={e=>setSortDirection(e.target.value as 'asc'|'desc')} className="mt-1.5 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5 text-sm text-[var(--fg)]"><option value="asc">Ascending</option><option value="desc">Descending</option></select></label>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button onClick={()=>setNextSevenDays(value=>!value)} className={`rounded-full border px-3 py-1.5 text-xs font-medium ${nextSevenDays?'border-indigo-500 bg-indigo-500/10 text-indigo-600':'border-[var(--line)] muted'}`}><CalendarDays size={14} className="mr-1.5 inline"/>Due in 7 days</button>
          {savedViews.data?.map(view=><button key={view.id} onClick={()=>applySavedView(view)} className="rounded-full border border-[var(--line)] px-3 py-1.5 text-xs font-medium">{view.name}</button>)}
        </div>
      </section>

      <div className="mt-6 flex items-end justify-between gap-3"><div><p className="text-sm muted">{tasks.data?.total??0} matching tasks</p><h2 className="text-xl font-semibold tracking-tight">Work queue</h2></div></div>

      <section className="mt-4 overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--panel)]">
        {tasks.isLoading&&<div className="p-8 text-center text-sm muted">Loading tasks…</div>}
        {tasks.isError&&<div className="p-8 text-center text-sm text-red-600">Could not load tasks.</div>}
        {tasks.data?.items.map(task=><Link href={`/app/tasks/${task.id}`} key={task.id} className="grid gap-3 border-b border-[var(--line)] p-4 last:border-b-0 hover:bg-black/[.025] dark:hover:bg-white/[.025] sm:grid-cols-[110px_1fr_130px_140px] sm:items-center">
          <span className="text-xs font-semibold muted">{task.identifier}</span>
          <div className="min-w-0"><p className="truncate text-sm font-medium">{task.title}</p><p className="mt-1 text-xs muted">Updated {new Date(task.updated_at).toLocaleDateString()}</p></div>
          <span className="w-fit rounded-full bg-black/5 px-2.5 py-1 text-xs dark:bg-white/5">{nice(task.priority)}</span>
          <span className={`text-xs ${task.due_date&&new Date(task.due_date)<new Date()&&task.status!=='done'?'font-semibold text-red-600':'muted'}`}>{task.due_date?`Due ${new Date(task.due_date).toLocaleDateString()}`:'No due date'}</span>
        </Link>)}
        {tasks.data?.items.length===0&&<div className="p-12 text-center"><div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-indigo-500/10 text-indigo-600"><ListTodo/></div><h3 className="mt-4 font-semibold">Nothing matches this view</h3><p className="mt-1 text-sm muted">Adjust the filters or pick a different saved view.</p></div>}
      </section>
    </div>

    {saveOpen&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/35 p-4" onMouseDown={()=>setSaveOpen(false)}><form onSubmit={saveView} onMouseDown={e=>e.stopPropagation()} className="panel w-full max-w-md rounded-2xl p-6"><div className="flex items-center justify-between"><div><p className="text-xs muted">Reusable filter</p><h2 className="text-lg font-semibold">Save this view</h2></div><button type="button" onClick={()=>setSaveOpen(false)} className="rounded-xl border border-[var(--line)] p-2"><X size={17}/></button></div><label className="mt-5 block text-sm font-medium">Name<input autoFocus required name="name" maxLength={120} placeholder="My critical tasks" className="mt-2 w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-3 outline-none focus:border-indigo-500"/></label><p className="mt-3 text-xs muted">Saved views keep the current scope, status, priority, deadline filter, and sorting.</p><div className="mt-6 flex justify-end"><button className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white"><Plus size={16}/>Save view</button></div></form></div>}
  </main>
}
