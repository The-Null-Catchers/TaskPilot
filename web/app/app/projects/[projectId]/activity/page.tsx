'use client'

import { useQuery } from '@tanstack/react-query'
import { Activity, ArrowLeft, ExternalLink } from 'lucide-react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { useEffect } from 'react'

import { useAuth } from '@/components/providers'
import { ThemeToggle } from '@/components/theme-toggle'
import { request } from '@/lib/api'

type ActivityItem={id:string;action:string;summary:string;actor_id:string;workspace_id:string;task_id:string|null;created_at:string}

export default function ProjectActivityPage(){
  const {projectId}=useParams<{projectId:string}>()
  const {token,loading}=useAuth()
  const router=useRouter()
  useEffect(()=>{if(!loading&&!token)router.replace('/login')},[loading,token,router])
  const feed=useQuery({queryKey:['project-activity',projectId],queryFn:()=>request<ActivityItem[]>(`/api/v1/activity/projects/${projectId}`,{},token),enabled:!!token&&!!projectId})
  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading TaskPilot…</div>
  return <main className="min-h-screen bg-[var(--bg)]"><header className="border-b border-[var(--line)] bg-[var(--panel)]"><div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-4 sm:px-6"><div className="flex items-center gap-3"><Link href={`/app/projects/${projectId}/overview`} className="rounded-xl border border-[var(--line)] p-2"><ArrowLeft size={18}/></Link><div><p className="text-xs muted">Project history</p><h1 className="font-semibold">Activity</h1></div></div><ThemeToggle/></div></header><div className="mx-auto max-w-5xl p-4 sm:p-6">{feed.isLoading&&<div className="panel animate-pulse rounded-2xl p-12 text-center text-sm muted">Loading activity…</div>}{feed.isError&&<div className="rounded-2xl border border-red-300/40 bg-red-500/5 p-5 text-sm text-red-600">Could not load project activity.</div>}{!feed.isLoading&&!feed.isError&&<section className="panel rounded-2xl p-5"><div className="flex items-center gap-2"><Activity size={18}/><h2 className="font-semibold">Recent changes</h2></div><div className="mt-4 space-y-1">{feed.data?.map(item=><div key={item.id} className="flex gap-3 border-b border-[var(--line)] py-4 last:border-0"><span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-indigo-600"/><div className="min-w-0 flex-1"><p className="text-sm">{item.summary}</p><div className="mt-1 flex flex-wrap items-center gap-2 text-xs muted"><span>{new Date(item.created_at).toLocaleString()}</span><span>·</span><span>{item.action}</span>{item.task_id&&<Link href={`/app/tasks/${item.task_id}`} className="inline-flex items-center gap-1 font-medium text-indigo-600">Open task <ExternalLink size={11}/></Link>}</div></div></div>)}{feed.data?.length===0&&<div className="py-12 text-center"><Activity className="mx-auto muted"/><h3 className="mt-3 font-semibold">No project activity yet</h3><p className="mt-1 text-sm muted">Task, collaboration and project changes will appear here.</p></div>}</div></section>}</div></main>
}
