'use client'

import { useQuery } from '@tanstack/react-query'
import { Archive, Bell, BellOff, Check, Copy, GitBranch, History, Loader2, Plus, ShieldAlert, Sparkles, Trash2 } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useMemo, useState } from 'react'

import { ActivityItem, Board, DuplicateTaskResult, request, Task, TaskCollaborationState, TaskDependencies } from '@/lib/api'

export function TaskCollaborationPanel({task,token}:{task:Task;token:string}) {
  const router=useRouter()
  const [blockerToAdd,setBlockerToAdd]=useState('')
  const [copied,setCopied]=useState(false)
  const [duplicating,setDuplicating]=useState(false)
  const [confirmArchive,setConfirmArchive]=useState(false)
  const [error,setError]=useState('')

  const state=useQuery({
    queryKey:['task-collaboration-state',task.id],
    queryFn:()=>request<TaskCollaborationState>(`/api/v1/tasks/${task.id}/collaboration-state`,{},token),
  })
  const dependencies=useQuery({
    queryKey:['task-dependencies',task.id],
    queryFn:()=>request<TaskDependencies>(`/api/v1/tasks/${task.id}/dependencies`,{},token),
  })
  const board=useQuery({
    queryKey:['board',task.project_id],
    queryFn:()=>request<Board>(`/api/v1/projects/${task.project_id}/board`,{},token),
  })
  const activity=useQuery({
    queryKey:['task-activity',task.id],
    queryFn:()=>request<ActivityItem[]>(`/api/v1/tasks/${task.id}/activity`,{},token),
  })

  const tasksById=useMemo(()=>new Map((board.data?.tasks??[]).map(item=>[item.id,item])),[board.data?.tasks])
  const existingBlockers=useMemo(()=>new Set((dependencies.data?.blocked_by??[]).map(item=>item.blocker_task_id)),[dependencies.data?.blocked_by])
  const blockerOptions=useMemo(
    ()=>(board.data?.tasks??[]).filter(item=>item.id!==task.id&&!existingBlockers.has(item.id)&&item.status!=='done'),
    [board.data?.tasks,existingBlockers,task.id],
  )

  async function toggleWatch() {
    setError('')
    try {
      await request<void>(`/api/v1/tasks/${task.id}/watch`,{method:state.data?.watching?'DELETE':'POST'},token)
      await state.refetch()
    } catch(value) {
      setError(value instanceof Error?value.message:'Could not update watcher state')
    }
  }

  async function addDependency() {
    if(!blockerToAdd)return
    setError('')
    try {
      await request(`/api/v1/tasks/${task.id}/dependencies`,{method:'POST',body:JSON.stringify({blocker_task_id:blockerToAdd})},token)
      setBlockerToAdd('')
      await Promise.all([dependencies.refetch(),state.refetch(),activity.refetch()])
    } catch(value) {
      setError(value instanceof Error?value.message:'Could not add dependency')
    }
  }

  async function removeDependency(id:string) {
    setError('')
    try {
      await request<void>(`/api/v1/tasks/${task.id}/dependencies/${id}`,{method:'DELETE'},token)
      await Promise.all([dependencies.refetch(),state.refetch(),activity.refetch()])
    } catch(value) {
      setError(value instanceof Error?value.message:'Could not remove dependency')
    }
  }

  async function copyLink() {
    const url=`${window.location.origin}/app/tasks/${task.id}`
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      window.setTimeout(()=>setCopied(false),1600)
    } catch {
      setError('Could not copy the task link.')
    }
  }

  async function duplicateTask() {
    setDuplicating(true);setError('')
    try {
      const result=await request<DuplicateTaskResult>(`/api/v1/tasks/${task.id}/duplicate`,{method:'POST',body:JSON.stringify({})},token)
      router.push(`/app/tasks/${result.task.id}`)
    } catch(value) {
      setError(value instanceof Error?value.message:'Could not duplicate task')
    } finally {
      setDuplicating(false)
    }
  }

  async function archiveTask() {
    setError('')
    try {
      await request<Task>(`/api/v1/tasks/${task.id}/archive`,{method:'POST'},token)
      router.push('/app/my-tasks')
    } catch(value) {
      setError(value instanceof Error?value.message:'Could not archive task')
      setConfirmArchive(false)
    }
  }

  return <section className="mt-8 border-t border-[var(--line)] pt-6">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="flex items-center gap-2 font-semibold"><GitBranch size={18}/>Collaboration</h2>
        <p className="mt-1 text-xs muted">Followers, blockers, sharing, and task lifecycle.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={()=>void toggleWatch()} disabled={state.isLoading} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] px-3 py-2 text-xs font-medium disabled:opacity-50">{state.data?.watching?<BellOff size={15}/>:<Bell size={15}/>} {state.data?.watching?'Unwatch':'Watch'}{state.data&&<span className="rounded-full bg-black/5 px-1.5 py-0.5 dark:bg-white/10">{state.data.watcher_count}</span>}</button>
        <button type="button" onClick={()=>void copyLink()} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] px-3 py-2 text-xs font-medium">{copied?<Check size={15}/>:<Copy size={15}/>} {copied?'Copied':'Copy link'}</button>
        <button type="button" onClick={()=>void duplicateTask()} disabled={duplicating} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] px-3 py-2 text-xs font-medium disabled:opacity-50">{duplicating?<Loader2 size={15} className="animate-spin"/>:<Sparkles size={15}/>}Duplicate</button>
      </div>
    </div>

    {state.data?.blocked&&<div className="mt-4 flex items-start gap-3 rounded-xl border border-amber-500/25 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200"><ShieldAlert size={18} className="mt-0.5 shrink-0"/><div><p className="font-medium">This task is blocked</p><p className="mt-1 text-xs opacity-80">Complete or remove the blocking dependencies before considering this task ready.</p></div></div>}
    {error&&<p role="alert" className="mt-3 rounded-xl border border-red-500/20 bg-red-500/5 px-3 py-2 text-xs text-red-600 dark:text-red-300">{error}</p>}

    <div className="mt-5 rounded-2xl border border-[var(--line)] p-4">
      <div className="flex items-center justify-between gap-3"><div><h3 className="font-medium">Dependencies</h3><p className="mt-1 text-xs muted">Circular relationships are rejected by the server.</p></div><span className="rounded-full bg-black/5 px-2 py-1 text-xs muted dark:bg-white/10">{dependencies.data?.blocked_by.length??0} blockers</span></div>
      <div className="mt-3 space-y-2">
        {dependencies.data?.blocked_by.map(dependency=>{
          const blocker=tasksById.get(dependency.blocker_task_id)
          return <div key={dependency.id} className="flex items-center gap-3 rounded-xl bg-black/[.025] px-3 py-2 dark:bg-white/[.025]"><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{blocker?.identifier??dependency.blocker_task_id.slice(0,8)} · {blocker?.title??'Task'}</p><p className="text-xs muted">{blocker?.status==='done'?'Resolved':'Blocking this task'}</p></div><button type="button" onClick={()=>void removeDependency(dependency.id)} className="rounded-lg p-2 text-red-600 hover:bg-red-500/10" aria-label="Remove dependency"><Trash2 size={15}/></button></div>
        })}
        {!dependencies.isLoading&&dependencies.data?.blocked_by.length===0&&<p className="text-sm muted">No blocking dependencies.</p>}
      </div>
      <div className="mt-3 flex gap-2"><select value={blockerToAdd} onChange={e=>setBlockerToAdd(e.target.value)} className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm"><option value="">Add blocker…</option>{blockerOptions.map(item=><option key={item.id} value={item.id}>{item.identifier} · {item.title}</option>)}</select><button type="button" disabled={!blockerToAdd} onClick={()=>void addDependency()} className="rounded-xl border border-[var(--line)] px-3 disabled:opacity-40" aria-label="Add dependency"><Plus size={16}/></button></div>
      {dependencies.data?.blocks.length? <div className="mt-4 border-t border-[var(--line)] pt-3"><p className="text-xs font-medium muted">This task blocks</p><div className="mt-2 flex flex-wrap gap-2">{dependencies.data.blocks.map(item=>{const blocked=tasksById.get(item.blocked_task_id);return <span key={item.id} className="rounded-full bg-black/5 px-2.5 py-1 text-xs dark:bg-white/10">{blocked?.identifier??item.blocked_task_id.slice(0,8)}</span>})}</div></div>:null}
    </div>

    <div className="mt-5 rounded-2xl border border-[var(--line)] p-4">
      <h3 className="flex items-center gap-2 font-medium"><History size={16}/>Activity</h3>
      <div className="mt-3 space-y-3">
        {activity.data?.slice(0,20).map(item=><div key={item.id} className="flex gap-3 text-sm"><span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-indigo-500"/><div className="min-w-0 flex-1"><p className="leading-5">{item.summary}</p><time className="mt-0.5 block text-xs muted">{new Date(item.created_at).toLocaleString()}</time></div></div>)}
        {activity.isLoading&&<div className="h-16 animate-pulse rounded-xl bg-black/5 dark:bg-white/5"/>}
        {!activity.isLoading&&activity.data?.length===0&&<p className="text-sm muted">No task activity recorded yet.</p>}
      </div>
    </div>

    <div className="mt-5 flex justify-end">
      {confirmArchive?<div className="flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/5 p-2"><span className="px-1 text-xs text-red-700 dark:text-red-300">Archive this task?</span><button type="button" onClick={()=>void archiveTask()} className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white">Archive</button><button type="button" onClick={()=>setConfirmArchive(false)} className="rounded-lg px-3 py-1.5 text-xs">Cancel</button></div>:<button type="button" onClick={()=>setConfirmArchive(true)} className="inline-flex items-center gap-2 rounded-xl border border-red-500/20 px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-500/5"><Archive size={15}/>Archive task</button>}
    </div>
  </section>
}
