'use client'

import { useQuery } from '@tanstack/react-query'
import { Archive, ArrowLeft, Copy, Crown, LogOut, RefreshCw, Trash2, UserMinus, Users } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { FormEvent, useEffect, useMemo, useState } from 'react'

import { useAuth } from '@/components/providers'
import { request, Workspace, WorkspaceMember } from '@/lib/api'

type ArchivedWorkspace = Workspace & {
  archived_at:string
  archived_by_id:string|null
  updated_at:string
}
type Invitation = {
  id:string
  workspace_id:string
  email:string
  role:'admin'|'member'|'guest'
  expires_at:string
  accepted_at:string|null
  delivery_status:'pending'|'sent'|'failed'
  delivered_at:string|null
  created_at:string
}
type CreatedInvitation = Invitation & { token:string }

function roleLabel(role:string){ return role.charAt(0).toUpperCase()+role.slice(1) }

export default function WorkspaceSettingsPage(){
  const {user,token,loading}=useAuth()
  const router=useRouter()
  const [selectedId,setSelectedId]=useState('')
  const [busy,setBusy]=useState('')
  const [notice,setNotice]=useState('')
  const [error,setError]=useState('')
  const [inviteLink,setInviteLink]=useState('')

  useEffect(()=>{ if(!loading&&!token) router.replace('/login?next=%2Fapp%2Fsettings%2Fworkspaces') },[loading,token,router])

  const active=useQuery({
    queryKey:['workspaces'],
    queryFn:()=>request<Workspace[]>('/api/v1/workspaces',{},token),
    enabled:!!token,
  })
  const archived=useQuery({
    queryKey:['workspaces','archived'],
    queryFn:()=>request<ArchivedWorkspace[]>('/api/v1/workspaces/archived',{},token),
    enabled:!!token,
  })

  const all=useMemo(()=>[...(active.data??[]),...(archived.data??[])],[active.data,archived.data])
  useEffect(()=>{
    if(selectedId&&all.some(workspace=>workspace.id===selectedId))return
    const requested=typeof window==='undefined'?null:new URLSearchParams(window.location.search).get('workspace')
    const next=(requested&&all.some(workspace=>workspace.id===requested)?requested:null)??all[0]?.id??''
    if(next!==selectedId)setSelectedId(next)
  },[all,selectedId])

  const selected=all.find(workspace=>workspace.id===selectedId)
  const archivedWorkspace=archived.data?.find(workspace=>workspace.id===selectedId)
  const isArchived=!!archivedWorkspace
  const members=useQuery({
    queryKey:['workspace-members',selectedId],
    queryFn:()=>request<WorkspaceMember[]>(`/api/v1/workspaces/${selectedId}/members`,{},token),
    enabled:!!token&&!!selectedId,
  })
  const actorRole=members.data?.find(member=>member.user_id===user?.id)?.role
  const canManage=!isArchived&&(actorRole==='owner'||actorRole==='admin')
  const invitations=useQuery({
    queryKey:['workspace-invitations',selectedId],
    queryFn:()=>request<Invitation[]>(`/api/v1/workspaces/${selectedId}/invitations`,{},token),
    enabled:!!token&&!!selectedId&&canManage,
  })

  async function refresh(){
    await Promise.all([active.refetch(),archived.refetch(),members.refetch()])
    if(canManage)await invitations.refetch()
  }

  async function action(key:string,work:()=>Promise<void>,success:string){
    setBusy(key); setError(''); setNotice('')
    try{ await work(); setNotice(success); await refresh() }
    catch(err){ setError(err instanceof Error?err.message:'Request failed') }
    finally{ setBusy('') }
  }

  async function rename(e:FormEvent<HTMLFormElement>){
    e.preventDefault()
    const name=String(new FormData(e.currentTarget).get('name')??'').trim()
    if(!selectedId||!name)return
    await action('rename',async()=>{ await request(`/api/v1/workspaces/${selectedId}`,{method:'PATCH',body:JSON.stringify({name})},token) },'Workspace renamed.')
  }

  async function invite(e:FormEvent<HTMLFormElement>){
    e.preventDefault()
    if(!selectedId)return
    const data=new FormData(e.currentTarget)
    await action('invite',async()=>{
      const created=await request<CreatedInvitation>(`/api/v1/workspaces/${selectedId}/invitations`,{
        method:'POST',
        body:JSON.stringify({email:String(data.get('email')),role:String(data.get('role'))}),
      },token)
      setInviteLink(`${window.location.origin}/invite/${created.token}`)
      e.currentTarget.reset()
    },'Invitation created. Email delivery is queued when SMTP is configured; the secure link is available below as a fallback.')
  }

  async function copyInvite(){
    if(!inviteLink)return
    await navigator.clipboard.writeText(inviteLink)
    setNotice('Invitation link copied.')
  }

  async function changeRole(member:WorkspaceMember,role:string){
    await action(`role:${member.user_id}`,async()=>{
      await request(`/api/v1/workspaces/${selectedId}/members/${member.user_id}`,{
        method:'PATCH',body:JSON.stringify({role}),
      },token)
    },`${member.name}'s role was updated.`)
  }

  async function removeMember(member:WorkspaceMember){
    if(!confirm(`Remove ${member.name} from this workspace?`))return
    await action(`remove:${member.user_id}`,async()=>{
      await request(`/api/v1/workspaces/${selectedId}/members/${member.user_id}`,{method:'DELETE'},token)
    },`${member.name} was removed.`)
  }

  async function transfer(member:WorkspaceMember){
    if(!confirm(`Transfer workspace ownership to ${member.name}? You will become an admin.`))return
    await action(`transfer:${member.user_id}`,async()=>{
      await request(`/api/v1/workspaces/${selectedId}/transfer-ownership`,{
        method:'POST',body:JSON.stringify({user_id:member.user_id}),
      },token)
    },`Ownership transferred to ${member.name}.`)
  }

  async function cancelInvitation(invitation:Invitation){
    await action(`invite:${invitation.id}`,async()=>{
      await request(`/api/v1/workspaces/${selectedId}/invitations/${invitation.id}`,{method:'DELETE'},token)
    },`Invitation for ${invitation.email} was cancelled.`)
  }

  async function archiveWorkspace(){
    if(!selected||!confirm(`Archive ${selected.name}? Project and task access will be blocked until it is restored.`))return
    await action('archive',async()=>{ await request(`/api/v1/workspaces/${selectedId}/archive`,{method:'POST'},token) },'Workspace archived.')
  }

  async function restoreWorkspace(){
    await action('restore',async()=>{ await request(`/api/v1/workspaces/${selectedId}/restore`,{method:'POST'},token) },'Workspace restored.')
  }

  async function leaveWorkspace(){
    if(!selected||!confirm(`Leave ${selected.name}?`))return
    await action('leave',async()=>{
      await request(`/api/v1/workspaces/${selectedId}/leave`,{method:'POST'},token)
      setSelectedId('')
    },'You left the workspace.')
  }

  async function deleteWorkspace(){
    if(!selected||!confirm(`Permanently delete ${selected.name}? This cannot be undone.`))return
    await action('delete',async()=>{
      await request(`/api/v1/workspaces/${selectedId}`,{method:'DELETE'},token)
      setSelectedId('')
    },'Workspace deleted.')
  }

  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading workspace settings…</div>

  return <main className="min-h-screen bg-[var(--bg)]">
    <header className="border-b border-[var(--line)] bg-[var(--panel)]">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <div className="flex items-center gap-3"><Link href="/app" className="rounded-xl border border-[var(--line)] p-2" aria-label="Back to projects"><ArrowLeft size={17}/></Link><div><p className="text-xs muted">Settings</p><h1 className="text-lg font-semibold">Workspace management</h1></div></div>
        <button onClick={()=>void refresh()} className="rounded-xl border border-[var(--line)] p-2" aria-label="Refresh"><RefreshCw size={17}/></button>
      </div>
    </header>

    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[280px_1fr]">
      <aside className="panel h-fit rounded-2xl p-4">
        <p className="px-2 text-xs font-semibold uppercase tracking-wider muted">Active workspaces</p>
        <div className="mt-2 space-y-1">{active.data?.map(workspace=><button key={workspace.id} onClick={()=>{setSelectedId(workspace.id);setInviteLink('')}} className={`w-full rounded-xl px-3 py-2.5 text-left text-sm ${selectedId===workspace.id?'bg-indigo-500/10 font-medium text-indigo-600':'hover:bg-black/5 dark:hover:bg-white/5'}`}>{workspace.name}</button>)}</div>
        <p className="mt-6 px-2 text-xs font-semibold uppercase tracking-wider muted">Archived</p>
        <div className="mt-2 space-y-1">{archived.data?.length?archived.data.map(workspace=><button key={workspace.id} onClick={()=>{setSelectedId(workspace.id);setInviteLink('')}} className={`w-full rounded-xl px-3 py-2.5 text-left text-sm ${selectedId===workspace.id?'bg-amber-500/10 font-medium text-amber-700 dark:text-amber-300':'muted hover:bg-black/5 dark:hover:bg-white/5'}`}>{workspace.name}</button>):<p className="px-3 py-2 text-sm muted">No archived workspaces</p>}</div>
      </aside>

      <section className="min-w-0 space-y-6">
        {notice&&<div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">{notice}</div>}
        {error&&<div role="alert" className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-300">{error}</div>}
        {!selected?<div className="panel rounded-2xl p-8 text-center"><h2 className="font-semibold">No workspace selected</h2><p className="mt-2 text-sm muted">Create or join a workspace from the main app first.</p></div>:<>
          <div className="panel rounded-2xl p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex items-center gap-2"><h2 className="text-xl font-semibold">{selected.name}</h2>{isArchived&&<span className="rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-700 dark:text-amber-300">Archived</span>}</div><p className="mt-1 text-sm muted">Your role: {roleLabel(actorRole??'loading')}</p></div><div className="flex flex-wrap gap-2">{actorRole==='owner'&&isArchived&&<button disabled={busy==='restore'} onClick={()=>void restoreWorkspace()} className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-medium">Restore</button>}{actorRole==='owner'&&!isArchived&&<button disabled={busy==='archive'} onClick={()=>void archiveWorkspace()} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-medium"><Archive size={15}/>Archive</button>}{actorRole&&actorRole!=='owner'&&<button disabled={busy==='leave'} onClick={()=>void leaveWorkspace()} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-medium"><LogOut size={15}/>Leave</button>}</div></div>
            {canManage&&<form onSubmit={rename} className="mt-6 flex gap-2"><input name="name" defaultValue={selected.name} minLength={2} maxLength={120} className="min-w-0 flex-1 rounded-xl border border-[var(--line)] bg-transparent px-3 py-2.5 text-sm"/><button disabled={busy==='rename'} className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white">Rename</button></form>}
          </div>

          <div className="panel rounded-2xl p-5 sm:p-6">
            <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-indigo-500/10 text-indigo-600"><Users size={19}/></span><div><h2 className="font-semibold">Members</h2><p className="text-sm muted">Roles are enforced by the API, including guest project isolation.</p></div></div>
            <div className="mt-5 divide-y divide-[var(--line)]">{members.data?.map(member=>{
              const actorCanManage=actorRole==='owner'?member.role!=='owner':actorRole==='admin'?!['owner','admin'].includes(member.role):false
              const editableRoles=actorRole==='owner'?['admin','member','guest']:['member','guest']
              return <div key={member.user_id} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center"><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="truncate font-medium">{member.name}</p>{member.role==='owner'&&<Crown size={15} className="text-amber-500"/>}</div><p className="truncate text-sm muted">{member.email}</p></div><div className="flex flex-wrap items-center gap-2">{actorCanManage&&!isArchived?<select value={member.role} onChange={event=>void changeRole(member,event.target.value)} disabled={busy===`role:${member.user_id}`} className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm">{editableRoles.map(role=><option key={role} value={role}>{roleLabel(role)}</option>)}</select>:<span className="rounded-full border border-[var(--line)] px-3 py-1.5 text-xs muted">{roleLabel(member.role)}</span>}{actorRole==='owner'&&member.user_id!==user?.id&&!isArchived&&<button onClick={()=>void transfer(member)} disabled={busy===`transfer:${member.user_id}`} className="rounded-xl border border-[var(--line)] px-3 py-2 text-xs font-medium">Transfer ownership</button>}{actorCanManage&&!isArchived&&<button onClick={()=>void removeMember(member)} disabled={busy===`remove:${member.user_id}`} className="rounded-xl border border-red-500/20 p-2 text-red-600" aria-label={`Remove ${member.name}`}><UserMinus size={15}/></button>}</div></div>
            })}</div>
          </div>

          {canManage&&<div className="panel rounded-2xl p-5 sm:p-6">
            <h2 className="font-semibold">Invite by email</h2><p className="mt-1 text-sm muted">Invitations expire after seven days and can only be accepted by the matching account email.</p>
            <form onSubmit={invite} className="mt-5 grid gap-3 sm:grid-cols-[1fr_150px_auto]"><input required type="email" name="email" placeholder="teammate@example.com" className="rounded-xl border border-[var(--line)] bg-transparent px-3 py-2.5 text-sm"/><select name="role" className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5 text-sm">{actorRole==='owner'&&<option value="admin">Admin</option>}<option value="member">Member</option><option value="guest">Guest</option></select><button disabled={busy==='invite'} className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white">Create invite</button></form>
            {inviteLink&&<div className="mt-4 flex gap-2 rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-3"><input readOnly value={inviteLink} className="min-w-0 flex-1 bg-transparent text-xs outline-none"/><button onClick={()=>void copyInvite()} className="rounded-lg border border-[var(--line)] p-2" aria-label="Copy invitation link"><Copy size={15}/></button></div>}
            <div className="mt-6"><p className="text-xs font-semibold uppercase tracking-wider muted">Active invitations</p><div className="mt-2 divide-y divide-[var(--line)]">{invitations.data?.length?invitations.data.map(invitation=><div key={invitation.id} className="flex items-center gap-3 py-3"><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{invitation.email}</p><p className="text-xs muted">{roleLabel(invitation.role)} · expires {new Date(invitation.expires_at).toLocaleDateString()} · email {invitation.delivery_status}</p></div><button onClick={()=>void cancelInvitation(invitation)} disabled={busy===`invite:${invitation.id}`} className="rounded-xl border border-[var(--line)] px-3 py-2 text-xs font-medium">Cancel</button></div>):<p className="py-3 text-sm muted">No active invitations</p>}</div></div>
          </div>}

          {actorRole==='owner'&&<div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-5 sm:p-6"><h2 className="font-semibold text-red-700 dark:text-red-300">Danger zone</h2><p className="mt-1 text-sm muted">Deleting a workspace permanently removes its projects, tasks, memberships, and collaboration data.</p><button onClick={()=>void deleteWorkspace()} disabled={busy==='delete'} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white"><Trash2 size={15}/>Delete workspace</button></div>}
        </>}
      </section>
    </div>
  </main>
}
