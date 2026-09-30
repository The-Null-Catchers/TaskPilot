'use client'

import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ListFilter } from 'lucide-react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'

import { useAuth } from '@/components/providers'
import { ThemeToggle } from '@/components/theme-toggle'
import { request, TaskPage } from '@/lib/api'

const priorities = ['all', 'urgent', 'high', 'medium', 'low', 'none'] as const
const statuses = ['all', 'open', 'in_progress', 'review', 'done'] as const

function nice(value:string){return value.replaceAll('_',' ').replace(/\b\w/g,m=>m.toUpperCase())}

export default function ProjectListPage(){
  const {projectId}=useParams<{projectId:string}>()
  const {token,loading}=useAuth()
  const router=useRouter()
  const [status,setStatus]=useState<(typeof statuses)[number]>('all')
  const [priority,setPriority]=useState<(typeof priorities)[number]>('all')
  const [sortBy,setSortBy]=useState<'due_date'|'priority'|'created_at'|'updated_at'>('due_date')

  useEffect(()=>{if(!loading&&!token)router.replace('/login')},[loading,token,router])

  const query=useMemo(()=>{
    const p=new URLSearchParams({project_id:projectId,scope:'all',limit:'100',sort_by:sortBy,sort_direction:sortBy==='due_date'?'asc':'desc'})
    if(status!=='all')p.set('status',status)
    if(priority!=='all')p.set('priority',priority)
    return p.toString()
  },[projectId,status,priority,sortBy])

  const tasks=useQuery({queryKey:['project-list',query],queryFn:()=>request<TaskPage>(`/api/v1/my-tasks?${query}`,{},token),enabled:!!token&&!!projectId})

  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading TaskPilot…</div>
  return <main className="min-h-screen bg-[var(--bg)]">
    <header className="border-b border-[var(--line)] bg-[var(--panel)]"><div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6"><div className="flex items-center gap-3"><Link href={`/app/projects/${projectId}/overview`} className="rounded-xl border border-[var(--line)] p-2"><ArrowLeft size={18}/></Link><div><p className="text-xs muted">Project view</p><h1 className="font-semibold">Task list</h1></div></div><ThemeToggle/></div></header>
    <div className="mx-auto max-w-7xl p-4 sm:p-6">
      <section className="panel rounded-2xl p-4"><div className="mb-3 flex items-center gap-2 text-sm font-semibold"><ListFilter size={17}/>Project filters</div><div className="grid gap-3 sm:grid-cols-3"><label className="text-xs muted">Status<select value={status} onChange={e=>setStatus(e.target.value as typeof status)} className="mt-1 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] p-2.5 text-sm">{statuses.map(v=><option key={v} value={v}>{nice(v)}</option>)}</select></label><label className="text-xs muted">Priority<select value={priority} onChange={e=>setPriority(e.target.value as typeof priority)} className="mt-1 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] p-2.5 text-sm">{priorities.map(v=><option key={v} value={v}>{nice(v)}</option>)}</select></label><label className="text-xs muted">Sort<select value={sortBy} onChange={e=>setSortBy(e.target.value as typeof sortBy)} className="mt-1 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] p-2.5 text-sm"><option value="due_date">Due date</option><option value="priority">Priority</option><option value="created_at">Created</option><option value="updated_at">Updated</option></select></label></div></section>
      {tasks.isLoading&&<div className="panel mt-4 animate-pulse rounded-2xl p-12 text-center text-sm muted">Loading project tasks…</div>}
      {tasks.isError&&<div className="mt-4 rounded-2xl border border-red-300/40 bg-red-500/5 p-5 text-sm text-red-600">Could not load project tasks.</div>}
      {!tasks.isLoading&&!tasks.isError&&<section className="mt-4 overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--panel)]"><div className="hidden grid-cols-[100px_1fr_110px_120px] gap-3 border-b border-[var(--line)] px-4 py-3 text-xs font-semibold muted sm:grid"><span>ID</span><span>Task</span><span>Priority</span><span>Due</span></div>{tasks.data?.items.map(task=><Link href={`/app/tasks/${task.id}`} key={task.id} className="block border-b border-[var(--line)] px-4 py-3 text-sm last:border-0 hover:bg-black/[.025] dark:hover:bg-white/[.025] sm:grid sm:grid-cols-[100px_1fr_110px_120px] sm:gap-3"><span className="text-xs font-semibold muted">{task.identifier}</span><span className="mt-1 block min-w-0 truncate font-medium sm:mt-0">{task.title}<span className="mt-1 block text-xs font-normal muted sm:hidden">{nice(task.priority)} · {task.due_date?new Date(task.due_date).toLocaleDateString():'No due date'}</span></span><span className="hidden text-xs muted sm:block">{nice(task.priority)}</span><span className="hidden text-xs muted sm:block">{task.due_date?new Date(task.due_date).toLocaleDateString():'—'}</span></Link>)}{tasks.data?.items.length===0&&<div className="p-12 text-center text-sm muted">No tasks match these filters.</div>}</section>}
    </div>
  </main>
}
