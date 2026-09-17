'use client'

import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

import { AttachmentsPanel } from '@/components/attachments-panel'
import { useAuth } from '@/components/providers'
import { TaskDrawer } from '@/components/task-drawer'
import { request, Task } from '@/lib/api'

export default function TaskPage() {
  const params=useParams<{taskId:string}>()
  const router=useRouter()
  const {token,loading}=useAuth()
  const [task,setTask]=useState<Task|null>(null)
  useEffect(()=>{if(!loading&&!token)router.replace('/login')},[loading,token,router])
  const query=useQuery({
    queryKey:['task',params.taskId],
    queryFn:()=>request<Task>(`/api/v1/tasks/${params.taskId}`,{},token),
    enabled:!!token&&!!params.taskId,
  })
  useEffect(()=>{if(query.data)setTask(query.data)},[query.data])

  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading TaskPilot…</div>
  if(query.isLoading)return <div className="grid min-h-screen place-items-center muted">Loading task…</div>
  if(query.isError||!task)return <main className="grid min-h-screen place-items-center p-6"><div className="panel max-w-md rounded-2xl p-8 text-center"><h1 className="font-semibold">Task unavailable</h1><p className="mt-2 text-sm muted">It may have been removed, or you may no longer have access.</p><Link href="/app/my-tasks" className="mt-5 inline-flex items-center gap-2 rounded-xl border border-[var(--line)] px-4 py-2 text-sm"><ArrowLeft size={16}/>Back to My Tasks</Link></div></main>

  return <main className="min-h-screen bg-[var(--bg)]"><TaskDrawer task={task} token={token} onClose={()=>router.back()} onUpdated={setTask}/><div className="fixed bottom-5 left-5 z-[80] w-[min(92vw,420px)]"><AttachmentsPanel entityType="task" entityId={task.id} token={token} compact/></div></main>
}
