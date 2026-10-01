'use client'

import { ArrowLeft, Files } from 'lucide-react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { useEffect } from 'react'

import { AttachmentsPanel } from '@/components/attachments-panel'
import { useAuth } from '@/components/providers'
import { ThemeToggle } from '@/components/theme-toggle'

export default function ProjectFilesPage(){
  const {projectId}=useParams<{projectId:string}>()
  const {token,loading}=useAuth()
  const router=useRouter()
  useEffect(()=>{if(!loading&&!token)router.replace('/login')},[loading,token,router])
  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading TaskPilot…</div>
  return <main className="min-h-screen bg-[var(--bg)]"><header className="border-b border-[var(--line)] bg-[var(--panel)]"><div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-4 sm:px-6"><div className="flex items-center gap-3"><Link href={`/app/projects/${projectId}/overview`} className="rounded-xl border border-[var(--line)] p-2"><ArrowLeft size={18}/></Link><div><p className="text-xs muted">Project resources</p><h1 className="font-semibold">Files</h1></div></div><ThemeToggle/></div></header><div className="mx-auto max-w-5xl p-4 sm:p-6"><div className="mb-4 flex items-center gap-3"><div className="grid h-11 w-11 place-items-center rounded-2xl bg-indigo-500/10 text-indigo-600"><Files size={20}/></div><div><h2 className="font-semibold">Project attachments</h2><p className="text-sm muted">Shared files attached directly to this project.</p></div></div><AttachmentsPanel entityType="project" entityId={projectId} token={token}/></div></main>
}
