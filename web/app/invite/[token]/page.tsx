'use client'

import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Check, Mail, X } from 'lucide-react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { useState } from 'react'

import { useAuth } from '@/components/providers'
import { request } from '@/lib/api'

type InvitationPreview = {
  workspace_id:string
  workspace_name:string
  email:string
  role:'owner'|'admin'|'member'|'guest'
  expires_at:string
}

function roleLabel(role:string){ return role.charAt(0).toUpperCase()+role.slice(1) }

export default function WorkspaceInvitationPage(){
  const {token:authToken,loading,user}=useAuth()
  const params=useParams<{token:string}>()
  const router=useRouter()
  const inviteToken=typeof params.token==='string'?params.token:''
  const [busy,setBusy]=useState<'accept'|'reject'|''>('')
  const [error,setError]=useState('')

  const preview=useQuery({
    queryKey:['workspace-invitation',inviteToken],
    queryFn:()=>request<InvitationPreview>(`/api/v1/workspaces/invitations/${encodeURIComponent(inviteToken)}`,{},authToken),
    enabled:!!authToken&&!!inviteToken,
    retry:false,
  })

  async function respond(kind:'accept'|'reject'){
    if(!authToken||!inviteToken)return
    setBusy(kind); setError('')
    try{
      await request(`/api/v1/workspaces/invitations/${encodeURIComponent(inviteToken)}/${kind}`,{method:'POST'},authToken)
      router.replace('/app')
    }catch(err){
      setError(err instanceof Error?err.message:'Unable to process invitation')
    }finally{
      setBusy('')
    }
  }

  if(loading)return <main className="grid min-h-screen place-items-center muted">Loading invitation…</main>

  if(!authToken){
    const next=`/invite/${encodeURIComponent(inviteToken)}`
    return <main className="grid min-h-screen place-items-center px-6">
      <div className="panel w-full max-w-lg rounded-3xl p-8 text-center shadow-soft">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-indigo-500/10 text-indigo-600"><Mail size={22}/></span>
        <h1 className="mt-5 text-2xl font-semibold">Workspace invitation</h1>
        <p className="mt-2 text-sm muted">Sign in with the email address this invitation was sent to. You can create an account if you do not have one yet.</p>
        <Link href={`/login?next=${encodeURIComponent(next)}`} className="mt-6 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white">Continue to sign in <ArrowRight size={16}/></Link>
      </div>
    </main>
  }

  return <main className="grid min-h-screen place-items-center px-6">
    <div className="panel w-full max-w-lg rounded-3xl p-8 shadow-soft">
      {preview.isLoading?<div className="py-12 text-center muted">Checking invitation…</div>:preview.error?<div className="text-center"><span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-red-500/10 text-red-600"><X size={22}/></span><h1 className="mt-5 text-xl font-semibold">Invitation unavailable</h1><p className="mt-2 text-sm muted">{preview.error instanceof Error?preview.error.message:'This invitation is invalid, expired, or unavailable.'}</p><Link href="/app" className="mt-6 inline-flex rounded-xl border border-[var(--line)] px-4 py-2.5 text-sm font-medium">Back to TaskPilot</Link></div>:preview.data?<>
        <div className="flex items-start gap-4"><span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-indigo-500/10 text-indigo-600"><Mail size={22}/></span><div><p className="text-sm muted">You were invited to</p><h1 className="mt-1 text-2xl font-semibold">{preview.data.workspace_name}</h1></div></div>
        <dl className="mt-6 grid gap-3 rounded-2xl border border-[var(--line)] p-4 text-sm"><div className="flex justify-between gap-4"><dt className="muted">Account</dt><dd className="truncate font-medium">{user?.email}</dd></div><div className="flex justify-between gap-4"><dt className="muted">Role</dt><dd className="font-medium">{roleLabel(preview.data.role)}</dd></div><div className="flex justify-between gap-4"><dt className="muted">Expires</dt><dd className="font-medium">{new Date(preview.data.expires_at).toLocaleString()}</dd></div></dl>
        {error&&<p role="alert" className="mt-4 rounded-xl bg-red-500/10 p-3 text-sm text-red-600">{error}</p>}
        <div className="mt-6 grid gap-3 sm:grid-cols-2"><button disabled={!!busy} onClick={()=>void respond('reject')} className="inline-flex items-center justify-center gap-2 rounded-xl border border-[var(--line)] px-4 py-2.5 text-sm font-semibold"><X size={16}/>Decline</button><button disabled={!!busy} onClick={()=>void respond('accept')} className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white"><Check size={16}/>{busy==='accept'?'Joining…':'Accept invitation'}</button></div>
      </>:null}
    </div>
  </main>
}
