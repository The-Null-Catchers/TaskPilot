'use client'

import { useQuery } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, CheckCircle2, Circle, Clock3, ExternalLink, Eye, ListChecks, Pencil, Plus, Tags, UserPlus, X } from 'lucide-react'
import { FormEvent, useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { CommentThread } from '@/components/comment-thread'
import { TaskCollaborationPanel } from '@/components/task-collaboration-panel'
import { Checklist, ChecklistItem, Label, request, Subtask, Task, TimeSummary, UserSummary, WorkspaceMember } from '@/lib/api'

function formatDuration(seconds:number) {
  const hours=Math.floor(seconds/3600)
  const minutes=Math.floor((seconds%3600)/60)
  if(hours)return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function ChecklistSection({taskId, checklist, token, members}:{taskId:string; checklist:Checklist; token:string; members:WorkspaceMember[]}) {
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
  async function assignItem(item:ChecklistItem,assigneeId:string) {
    await request<ChecklistItem>(`/api/v1/tasks/${taskId}/checklists/${checklist.id}/items/${item.id}`,{method:'PATCH',body:JSON.stringify({version:item.version,assignee_id:assigneeId||null})},token)
    await items.refetch()
  }
  async function moveItem(item:ChecklistItem,direction:-1|1) {
    const ordered=[...(items.data??[])].sort((a,b)=>a.position-b.position)
    const index=ordered.findIndex(candidate=>candidate.id===item.id)
    const other=ordered[index+direction]
    if(index<0||!other)return
    await Promise.all([
      request<ChecklistItem>(`/api/v1/tasks/${taskId}/checklists/${checklist.id}/items/${item.id}`,{method:'PATCH',body:JSON.stringify({version:item.version,position:other.position})},token),
      request<ChecklistItem>(`/api/v1/tasks/${taskId}/checklists/${checklist.id}/items/${other.id}`,{method:'PATCH',body:JSON.stringify({version:other.version,position:item.position})},token),
    ])
    await items.refetch()
  }

  const ordered=[...(items.data??[])].sort((a,b)=>a.position-b.position)
  return <section className="rounded-2xl border border-[var(--line)] p-4"><div className="flex items-center justify-between gap-3"><div><h3 className="font-medium">{checklist.title}</h3><p className="mt-0.5 text-xs muted">{completed} / {total} complete</p></div><span className="text-xs font-medium muted">{percentage}%</span></div><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-black/5 dark:bg-white/10"><div className="h-full rounded-full bg-indigo-600 transition-all" style={{width:`${percentage}%`}} /></div><div className="mt-4 space-y-2">{ordered.map((item,index)=><div key={item.id} className="rounded-xl border border-[var(--line)] p-2"><div className="flex items-start gap-2"><button type="button" onClick={()=>void toggleItem(item)} className="mt-1 rounded-lg p-1" aria-label={item.completed?'Mark incomplete':'Mark complete'}>{item.completed?<CheckCircle2 size={18} className="text-indigo-600"/>:<Circle size={18} className="muted"/>}</button><div className="min-w-0 flex-1"><p className={`text-sm leading-5 ${item.completed?'line-through muted':''}`}>{item.title}</p><select value={item.assignee_id??''} onChange={e=>void assignItem(item,e.target.value)} className="mt-2 w-full rounded-lg border border-[var(--line)] bg-[var(--panel)] px-2 py-1.5 text-xs"><option value="">Unassigned</option>{members.map(member=><option key={member.user_id} value={member.user_id}>{member.name}</option>)}</select></div><div className="flex shrink-0 flex-col"><button type="button" disabled={index===0} onClick={()=>void moveItem(item,-1)} className="rounded-lg p-1.5 disabled:opacity-25" aria-label="Move item up"><ArrowUp size={14}/></button><button type="button" disabled={index===ordered.length-1} onClick={()=>void moveItem(item,1)} className="rounded-lg p-1.5 disabled:opacity-25" aria-label="Move item down"><ArrowDown size={14}/></button></div></div></div>)}{items.isLoading&&<p className="px-2 text-sm muted">Loading checklist…</p>}</div><form onSubmit={addItem} className="mt-3 flex gap-2"><input name="title" required maxLength={240} placeholder="Add checklist item" className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-transparent px-3 py-2 text-sm outline-none focus:border-indigo-500"/><button className="rounded-xl border border-[var(--line)] px-3 py-2" aria-label="Add checklist item"><Plus size={16}/></button></form></section>
}

export function TaskDrawer({task,token,onClose,onUpdated}:{task:Task;token:string;onClose:()=>void;onUpdated:(task:Task)=>void}) {
  const [title,setTitle]=useState(task.title)
  const [description,setDescription]=useState(task.description)
  const [priority,setPriority]=useState(task.priority)
  const [status,setStatus]=useState(task.status)
  const [dueDate,setDueDate]=useState(task.due_date?.slice(0,10)??'')
  const [saving,setSaving]=useState(false)
  const [descriptionPreview,setDescriptionPreview]=useState(false)
  const [error,setError]=useState('')
  const [assigneeToAdd,setAssigneeToAdd]=useState('')
  const [labelToAdd,setLabelToAdd]=useState('')
  const [newLabelName,setNewLabelName]=useState('')

  const subtasks=useQuery({queryKey:['subtasks',task.id],queryFn:()=>request<Subtask[]>(`/api/v1/tasks/${task.id}/subtasks`,{},token)})
  const workspaceLabels=useQuery({queryKey:['workspace-labels',task.workspace_id],queryFn:()=>request<Label[]>(`/api/v1/workspaces/${task.workspace_id}/labels`,{},token)})
  const taskLabels=useQuery({queryKey:['task-labels',task.id],queryFn:()=>request<Label[]>(`/api/v1/tasks/${task.id}/labels`,{},token)})
  const checklists=useQuery({queryKey:['checklists',task.id],queryFn:()=>request<Checklist[]>(`/api/v1/tasks/${task.id}/checklists`,{},token)})
  const assignees=useQuery({queryKey:['assignees',task.id],queryFn:()=>request<UserSummary[]>(`/api/v1/tasks/${task.id}/assignees`,{},token)})
  const members=useQuery({queryKey:['members',task.workspace_id],queryFn:()=>request<WorkspaceMember[]>(`/api/v1/workspaces/${task.workspace_id}/members`,{},token)})
  const time=useQuery({queryKey:['task-time',task.id],queryFn:()=>request<TimeSummary>(`/api/v1/tasks/${task.id}/time`,{},token)})
  const subtaskProgress=useMemo(()=>{const total=subtasks.data?.length??0;const done=subtasks.data?.filter(item=>item.status==='done').length??0;return {total,done,percentage:total?Math.round((done/total)*100):0}},[subtasks.data])
  const availableMembers=useMemo(()=>{const assigned=new Set(assignees.data?.map(item=>item.id)??[]);return members.data?.filter(member=>!assigned.has(member.user_id))??[]},[assignees.data,members.data])
  const availableLabels=useMemo(()=>{const selected=new Set(taskLabels.data?.map(item=>item.id)??[]);return workspaceLabels.data?.filter(label=>!selected.has(label.id))??[]},[taskLabels.data,workspaceLabels.data])

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
  async function addLabel() {if(!labelToAdd)return;await request<Label>(`/api/v1/tasks/${task.id}/labels`,{method:'POST',body:JSON.stringify({label_id:labelToAdd})},token);setLabelToAdd('');await taskLabels.refetch()}
  async function removeLabel(labelId:string) {await request<void>(`/api/v1/tasks/${task.id}/labels/${labelId}`,{method:'DELETE'},token);await taskLabels.refetch()}
  async function createLabel(e:FormEvent<HTMLFormElement>) {e.preventDefault();const name=newLabelName.trim();if(!name)return;const created=await request<Label>(`/api/v1/workspaces/${task.workspace_id}/labels`,{method:'POST',body:JSON.stringify({name,color:'#64748b'})},token);setNewLabelName('');await workspaceLabels.refetch();await request<Label>(`/api/v1/tasks/${task.id}/labels`,{method:'POST',body:JSON.stringify({label_id:created.id})},token);await taskLabels.refetch()}
  async function convertSubtask(subtaskId:string) {await request<Task>(`/api/v1/tasks/${task.id}/subtasks/${subtaskId}/convert`,{method:'POST',body:JSON.stringify({})},token);await subtasks.refetch()}

  return <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onMouseDown={onClose}><aside className="h-full w-full max-w-2xl overflow-y-auto border-l border-[var(--line)] bg-[var(--panel)] p-5 sm:p-7" onMouseDown={e=>e.stopPropagation()}><div className="flex items-start justify-between gap-4"><div className="min-w-0 flex-1"><p className="text-sm font-medium muted">{task.identifier}</p><input value={title} onChange={e=>setTitle(e.target.value)} className="mt-1 w-full bg-transparent text-2xl font-semibold tracking-tight outline-none" aria-label="Task title"/></div><button onClick={onClose} className="rounded-xl border border-[var(--line)] p-2" aria-label="Close task"><X size={18}/></button></div>

    <div className="mt-6 grid gap-4 sm:grid-cols-3"><label className="text-sm font-medium">Priority<select value={priority} onChange={e=>setPriority(e.target.value as Task['priority'])} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5">{['urgent','high','medium','low','none'].map(p=><option key={p} value={p}>{p[0].toUpperCase()+p.slice(1)}</option>)}</select></label><label className="text-sm font-medium">Status<select value={status} onChange={e=>setStatus(e.target.value)} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5"><option value="open">Open</option><option value="in_progress">In progress</option><option value="review">Review</option><option value="done">Done</option></select></label><label className="text-sm font-medium">Due date<input type="date" value={dueDate} onChange={e=>setDueDate(e.target.value)} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5"/></label></div>

    <section className="mt-6 rounded-2xl border border-[var(--line)] p-4"><div className="flex items-center justify-between gap-3"><div><h2 className="flex items-center gap-2 font-semibold"><UserPlus size={17}/>Assignees</h2><p className="mt-1 text-xs muted">Assignments generate notifications automatically.</p></div></div><div className="mt-3 flex flex-wrap gap-2">{assignees.data?.map(person=><span key={person.id} className="flex items-center gap-2 rounded-full bg-black/5 py-1 pl-1 pr-2 text-xs dark:bg-white/5"><span className="grid h-6 w-6 place-items-center rounded-full bg-indigo-500/15 font-semibold text-indigo-600">{person.name.slice(0,2).toUpperCase()}</span>{person.name}<button onClick={()=>void removeAssignee(person.id)} aria-label={`Remove ${person.name}`} className="muted hover:text-red-600"><X size={13}/></button></span>)}</div><div className="mt-3 flex gap-2"><select value={assigneeToAdd} onChange={e=>setAssigneeToAdd(e.target.value)} className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm"><option value="">Add a member…</option>{availableMembers.map(member=><option key={member.user_id} value={member.user_id}>{member.name} · {member.role}</option>)}</select><button disabled={!assigneeToAdd} onClick={()=>void addAssignee()} className="rounded-xl border border-[var(--line)] px-3 text-sm font-medium disabled:opacity-40">Assign</button></div></section>

    <section className="mt-6 rounded-2xl border border-[var(--line)] p-4"><div className="flex items-center gap-2"><Tags size={17}/><div><h2 className="font-semibold">Labels</h2><p className="mt-1 text-xs muted">Categorize and filter this task across project views.</p></div></div><div className="mt-3 flex flex-wrap gap-2">{taskLabels.data?.map(label=><span key={label.id} className="inline-flex items-center gap-2 rounded-full border border-[var(--line)] px-2.5 py-1 text-xs"><span className="h-2.5 w-2.5 rounded-full" style={{backgroundColor:label.color}}/>{label.name}<button type="button" onClick={()=>void removeLabel(label.id)} aria-label={`Remove ${label.name}`}><X size={12}/></button></span>)}{!taskLabels.isLoading&&taskLabels.data?.length===0&&<span className="text-sm muted">No labels yet.</span>}</div><div className="mt-3 flex gap-2"><select value={labelToAdd} onChange={e=>setLabelToAdd(e.target.value)} className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm"><option value="">Add existing label…</option>{availableLabels.map(label=><option key={label.id} value={label.id}>{label.name}</option>)}</select><button type="button" disabled={!labelToAdd} onClick={()=>void addLabel()} className="rounded-xl border border-[var(--line)] px-3 text-sm disabled:opacity-40">Add</button></div><form onSubmit={createLabel} className="mt-2 flex gap-2"><input value={newLabelName} onChange={e=>setNewLabelName(e.target.value)} maxLength={80} placeholder="Create new label" className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-transparent px-3 py-2 text-sm"/><button disabled={!newLabelName.trim()} className="rounded-xl border border-[var(--line)] px-3 text-sm disabled:opacity-40">Create</button></form></section>

    <section className="mt-6"><div className="flex items-center justify-between gap-3"><div><h2 className="text-sm font-medium">Description</h2><p className="mt-1 text-xs muted">GitHub-flavored Markdown is supported. Raw HTML is ignored.</p></div><button type="button" onClick={()=>setDescriptionPreview(value=>!value)} className="flex items-center gap-2 rounded-xl border border-[var(--line)] px-3 py-2 text-xs font-medium">{descriptionPreview?<><Pencil size={14}/>Edit</>:<><Eye size={14}/>Preview</>}</button></div>{descriptionPreview?<div className="mt-2 min-h-48 rounded-2xl border border-[var(--line)] bg-black/[.015] p-4 text-sm leading-7 dark:bg-white/[.02]"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{a:({node,...props})=><a {...props} target="_blank" rel="noopener noreferrer" className="text-indigo-600 underline underline-offset-2"/>,h1:({node,...props})=><h1 {...props} className="mb-3 mt-4 text-2xl font-semibold"/>,h2:({node,...props})=><h2 {...props} className="mb-2 mt-4 text-xl font-semibold"/>,h3:({node,...props})=><h3 {...props} className="mb-2 mt-3 text-lg font-semibold"/>,p:({node,...props})=><p {...props} className="my-2"/>,ul:({node,...props})=><ul {...props} className="my-2 list-disc pl-6"/>,ol:({node,...props})=><ol {...props} className="my-2 list-decimal pl-6"/>,blockquote:({node,...props})=><blockquote {...props} className="my-3 border-l-4 border-indigo-500/40 pl-4 muted"/>,code:({node,...props})=><code {...props} className="rounded bg-black/5 px-1 py-0.5 font-mono text-[.92em] dark:bg-white/10"/>,table:({node,...props})=><div className="my-3 overflow-x-auto"><table {...props} className="w-full border-collapse text-left"/></div>,th:({node,...props})=><th {...props} className="border border-[var(--line)] bg-black/[.025] px-3 py-2 font-semibold dark:bg-white/[.035]"/>,td:({node,...props})=><td {...props} className="border border-[var(--line)] px-3 py-2"/>}}>{description || '*No description yet.*'}</ReactMarkdown></div>:<textarea value={description} onChange={e=>setDescription(e.target.value)} rows={8} placeholder="Add context, acceptance criteria, links, or notes…" className="mt-2 w-full resize-y rounded-2xl border border-[var(--line)] bg-transparent p-4 font-mono text-sm leading-6 outline-none focus:border-indigo-500"/>}</section>{error&&<p className="mt-3 rounded-xl bg-red-500/10 p-3 text-sm text-red-600">{error}</p>}<div className="mt-4 flex justify-end"><button disabled={saving} onClick={()=>void save()} className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{saving?'Saving…':'Save changes'}</button></div>

    <section className="mt-10 border-t border-[var(--line)] pt-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="flex items-center gap-2 font-semibold"><Clock3 size={18}/>Time tracking</h2><p className="mt-1 text-xs muted">{formatDuration(time.data?.total_seconds??0)} tracked across this task</p></div>{time.data?.running_entry?<button onClick={()=>void stopTimer()} className="rounded-xl bg-red-500/10 px-3 py-2 text-sm font-semibold text-red-600">Stop timer</button>:<button onClick={()=>void startTimer()} className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-semibold">Start timer</button>}</div>{time.data?.running_entry&&<p className="mt-3 rounded-xl bg-indigo-500/10 p-3 text-sm text-indigo-700 dark:text-indigo-300">Timer running since {new Date(time.data.running_entry.started_at).toLocaleTimeString()}.</p>}<div className="mt-4 space-y-2">{time.data?.entries.filter(entry=>entry.ended_at).slice(0,5).map(entry=><div key={entry.id} className="flex items-center justify-between rounded-xl bg-black/[.025] px-3 py-2 text-sm dark:bg-white/[.025]"><span className="muted">{new Date(entry.started_at).toLocaleDateString()}</span><span className="font-medium">{formatDuration(entry.duration_seconds??0)}</span></div>)}</div></section>

    <section className="mt-10 border-t border-[var(--line)] pt-6"><div className="flex items-center justify-between gap-3"><div><h2 className="flex items-center gap-2 font-semibold"><CheckCircle2 size={18}/>Subtasks</h2><p className="mt-1 text-xs muted">{subtaskProgress.done} / {subtaskProgress.total} completed</p></div><span className="text-xs font-medium muted">{subtaskProgress.percentage}%</span></div><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-black/5 dark:bg-white/10"><div className="h-full rounded-full bg-indigo-600 transition-all" style={{width:`${subtaskProgress.percentage}%`}} /></div><div className="mt-4 space-y-1">{subtasks.data?.map(subtask=><div key={subtask.id} className="flex items-start gap-2 rounded-xl px-2 py-2 hover:bg-black/[.035] dark:hover:bg-white/[.035]"><button type="button" onClick={()=>void toggleSubtask(subtask)} className="mt-0.5 shrink-0" aria-label={subtask.status==='done'?'Mark subtask open':'Complete subtask'}>{subtask.status==='done'?<CheckCircle2 size={18} className="text-indigo-600"/>:<Circle size={18} className="muted"/>}</button><span className={`min-w-0 flex-1 text-sm ${subtask.status==='done'?'line-through muted':''}`}>{subtask.title}</span><button type="button" onClick={()=>void convertSubtask(subtask.id)} className="rounded-lg p-1.5 muted hover:bg-black/5 hover:text-indigo-600 dark:hover:bg-white/10" aria-label="Convert subtask to task" title="Convert to task"><ExternalLink size={15}/></button></div>)}{subtasks.isLoading&&<p className="text-sm muted">Loading subtasks…</p>}{subtasks.data?.length===0&&<p className="text-sm muted">Break this task into smaller steps.</p>}</div><form onSubmit={addSubtask} className="mt-3 flex gap-2"><input name="title" required maxLength={240} placeholder="Add a subtask" className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-transparent px-3 py-2.5 text-sm outline-none focus:border-indigo-500"/><button className="rounded-xl border border-[var(--line)] px-3" aria-label="Add subtask"><Plus size={17}/></button></form></section>

    <section className="mt-10 border-t border-[var(--line)] pt-6"><h2 className="flex items-center gap-2 font-semibold"><ListChecks size={18}/>Checklists</h2><div className="mt-4 space-y-4">{checklists.data?.map(checklist=><ChecklistSection key={checklist.id} taskId={task.id} checklist={checklist} token={token} members={members.data??[]}/>)}</div>{checklists.data?.length===0&&<p className="mt-3 text-sm muted">Add a checklist for repeatable completion criteria.</p>}<form onSubmit={addChecklist} className="mt-4 flex gap-2"><input name="title" required maxLength={160} placeholder="Checklist title" className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-transparent px-3 py-2.5 text-sm outline-none focus:border-indigo-500"/><button className="rounded-xl border border-[var(--line)] px-3 text-sm font-medium">Add</button></form></section>

    <TaskCollaborationPanel task={task} token={token}/>

    <CommentThread task={task} token={token}/>
  </aside></div>
}
