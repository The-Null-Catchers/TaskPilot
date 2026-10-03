'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, ArrowLeft, RotateCcw, Save, UserMinus, UserPlus, Users } from 'lucide-react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { FormEvent, useEffect, useMemo, useState } from 'react'

import { useAuth } from '@/components/providers'
import { Board, Project, request, WorkspaceMember } from '@/lib/api'

type ProjectPreferences={
  default_task_priority:'urgent'|'high'|'medium'|'low'|'none'
  time_tracking_enabled:boolean
  auto_complete_on_done_column:boolean
  show_completed_tasks:boolean
  updated_at:string
}

type ProjectMember={
  user_id:string
  email:string
  name:string
  role:'owner'|'member'|'guest'
  created_at:string
}

const statuses = [
  ['planning', 'Planning'],
  ['active', 'Active'],
  ['on_hold', 'On hold'],
  ['completed', 'Completed'],
] as const

export default function ProjectSettingsPage(){
  const {projectId}=useParams<{projectId:string}>()
  const {user,token,loading}=useAuth()
  const router=useRouter()
  const queryClient=useQueryClient()
  const [notice,setNotice]=useState('')
  const [error,setError]=useState('')
  const [memberToAdd,setMemberToAdd]=useState('')
  const [memberRole,setMemberRole]=useState<'member'|'guest'>('member')
  const [memberBusy,setMemberBusy]=useState('')

  useEffect(()=>{if(!loading&&!token)router.replace('/login')},[loading,token,router])

  const board=useQuery({
    queryKey:['board',projectId],
    queryFn:()=>request<Board>(`/api/v1/projects/${projectId}/board`,{},token),
    enabled:!!token&&!!projectId,
  })
  const project=board.data?.project
  const preferences=useQuery({
    queryKey:['project-settings-preferences',projectId],
    queryFn:()=>request<ProjectPreferences>(`/api/v1/projects/${projectId}/settings/preferences`,{},token),
    enabled:!!token&&!!projectId,
  })
  const projectMembers=useQuery({
    queryKey:['project-members',projectId],
    queryFn:()=>request<ProjectMember[]>(`/api/v1/projects/${projectId}/members`,{},token),
    enabled:!!token&&!!projectId,
  })
  const workspaceMembers=useQuery({
    queryKey:['workspace-members',project?.workspace_id],
    queryFn:()=>request<WorkspaceMember[]>(`/api/v1/workspaces/${project!.workspace_id}/members`,{},token),
    enabled:!!token&&!!project?.workspace_id,
  })

  const actorWorkspaceRole=workspaceMembers.data?.find(member=>member.user_id===user?.id)?.role
  const canManageMembers=!!project&&!!user&&(project.owner_id===user.id||actorWorkspaceRole==='owner'||actorWorkspaceRole==='admin')
  const availableMembers=useMemo(()=>{
    const assigned=new Set(projectMembers.data?.map(member=>member.user_id)??[])
    return (workspaceMembers.data??[]).filter(member=>!assigned.has(member.user_id))
  },[projectMembers.data,workspaceMembers.data])

  const save=useMutation({
    mutationFn:(payload:Record<string,unknown>)=>request<Project>(`/api/v1/projects/${projectId}`,{
      method:'PATCH',
      body:JSON.stringify(payload),
    },token),
    onSuccess:async()=>{
      setError('');setNotice('Project settings saved.')
      await Promise.all([
        queryClient.invalidateQueries({queryKey:['board',projectId]}),
        queryClient.invalidateQueries({queryKey:['projects']}),
        queryClient.invalidateQueries({queryKey:['project-overview',projectId]}),
      ])
    },
    onError:(err)=>{setNotice('');setError(err instanceof Error?err.message:'Could not save project settings.')},
  })

  const savePreferences=useMutation({
    mutationFn:(payload:Partial<ProjectPreferences>)=>request<ProjectPreferences>(`/api/v1/projects/${projectId}/settings/preferences`,{
      method:'PATCH',
      body:JSON.stringify(payload),
    },token),
    onSuccess:async()=>{setError('');setNotice('Project defaults saved.');await preferences.refetch()},
    onError:(err)=>{setNotice('');setError(err instanceof Error?err.message:'Could not save project defaults.')},
  })

  async function submit(event:FormEvent<HTMLFormElement>){
    event.preventDefault()
    if(!project)return
    const data=new FormData(event.currentTarget)
    const value=(name:string)=>String(data.get(name)??'').trim()
    await save.mutateAsync({
      name:value('name'),
      description:value('description'),
      icon:value('icon')||null,
      color:value('color'),
      status:value('status'),
      start_date:value('start_date')||null,
      due_date:value('due_date')||null,
    }).catch(()=>undefined)
  }

  async function submitPreferences(event:FormEvent<HTMLFormElement>){
    event.preventDefault()
    const data=new FormData(event.currentTarget)
    await savePreferences.mutateAsync({
      default_task_priority:String(data.get('default_task_priority')) as ProjectPreferences['default_task_priority'],
      time_tracking_enabled:data.get('time_tracking_enabled')==='on',
      auto_complete_on_done_column:data.get('auto_complete_on_done_column')==='on',
      show_completed_tasks:data.get('show_completed_tasks')==='on',
    }).catch(()=>undefined)
  }

  async function addMember(){
    if(!memberToAdd||!canManageMembers)return
    setMemberBusy(`add:${memberToAdd}`);setError('');setNotice('')
    try{
      await request<ProjectMember>(`/api/v1/projects/${projectId}/members`,{
        method:'POST',
        body:JSON.stringify({user_id:memberToAdd,role:memberRole}),
      },token)
      setMemberToAdd('');setMemberRole('member');setNotice('Project member added.')
      await projectMembers.refetch()
    }catch(err){setError(err instanceof Error?err.message:'Could not add project member.')}
    finally{setMemberBusy('')}
  }

  async function changeMemberRole(member:ProjectMember,role:'member'|'guest'){
    if(!canManageMembers||member.role==='owner')return
    setMemberBusy(`role:${member.user_id}`);setError('');setNotice('')
    try{
      await request<ProjectMember>(`/api/v1/projects/${projectId}/members`,{
        method:'POST',
        body:JSON.stringify({user_id:member.user_id,role}),
      },token)
      setNotice(`${member.name}'s project role was updated.`)
      await projectMembers.refetch()
    }catch(err){setError(err instanceof Error?err.message:'Could not update project member.')}
    finally{setMemberBusy('')}
  }

  async function removeMember(member:ProjectMember){
    if(!canManageMembers||member.role==='owner'||!confirm(`Remove ${member.name} from this project?`))return
    setMemberBusy(`remove:${member.user_id}`);setError('');setNotice('')
    try{
      await request<void>(`/api/v1/projects/${projectId}/members/${member.user_id}`,{method:'DELETE'},token)
      setNotice(`${member.name} was removed from this project.`)
      await projectMembers.refetch()
    }catch(err){setError(err instanceof Error?err.message:'Could not remove project member.')}
    finally{setMemberBusy('')}
  }

  async function archive(){
    if(!project||!confirm(`Archive ${project.name}? It will disappear from active project lists until restored.`))return
    setError('');setNotice('')
    try{
      await request<Project>(`/api/v1/projects/${projectId}/archive`,{method:'POST'},token)
      await queryClient.invalidateQueries({queryKey:['projects']})
      router.push('/app')
    }catch(err){setError(err instanceof Error?err.message:'Could not archive project.')}
  }

  async function restore(){
    setError('');setNotice('')
    try{
      await request<Project>(`/api/v1/projects/${projectId}/restore`,{method:'POST'},token)
      setNotice('Project restored.')
      await Promise.all([
        queryClient.invalidateQueries({queryKey:['board',projectId]}),
        queryClient.invalidateQueries({queryKey:['projects']}),
      ])
    }catch(err){setError(err instanceof Error?err.message:'Could not restore project.')}
  }

  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading project settings…</div>
  if(board.isLoading)return <div className="grid min-h-screen place-items-center muted">Loading project…</div>
  if(board.isError||!project)return <div className="grid min-h-screen place-items-center text-red-600">Could not load project settings.</div>

  const archived=project.archived_at!==null

  return <main className="min-h-screen bg-[var(--bg)]">
    <header className="border-b border-[var(--line)] bg-[var(--panel)]">
      <div className="mx-auto flex h-16 max-w-4xl items-center gap-3 px-4 sm:px-6">
        <Link href={`/app/projects/${projectId}/overview`} className="rounded-xl border border-[var(--line)] p-2" aria-label="Back to project"><ArrowLeft size={18}/></Link>
        <div><p className="text-xs muted">{project.key}</p><h1 className="font-semibold">Project settings</h1></div>
      </div>
    </header>

    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      {notice&&<div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">{notice}</div>}
      {error&&<div role="alert" className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</div>}

      <form onSubmit={submit} className="panel rounded-2xl p-5 sm:p-6">
        <div><h2 className="text-lg font-semibold">Project details</h2><p className="mt-1 text-sm muted">Identity, schedule, and lifecycle status are enforced by the project management API.</p></div>
        <div className="mt-6 grid gap-5 sm:grid-cols-2">
          <label className="sm:col-span-2"><span className="mb-2 block text-sm font-medium">Name</span><input name="name" required minLength={2} maxLength={160} defaultValue={project.name} disabled={archived} className="w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-2.5"/></label>
          <label><span className="mb-2 block text-sm font-medium">Icon</span><input name="icon" maxLength={32} defaultValue={project.icon??''} disabled={archived} placeholder="rocket" className="w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-2.5"/></label>
          <label><span className="mb-2 block text-sm font-medium">Color</span><div className="flex gap-2"><input name="color" type="color" defaultValue={project.color} disabled={archived} className="h-11 w-14 rounded-xl border border-[var(--line)] bg-transparent p-1"/><input readOnly value={project.color} className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-transparent px-3 py-2.5 text-sm muted"/></div></label>
          <label><span className="mb-2 block text-sm font-medium">Status</span><select name="status" defaultValue={project.status==='archived'?'active':project.status} disabled={archived} className="w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5">{statuses.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
          <div/>
          <label><span className="mb-2 block text-sm font-medium">Start date</span><input name="start_date" type="date" defaultValue={project.start_date??''} disabled={archived} className="w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-2.5"/></label>
          <label><span className="mb-2 block text-sm font-medium">Due date</span><input name="due_date" type="date" defaultValue={project.due_date??''} disabled={archived} className="w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-2.5"/></label>
          <label className="sm:col-span-2"><span className="mb-2 block text-sm font-medium">Description</span><textarea name="description" rows={7} maxLength={10000} defaultValue={project.description} disabled={archived} className="w-full resize-y rounded-xl border border-[var(--line)] bg-transparent px-3 py-2.5"/></label>
        </div>
        {!archived&&<div className="mt-6 flex justify-end"><button disabled={save.isPending} className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"><Save size={16}/>{save.isPending?'Saving…':'Save changes'}</button></div>}
      </form>

      <section className="panel rounded-2xl p-5 sm:p-6">
        <div className="flex items-start gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-indigo-500/10 text-indigo-600"><Users size={19}/></span><div><h2 className="text-lg font-semibold">Project members</h2><p className="mt-1 text-sm muted">Project membership controls guest visibility and project-specific access. Members must already belong to the workspace.</p></div></div>
        {projectMembers.isLoading?<p className="mt-5 text-sm muted">Loading project members…</p>:<div className="mt-5 divide-y divide-[var(--line)]">{projectMembers.data?.map(member=><div key={member.user_id} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center"><div className="min-w-0 flex-1"><p className="truncate font-medium">{member.name}</p><p className="truncate text-sm muted">{member.email}</p></div><div className="flex items-center gap-2">{member.role==='owner'?<span className="rounded-full border border-[var(--line)] px-3 py-1.5 text-xs font-medium">Owner</span>:canManageMembers&&!archived?<><select value={member.role} disabled={!!memberBusy} onChange={event=>void changeMemberRole(member,event.target.value as 'member'|'guest')} className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm"><option value="member">Member</option><option value="guest">Guest</option></select><button disabled={!!memberBusy} onClick={()=>void removeMember(member)} className="rounded-xl border border-red-500/20 p-2 text-red-600 disabled:opacity-40" aria-label={`Remove ${member.name}`}><UserMinus size={16}/></button></>:<span className="rounded-full border border-[var(--line)] px-3 py-1.5 text-xs muted">{member.role==='guest'?'Guest':'Member'}</span>}</div></div>)}</div>}
        {canManageMembers&&!archived&&<div className="mt-5 grid gap-3 rounded-xl border border-[var(--line)] p-4 sm:grid-cols-[1fr_140px_auto]"><select value={memberToAdd} onChange={event=>setMemberToAdd(event.target.value)} className="min-w-0 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5 text-sm"><option value="">Select workspace member…</option>{availableMembers.map(member=><option key={member.user_id} value={member.user_id}>{member.name} · {member.email}</option>)}</select><select value={memberRole} onChange={event=>setMemberRole(event.target.value as 'member'|'guest')} className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5 text-sm"><option value="member">Member</option><option value="guest">Guest</option></select><button type="button" onClick={()=>void addMember()} disabled={!memberToAdd||!!memberBusy} className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"><UserPlus size={16}/>Add member</button></div>}
        {canManageMembers&&availableMembers.length===0&&!projectMembers.isLoading&&<p className="mt-4 text-xs muted">Every active workspace member is already assigned to this project.</p>}
      </section>

      {preferences.data&&<form onSubmit={submitPreferences} className="panel rounded-2xl p-5 sm:p-6">
        <div><h2 className="text-lg font-semibold">Project defaults</h2><p className="mt-1 text-sm muted">Control defaults and behavior that apply specifically to this project.</p></div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-medium">Default task priority<select name="default_task_priority" defaultValue={preferences.data.default_task_priority} disabled={archived} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5">{['none','low','medium','high','urgent'].map(priority=><option key={priority} value={priority}>{priority[0].toUpperCase()+priority.slice(1)}</option>)}</select></label>
          <div className="grid gap-3 rounded-xl border border-[var(--line)] p-4">
            <label className="flex items-center justify-between gap-3 text-sm"><span>Time tracking</span><input type="checkbox" name="time_tracking_enabled" defaultChecked={preferences.data.time_tracking_enabled} disabled={archived}/></label>
            <label className="flex items-center justify-between gap-3 text-sm"><span>Auto-complete tasks moved to Done</span><input type="checkbox" name="auto_complete_on_done_column" defaultChecked={preferences.data.auto_complete_on_done_column} disabled={archived}/></label>
            <label className="flex items-center justify-between gap-3 text-sm"><span>Show completed tasks</span><input type="checkbox" name="show_completed_tasks" defaultChecked={preferences.data.show_completed_tasks} disabled={archived}/></label>
          </div>
        </div>
        {!archived&&<div className="mt-5 flex justify-end"><button disabled={savePreferences.isPending} className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"><Save size={16}/>{savePreferences.isPending?'Saving…':'Save defaults'}</button></div>}
      </form>}

      <section className="rounded-2xl border border-amber-500/25 bg-amber-500/5 p-5 sm:p-6">
        <h2 className="font-semibold">{archived?'Archived project':'Archive project'}</h2>
        <p className="mt-1 text-sm muted">{archived?'Restore this project to make it editable and visible in active project lists.':'Archive instead of deleting collaboration history. Tasks, files, and activity remain preserved.'}</p>
        {archived
          ? <button onClick={()=>void restore()} className="mt-4 inline-flex items-center gap-2 rounded-xl border border-[var(--line)] px-4 py-2.5 text-sm font-semibold"><RotateCcw size={16}/>Restore project</button>
          : <button onClick={()=>void archive()} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white"><Archive size={16}/>Archive project</button>}
      </section>
    </div>
  </main>
}
