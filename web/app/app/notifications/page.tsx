'use client'

import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Bell, CheckCheck } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

import { useAuth } from '@/components/providers'
import { ThemeToggle } from '@/components/theme-toggle'
import { Notification, request } from '@/lib/api'

export default function NotificationsPage() {
  const {token,loading}=useAuth()
  const router=useRouter()
  useEffect(()=>{if(!loading&&!token)router.replace('/login')},[loading,token,router])
  const notifications=useQuery({queryKey:['notifications'],queryFn:()=>request<Notification[]>('/api/v1/notifications',{},token),enabled:!!token})

  async function markRead(id:string) {
    if(!token)return
    await request<Notification>(`/api/v1/notifications/${id}/read`,{method:'POST'},token)
    await notifications.refetch()
  }
  async function markAll() {
    if(!token)return
    await request<void>('/api/v1/notifications/read-all',{method:'POST'},token)
    await notifications.refetch()
  }

  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading TaskPilot…</div>
  const unread=notifications.data?.filter(item=>!item.read_at).length??0

  return <main className="min-h-screen bg-[var(--bg)]">
    <header className="sticky top-0 z-20 border-b border-[var(--line)] bg-[var(--panel)]/95 backdrop-blur"><div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-3 px-4 sm:px-6"><div className="flex items-center gap-3"><Link href="/app" className="rounded-xl border border-[var(--line)] p-2" aria-label="Back"><ArrowLeft size={18}/></Link><div><p className="text-xs muted">Inbox</p><h1 className="font-semibold">Notifications</h1></div></div><div className="flex items-center gap-2"><ThemeToggle/><button onClick={()=>void markAll()} disabled={unread===0} className="flex items-center gap-2 rounded-xl border border-[var(--line)] px-3 py-2 text-sm font-medium disabled:opacity-40"><CheckCheck size={16}/>Mark all read</button></div></div></header>
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6"><div className="mb-4 flex items-end justify-between"><div><p className="text-sm muted">{unread} unread</p><h2 className="text-xl font-semibold tracking-tight">Activity requiring your attention</h2></div></div><section className="overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--panel)]">{notifications.isLoading&&<p className="p-8 text-center text-sm muted">Loading notifications…</p>}{notifications.data?.map(item=>{const content=<><div className={`mt-1 h-2 w-2 shrink-0 rounded-full ${item.read_at?'bg-transparent':'bg-indigo-600'}`}/><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-semibold">{item.title}</p><time className="text-xs muted">{new Date(item.created_at).toLocaleString()}</time></div>{item.body&&<p className="mt-1 text-sm leading-6 muted">{item.body}</p>}<p className="mt-2 text-[11px] uppercase tracking-wide muted">{item.kind.replaceAll('.',' · ')}</p></div></>;return <article key={item.id} className={`flex gap-3 border-b border-[var(--line)] p-4 last:border-0 ${item.read_at?'':'bg-indigo-500/[.035]'}`}>{item.entity_type==='task'&&item.entity_id?<Link onClick={()=>{if(!item.read_at)void markRead(item.id)}} href={`/app/tasks/${item.entity_id}`} className="flex min-w-0 flex-1 gap-3">{content}</Link>:<button onClick={()=>void markRead(item.id)} className="flex min-w-0 flex-1 gap-3 text-left">{content}</button>}{!item.read_at&&<button onClick={()=>void markRead(item.id)} className="h-fit shrink-0 rounded-lg border border-[var(--line)] px-2 py-1 text-xs">Read</button>}</article>})}{notifications.data?.length===0&&<div className="p-12 text-center"><div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-indigo-500/10 text-indigo-600"><Bell/></div><h3 className="mt-4 font-semibold">You’re all caught up</h3><p className="mt-1 text-sm muted">Assignments, mentions, comments, deadlines, and resolved dependencies will appear here.</p></div>}</section></div>
  </main>
}
