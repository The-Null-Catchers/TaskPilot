'use client'

import { useQuery } from '@tanstack/react-query'
import { ArchiveRestore, ArrowLeft, RotateCcw } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'

import { useAuth } from '@/components/providers'
import { ThemeToggle } from '@/components/theme-toggle'
import { Project, request, Task, Workspace } from '@/lib/api'

export default function ArchivedTasksPage() {
  const {token,loading}=useAuth()
  const router=useRouter()
  const [workspaceId,setWorkspaceId]=useState('')
  const [projectId,setProjectId]=useState('')
  const [restoring,setRestoring]=useState<string|null>(null)
  const [error,setError]=useState('')

  useEffect(()=>{if(!loading&&!token)router.replace('/login')},[loading,token,router])

  const workspaces=useQuery({
    queryKey:['workspaces'],
    queryFn:()=>request<Workspace[]>('/api/v1/workspaces',{},token),
    enabled:!!token,
  })
  const projects=useQuery({
    queryKey:['archived-projects',workspaceId],
    queryFn:()=>request<Project[]>(`/api/v1/projects?workspace_id=${workspaceId}`,{},token),
    enabled:!!token&&!!workspaceId,
  })
  const queryString=useMemo(()=>{
    if(!workspaceId)return ''
    const params=new URLSearchParams()
    if(projectId)params.set('project_id',projectId)
    return params.toString()
  },[workspaceId,projectId])
  const archived=useQuery({
    queryKey:['archived-tasks',workspaceId,projectId],
    queryFn:()=>request<Task[]>(`/api/v1/workspaces/${workspaceId}/archived-tasks${queryString?`?${queryString}`:''}`,{},token),
    enabled:!!token&&!!workspaceId,
  })

  useEffect(()=>{
    if(!workspaceId&&workspaces.data?.length)setWorkspaceId(workspaces.data[0].id)
  },[workspaceId,workspaces.data])

  async function restore(taskId:string){
    setRestoring(taskId);setError('')
    try{
      await request<Task>(`/api/v1/tasks/${taskId}/restore`,{method:'POST'},token)
      await archived.refetch()
    }catch(value){
      setError(value instanceof Error?value.message:'Could not restore task')
    }finally{
      setRestoring(null)
    }
  }

  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading TaskPilot…</div>

  return <main className="min-h-screen bg-[var(--bg)]">
    <header className="border-b border-[var(--line)] bg-[var(--panel)]">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <Link href="/app/my-tasks" className="rounded-xl border border-[var(--line)] p-2" aria-label="Back to My Tasks"><ArrowLeft size={18}/></Link>
          <div><p className="text-xs muted">Task lifecycle</p><h1 className="font-semibold">Archived tasks</h1></div>
        </div>
        <ThemeToggle/>
      </div>
    </header>

    <div className="mx-auto max-w-6xl p-4 sm:p-6">
      <section className="panel rounded-2xl p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs muted">Workspace
            <select value={workspaceId} onChange={e=>{setWorkspaceId(e.target.value);setProjectId('')}} className="mt-1 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] p-2.5 text-sm">
              {workspaces.data?.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label className="text-xs muted">Project
            <select value={projectId} onChange={e=>setProjectId(e.target.value)} disabled={!workspaceId} className="mt-1 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] p-2.5 text-sm">
              <option value="">All accessible projects</option>
              {projects.data?.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
        </div>
      </section>

      {error&&<p className="mt-4 rounded-xl border border-red-500/20 bg-red-500/5 p-3 text-sm text-red-600">{error}</p>}

      {archived.isLoading&&<div className="mt-5 panel h-40 animate-pulse rounded-2xl"/>}
      {archived.isError&&<div className="mt-5 rounded-2xl border border-red-500/20 bg-red-500/5 p-6 text-center text-sm text-red-600">Could not load archived tasks.</div>}

      {!archived.isLoading&&!archived.isError&&archived.data?.length===0&&
        <section className="panel mt-5 rounded-2xl p-12 text-center">
          <ArchiveRestore className="mx-auto muted"/>
          <h2 className="mt-3 font-semibold">No archived tasks</h2>
          <p className="mt-1 text-sm muted">Archived tasks from this scope will appear here and can be restored.</p>
        </section>
      }

      <section className="mt-5 space-y-3">
        {archived.data?.map(task=><article key={task.id} className="panel rounded-2xl p-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-semibold muted">{task.identifier}</p>
              <h2 className="mt-1 truncate font-medium">{task.title}</h2>
              <p className="mt-2 text-xs muted">{task.status.replaceAll('_',' ')} · {task.priority}</p>
            </div>
            <button type="button" disabled={restoring===task.id} onClick={()=>void restore(task.id)} className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">
              <RotateCcw size={16}/>{restoring===task.id?'Restoring…':'Restore'}
            </button>
          </div>
        </article>)}
      </section>
    </div>
  </main>
}
