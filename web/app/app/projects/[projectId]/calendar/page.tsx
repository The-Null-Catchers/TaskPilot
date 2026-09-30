'use client'

import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'

import { useAuth } from '@/components/providers'
import { ThemeToggle } from '@/components/theme-toggle'
import { request } from '@/lib/api'

type Item={id:string;kind:'task'|'project'|'milestone';title:string;starts_at:string;project_id:string;task_id:string|null;identifier:string|null;priority:string|null;status:string|null}
type View='month'|'week'
function startOfWeek(date:Date){const d=new Date(date);d.setDate(d.getDate()-d.getDay());d.setHours(0,0,0,0);return d}
function endOfWeek(date:Date){const d=startOfWeek(date);d.setDate(d.getDate()+7);return d}
function monthRange(date:Date){return [new Date(date.getFullYear(),date.getMonth(),1),new Date(date.getFullYear(),date.getMonth()+1,1)] as const}

export default function ProjectCalendarPage(){
  const {projectId}=useParams<{projectId:string}>()
  const {token,loading}=useAuth()
  const router=useRouter()
  const [view,setView]=useState<View>('month')
  const [cursor,setCursor]=useState(new Date())
  useEffect(()=>{if(!loading&&!token)router.replace('/login')},[loading,token,router])
  const range=useMemo(()=>view==='month'?monthRange(cursor):[startOfWeek(cursor),endOfWeek(cursor)] as const,[cursor,view])
  const params=useMemo(()=>new URLSearchParams({start:range[0].toISOString(),end:range[1].toISOString(),project_id:projectId}).toString(),[range,projectId])
  const items=useQuery({queryKey:['project-calendar',params],queryFn:()=>request<Item[]>(`/api/v1/calendar?${params}`,{},token),enabled:!!token&&!!projectId})
  const grouped=useMemo(()=>{const map=new Map<string,Item[]>();for(const item of items.data??[]){const key=new Date(item.starts_at).toDateString();map.set(key,[...(map.get(key)??[]),item])}return map},[items.data])
  const days=useMemo(()=>{const result:Date[]=[];const d=new Date(range[0]);while(d<range[1]){result.push(new Date(d));d.setDate(d.getDate()+1)}return result},[range])
  function move(delta:number){const d=new Date(cursor);if(view==='month')d.setMonth(d.getMonth()+delta);else d.setDate(d.getDate()+7*delta);setCursor(d)}
  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading TaskPilot…</div>
  return <main className="min-h-screen bg-[var(--bg)]"><header className="border-b border-[var(--line)] bg-[var(--panel)]"><div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6"><div className="flex items-center gap-3"><Link href={`/app/projects/${projectId}/overview`} className="rounded-xl border border-[var(--line)] p-2"><ArrowLeft size={18}/></Link><div><p className="text-xs muted">Project planning</p><h1 className="font-semibold">Calendar</h1></div></div><ThemeToggle/></div></header><div className="mx-auto max-w-7xl p-4 sm:p-6"><section className="panel rounded-2xl p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2"><button onClick={()=>move(-1)} className="rounded-xl border border-[var(--line)] p-2" aria-label="Previous period"><ChevronLeft size={17}/></button><button onClick={()=>setCursor(new Date())} className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm">Today</button><button onClick={()=>move(1)} className="rounded-xl border border-[var(--line)] p-2" aria-label="Next period"><ChevronRight size={17}/></button><h2 className="ml-2 font-semibold">{cursor.toLocaleDateString(undefined,{month:'long',year:'numeric'})}</h2></div><div className="flex rounded-xl border border-[var(--line)] p-1">{(['month','week'] as View[]).map(v=><button key={v} onClick={()=>setView(v)} className={`rounded-lg px-3 py-1.5 text-sm ${view===v?'bg-indigo-600 text-white':'muted'}`}>{v}</button>)}</div></div></section>{items.isError&&<div className="mt-4 rounded-2xl border border-red-300/50 bg-red-500/5 p-4 text-sm text-red-600">Could not load project calendar.</div>}<section className={`mt-4 grid gap-px overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--line)] ${view==='month'?'grid-cols-1 sm:grid-cols-7':'grid-cols-1 md:grid-cols-7'}`}>{days.map(day=><div key={day.toISOString()} className="min-h-32 bg-[var(--panel)] p-3"><div className="mb-2 flex items-center justify-between"><span className="text-xs font-semibold">{day.toLocaleDateString(undefined,{weekday:'short'})}</span><span className={`grid h-7 w-7 place-items-center rounded-full text-xs ${day.toDateString()===new Date().toDateString()?'bg-indigo-600 text-white':'muted'}`}>{day.getDate()}</span></div><div className="space-y-1.5">{(grouped.get(day.toDateString())??[]).map(item=>{const card=<div className="rounded-lg border border-[var(--line)] px-2 py-1.5 text-xs"><div className="flex items-center gap-1"><CalendarDays size={12}/><span className="truncate font-medium">{item.title}</span></div><p className="mt-0.5 muted">{item.kind}{item.identifier?` · ${item.identifier}`:''}</p></div>;return item.task_id?<Link key={item.id} href={`/app/tasks/${item.task_id}`}>{card}</Link>:<div key={item.id}>{card}</div>})}</div></div>)}</section>{items.isLoading&&<div className="mt-6 text-center text-sm muted">Loading calendar…</div>}</div></main>
}
