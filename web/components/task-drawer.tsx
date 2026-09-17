'use client'

import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, Circle, Clock3, ListChecks, MessageSquare, Plus, UserPlus, X } from 'lucide-react'
import { FormEvent, useEffect, useMemo, useState } from 'react'

import { Checklist, ChecklistItem, Comment, request, Subtask, Task, TimeSummary, UserSummary, WorkspaceMember } from '@/lib/api'

function formatDuration(seconds:number) {
  const hours=Math.floor(seconds/3600)
  const minutes=Math.floor((seconds%3600)/60)
  if(hours)return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function ChecklistSection({taskId, checklist, token}:{taskId:string; checklist:Checklist; token:string}) {
  const items = useQuery({
    queryKey:['checklist-items', checklist.id],
    queryFn:()=>request<ChecklistItem[]>(`/api/v1/tasks/${taskId}/checklists/${checklist.id}/items`,{},token),
  })
  const completed = items.data?.filter(item=>item.completed).length ?? 0
  const total = items.data?.length ?? 0
  const percentage = total ? Math.round((completed / total) * 100) : 0

  async function addItem(e:FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = e.currentTarget
    const data = new FormData(form)
    const title = String(data.get('title') ?? '').trim()
    if (!title) return
    await request<ChecklistItem>(`/api/v1/tasks/${taskId}/checklists/${checklist.id}/items`,{method:'POST',body:JSON.stringify({title})},token)
    form.reset()
    await items.refetch()
  }
  async function toggleItem(item:ChecklistItem) {
    await request<ChecklistItem>(`/api/v1/tasks/${taskId}/checklists/${checklist.id}/items/${item.id}`,{method:'PATCH',body:JSON.stringify({version:item.version,completed:!item.completed})},token)
    await items.refetch()
  }

  return <section className="rounded-2xl border border-[var(--line)] p-4"><div className="flex items-center justify-between gap-3"><div><h3 className="font-medium">{checklist.title}</h3><p className="mt-0.5 text-xs muted">{completed} / {total} complete</p></div><span className="text-xs font-medium muted">{percentage}%</span></div><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-black/5 dark:bg-white/10"><div className="h-full rounded-full bg-indigo-600 transition-all" style={{width:`${percentage}%`}} /></div><div className="mt-4 space-y-2">{items.data?.map(item=><button key={item.id} onClick={()=>void toggleItem(item)} className="flex w-full items-start gap-3 rounded-xl px-2 py-2 text-left hover:bg-black/[.035] dark:hover:bg-white/[.035]">{item.completed?<CheckCircle2 size={18} className="mt-0.5 shrink-0 text-indigo-600"/>:<Circle size={18} className="mt-0.5 shrink-0 muted"/>}<span className={`text-sm leading-5 ${item.completed?'line-through muted':''}`}>{item.title}</span></button>)}{items.isLoading&&<p className="px-2 text-sm muted">Loading checklist…</p>}</div><form onSubmit={addItem} className="mt-3 flex gap-2"><input name="title" required maxLength={240} placeholder="Add checklist item" className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-transparent px-3 py-2 text-sm outline-none focus:border-indigo-500"/><button className="rounded-xl border border-[var(--line)] px-3 py-2" aria-label="Add checklist item"><Plus size={16}/></button></form></section>
}

export function TaskDrawer({task,token,onClose,onUpdated}:{task:Task;token:string;onClose:()=>void;onUpdated:(task:Task)=>void}) {
  const [title,setTitle]=useState(task.title)
  const [description,setDescription]=useState(task.description)
  const [priority,setPriority]=useState(task.priority)
  const [status,setStatus]=useState(task.status)
  const [dueDate,setDueDate]=useState(task.due_date?.slice(0,10)??'')
  const [saving,setSaving]=useState(false)
  const [error,setError]=useState('')
  const [assigneeToAdd,setAssigneeToAdd]=useState('')

  const comments=useQuery({queryKey:['comments',task.id],queryFn:()=>request<Comment[]>(`/api/v1/tasks/${task.id}/comments`,{},token)})
  const subtasks=useQuery({queryKey:['subtasks',task.id],queryFn:()=>request<Subtask[]>(`/api/v1/tasks/${task.id}/subtasks`,{},token)})
  const checklists=useQuery({queryKey:['checklists',task.id],queryFn:()=>request<Checklist[]>(`/api/v1/tasks/${task.id}/checklists`,{},token)})
  const assignees=useQuery({queryKey:['assignees',task.id],queryFn:()=>request<UserSummary[]>(`/api/v1/tasks/${task.id}/assignees`,{},token)})
  const members=useQuery({queryKey:['members',task.workspace_id],queryFn:()=>request<WorkspaceMember[]>(`/api/v1/workspaces/${task.workspace_id}/members`,{},token)})
  const time=useQuery({queryKey:['task-time',task.id],queryFn:()=>request<TimeSummary>(`/api/v1/tasks/${task.id}/time`,{},token)})
  const subtaskProgress=useMemo(()=>{const total=subtasks.data?.length??0;const done=subtasks.data?.filter(item=>item.status==='done').length??0;return {total,done,percentage:total?Math.round((done/total)*100):0}},[subtasks.data])
  const availableMembers=useMemo(()=>{const assigned=new Set(assignees.data?.map(item=>item.id)??[]);return members.data?.filter(member=>!assigned.has(member.user_id))??[]},[assignees.data,members.data])

  useEffect(()=>{setTitle(task.title);setDescription(task.description);setPriority(task.priority);setStatus(task.status);setDueDate(task.due_date?.slice(0,10)??'')},[task])

  async function save() {
    setSaving(true);setError('')
    try {
      const updated=await request<Task>(`/api/v1/tasks/${task.id}`,{method:'PATCH',body:JSON.stringify({version:task.version,title,description,priority,status,due_date:dueDate?new Date(`${dueDate}T12:00:00Z`).toISOString():null})},token)
      onUpdated(updated)
    } catch(e) { setError(e instanceof Error?e.message:'Could not save task') } finally { setSaving(false) }
  }
  async function addAssignee() {
    if(!assigneeToAdd)return
    await request<UserSummary>(`/api/v1/tasks/${task.id}/assignees`,{method:'POST',body:JSON.stringify({user_id:assigneeToAdd})},token)
    setAssigneeToAdd('')
    await assignees.refetch()
  }
  async function removeAssignee(userId:string) {
    await request<void>(`/api/v1/tasks/${task.id}/assignees/${userId}`,{method:'DELETE'},token)
    await assignees.refetch()
  }
  async function startTimer() {
    await request(`/api/v1/tasks/${task.id}/time/start`,{method:'POST'},token)
    await time.refetch()
  }
  async function stopTimer() {
    await request(`/api/v1/tasks/${task.id}/time/stop`,{method:'POST'},token)
    await time.refetch()
  }
  async function addSubtask(e:FormEvent<HTMLFormElement>) {e.preventDefault();const form=e.currentTarget;const data=new FormData(form);const subtaskTitle=String(data.get('title')??'').trim();if(!subtaskTitle)return;await request<Subtask>(`/api/v1/tasks/${task.id}/subtasks`,{method:'POST',body:JSON.stringify({title:subtaskTitle})},token);form.reset();await subtasks.refetch()}
  async function toggleSubtask(subtask:Subtask) {await request<Subtask>(`/api/v1/tasks/${task.id}/subtasks/${subtask.id}`,{method:'PATCH',body:JSON.stringify({version:subtask.version,status:subtask.status==='done'?'open':'done'})},token);await subtasks.refetch()}
  async function addChecklist(e:FormEvent<HTMLFormElement>) {e.preventDefault();const form=e.currentTarget;const data=new FormData(form);const checklistTitle=String(data.get('title')??'').trim();if(!checklistTitle)return;await request<Checklist>(`/api/v1/tasks/${task.id}/checklists`,{method:'POST',body:JSON.stringify({title:checklistTitle})},token);form.reset();await checklists.refetch()}
  async function addComment(e:FormEvent<HTMLFormElement>) {e.preventDefault();const form=e.currentTarget;const data=new FormData(form);const body=String(data.get('body')??'').trim();if(!body)return;await request<Comment>(`/api/v1/tasks/${task.id}/comments`,{method:'POST',body:JSON.stringify({body})},token);form.reset();await comments.refetch()}

  return <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onMouseDown={onClose}><aside className="h-full w-full max-w-2xl overflow-y-auto border-l border-[var(--line)] bg-[var(--panel)] p-5 sm:p-7" onMouseDown={e=>e.stopPropagation()}><div className="flex items-start justify-between gap-4"><div className="min-w-0 flex-1"><p className="text-sm font-medium muted">{task.identifier}</p><input value={title} onChange={e=>setTitle(e.target.value)} className="mt-1 w-full bg-transparent text-2xl font-semibold tracking-tight outline-none" aria-label="Task title"/></div><button onClick={onClose} className="rounded-xl border border-[var(--line)] p-2" aria-label="Close task"><X size={18}/></button></div>

    <div className="mt-6 grid gap-4 sm:grid-cols-3"><label className="text-sm font-medium">Priority<select value={priority} onChange={e=>setPriority(e.target.value as Task['priority'])} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5">{['urgent','high','medium','low','none'].map(p=><option key={p} value={p}>{p[0].toUpperCase()+p.slice(1)}</option>)}</select></label><label className="text-sm font-medium">Status<select value={status} onChange={e=>setStatus(e.target.value)} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5"><option value="open">Open</option><option value="in_progress">In progress</option><option value="review">Review</option><option value="done">Done</option></select></label><label className="text-sm font-medium">Due date<input type="date" value={dueDate} onChange={e=>setDueDate(e.target.value)} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5"/></label></div>

    <section className="mt-6 rounded-2xl border border-[var(--line)] p-4"><div className="flex items-center justify-between gap-3"><div><h2 className="flex items-center gap-2 font-semibold"><UserPlus size={17}/>Assignees</h2><p className="mt-1 text-xs muted">Assignments generate notifications automatically.</p></div></div><div className="mt-3 flex flex-wrap gap-2">{assignees.data?.map(person=><span key={person.id} className="flex items-center gap-2 rounded-full bg-black/5 py-1 pl-1 pr-2 text-xs dark:bg-white/5"><span className="grid h-6 w-6 place-items-center rounded-full bg-indigo-500/15 font-semibold text-indigo-600">{person.name.slice(0,2).toUpperCase()}</span>{person.name}<button onClick={()=>void removeAssignee(person.id)} aria-label={`Remove ${person.name}`} className="muted hover:text-red-600"><X size={13}/></button></span>)}</div><div className="mt-3 flex gap-2"><select value={assigneeToAdd} onChange={e=>setAssigneeToAdd(e.target.value)} className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm"><option value="">Add a member…</option>{availableMembers.map(member=><option key={member.user_id} value={member.user_id}>{member.name} · {member.role}</option>)}</select><button disabled={!assigneeToAdd} onClick={()=>void addAssignee()} className="rounded-xl border border-[var(--line)] px-3 text-sm font-medium disabled:opacity-40">Assign</button></div></section>

    <label className="mt-6 block text-sm font-medium">Description<textarea value={description} onChange={e=>setDescription(e.target.value)} rows={8} placeholder="Add context, acceptance criteria, links, or notes…" className="mt-2 w-full resize-y rounded-2xl border border-[var(--line)] bg-transparent p-4 leading-6 outline-none focus:border-indigo-500"/></label>{error&&<p className="mt-3 rounded-xl bg-red-500/10 p-3 text-sm text-red-600">{error}</p>}<div className="mt-4 flex justify-end"><button disabled={saving} onClick={()=>void save()} className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{saving?'Saving…':'Save changes'}</button></div>

    <section className="mt-10 border-t border-[var(--line)] pt-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="flex items-center gap-2 font-semibold"><Clock3 size={18}/>Time tracking</h2><p className="mt-1 text-xs muted">{formatDuration(time.data?.total_seconds??0)} tracked across this task</p></div>{time.data?.running_entry?<button onClick={()=>void stopTimer()} className="rounded-xl bg-red-500/10 px-3 py-2 text-sm font-semibold text-red-600">Stop timer</button>:<button onClick={()=>void startTimer()} className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-semibold">Start timer</button>}</div>{time.data?.running_entry&&<p className="mt-3 rounded-xl bg-indigo-500/10 p-3 text-sm text-indigo-700 dark:text-indigo-300">Timer running since {new Date(time.data.running_entry.started_at).toLocaleTimeString()}.</p>}<div className="mt-4 space-y-2">{time.data?.entries.filter(entry=>entry.ended_at).slice(0,5).map(entry=><div key={entry.id} className="flex items-center justify-between rounded-xl bg-black/[.025] px-3 py-2 text-sm dark:bg-white/[.025]"><span className="muted">{new Date(entry.started_at).toLocaleDateString()}</span><span className="font-medium">{formatDuration(entry.duration_seconds??0)}</span></div>)}</div></section>

    <section className="mt-10 border-t border-[var(--line)] pt-6"><div className="flex items-center justify-between gap-3"><div><h2 className="flex items-center gap-2 font-semibold"><CheckCircle2 size={18}/>Subtasks</h2><p className="mt-1 text-xs muted">{subtaskProgress.done} / {subtaskProgress.total} completed</p></div><span className="text-xs font-medium muted">{subtaskProgress.percentage}%</span></div><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-black/5 dark:bg-white/10"><div className="h-full rounded-full bg-indigo-600 transition-all" style={{width:`${subtaskProgress.percentage}%`}} /></div><div className="mt-4 space-y-1">{subtasks.data?.map(subtask=><button key={subtask.id} onClick={()=>void toggleSubtask(subtask)} className="flex w-full items-start gap-3 rounded-xl px-2 py-2.5 text-left hover:bg-black/[.035] dark:hover:bg-white/[.035]">{subtask.status==='done'?<CheckCircle2 size={18} className="mt-0.5 shrink-0 text-indigo-600"/>:<Circle size={18} className="mt-0.5 shrink-0 muted"/>}<span className={`text-sm ${subtask.status==='done'?'line-through muted':''}`}>{subtask.title}</span></button>)}{subtasks.isLoading&&<p className="text-sm muted">Loading subtasks…</p>}{subtasks.data?.length===0&&<p className="text-sm muted">Break this task into smaller steps.</p>}</div><form onSubmit={addSubtask} className="mt-3 flex gap-2"><input name="title" required maxLength={240} placeholder="Add a subtask" className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-transparent px-3 py-2.5 text-sm outline-none focus:border-indigo-500"/><button className="rounded-xl border border-[var(--line)] px-3" aria-label="Add subtask"><Plus size={17}/></button></form></section>

    <section className="mt-10 border-t border-[var(--line)] pt-6"><h2 className="flex items-center gap-2 font-semibold"><ListChecks size={18}/>Checklists</h2><div className="mt-4 space-y-4">{checklists.data?.map(checklist=><ChecklistSection key={checklist.id} taskId={task.id} checklist={checklist} token={token}/>)}</div>{checklists.data?.length===0&&<p className="mt-3 text-sm muted">Add a checklist for repeatable completion criteria.</p>}<form onSubmit={addChecklist} className="mt-4 flex gap-2"><input name="title" required maxLength={160} placeholder="Checklist title" className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-transparent px-3 py-2.5 text-sm outline-none focus:border-indigo-500"/><button className="rounded-xl border border-[var(--line)] px-3 text-sm font-medium">Add</button></form></section>

    <section className="mt-10 border-t border-[var(--line)] pt-6"><h2 className="flex items-center gap-2 font-semibold"><MessageSquare size={18}/>Discussion</h2><form onSubmit={addComment} className="mt-4"><textarea name="body" required rows={3} placeholder="Write a comment…" className="w-full rounded-2xl border border-[var(--line)] bg-transparent p-3 outline-none"/><div className="mt-2 flex justify-end"><button className="rounded-xl border border-[var(--line)] px-4 py-2 text-sm font-semibold">Comment</button></div></form><div className="mt-5 space-y-3">{comments.data?.map(comment=><article key={comment.id} className="rounded-2xl bg-black/[.035] p-4 dark:bg-white/[.035]"><div className="mb-2 flex items-center justify-between gap-3"><span className="text-xs font-medium muted">{comment.author_id.slice(0,8)}</span><time className="text-xs muted">{new Date(comment.created_at).toLocaleString()}</time></div><p className="whitespace-pre-wrap text-sm leading-6">{comment.body}</p></article>)}{comments.isLoading&&<p className="text-sm muted">Loading comments…</p>}{comments.data?.length===0&&<p className="text-sm muted">No comments yet.</p>}</div></section>
  </aside></div>
}
