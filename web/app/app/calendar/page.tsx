'use client'

import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'

import { useAuth } from '@/components/providers'
import { ThemeToggle } from '@/components/theme-toggle'
import { Project, request, Workspace } from '@/lib/api'

type Item={id:string;kind:'task'|'project'|'milestone';title:string;starts_at:string;workspace_id:string;project_id:string;task_id:string|null;identifier:string|null;priority:string|null;status:string|null}
type View='month'|'week'

function startOfWeek(date:Date){const d=new Date(date);const day=d.getDay();d.setDate(d.getDate()-day);d.setHours(0,0,0,0);return d}
function endOfWeek(date:Date){const d=startOfWeek(date);d.setDate(d.getDate()+7);return d}
function monthRange(date:Date){return [new Date(date.getFullYear(),date.getMonth(),1),new Date(date.getFullYear(),date.getMonth()+1,1)] as const}

export default function CalendarPage(){
 const {token,loading}=useAuth();const router=useRouter();
 const [view,setView]=useState<View>('month');const [cursor,setCursor]=useState(new Date());const [workspaceId,setWorkspaceId]=useState('');const [projectId,setProjectId]=useState('');
 useEffect(()=>{if(!loading&&!token)router.replace('/login')},[loading,token,router])
 const workspaces=useQuery({queryKey:['workspaces'],queryFn:()=>request<Workspace[]>('/api/v1/workspaces',{},token),enabled:!!token})
 const projects=useQuery({queryKey:['calendar-projects',workspaceId],queryFn:()=>request<Project[]>(`/api/v1/projects?workspace_id=${workspaceId}`,{},token),enabled:!!token&&!!workspaceId})
 const range=useMemo(()=>view==='month'?monthRange(cursor):[startOfWeek(cursor),endOfWeek(cursor)] as const,[cursor,view])
 const params=useMemo(()=>{const p=new URLSearchParams({start:range[0].toISOString(),end:range[1].toISOString()});if(workspaceId)p.set('workspace_id',workspaceId);if(projectId)p.set('project_id',projectId);return p.toString()},[range,workspaceId,projectId])
 const items=useQuery({queryKey:['calendar',params],queryFn:()=>request<Item[]>(`/api/v1/calendar?${params}`,{},token),enabled:!!token})
 const grouped=useMemo(()=>{const map=new Map<string,Item[]>();for(const item of items.data??[]){const key=new Date(item.starts_at).toDateString();map.set(key,[...(map.get(key)??[]),item])}return map},[items.data])
 const days=useMemo(()=>{const result:Date[]=[];let d=new Date(range[0]);while(d<range[1]){result.push(new Date(d));d.setDate(d.getDate()+1)}return result},[range])
 function move(delta:number){const d=new Date(cursor);if(view==='month')d.setMonth(d.getMonth()+delta);else d.setDate(d.getDate()+7*delta);setCursor(d)}
 if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading TaskPilot…</div>
 return <main className="min-h-screen bg-[var(--bg)]"><header className="border-b border-[var(--line)] bg-[var(--panel)]"><div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6"><div className="flex items-center gap-3"><Link href="/app" className="rounded-xl border border-[var(--line)] p-2"><ArrowLeft size={18}/></Link><div><p className="text-xs muted">Planning</p><h1 className="font-semibold">Calendar</h1></div></div><ThemeToggle/></div></header><div className="mx-auto max-w-7xl p-4 sm:p-6"><section className="panel rounded-2xl p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2"><button onClick={()=>move(-1)} className="rounded-xl border border-[var(--line)] p-2"><ChevronLeft size={17}/></button><button onClick={()=>setCursor(new Date())} className="rounded-xl border border-[var(--line)] px-3 py-2 text-sm">Today</button><button onClick={()=>move(1)} className="rounded-xl border border-[var(--line)] p-2"><ChevronRight size={17}/></button><h2 className="ml-2 font-semibold">{cursor.toLocaleDateString(undefined,{month:'long',year:'numeric'})}</h2></div><div className="flex gap-2"><select value={workspaceId} onChange={e=>{setWorkspaceId(e.target.value);setProjectId('')}} className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm"><option value="">All workspaces</option>{workspaces.data?.map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</select><select value={projectId} onChange={e=>setProjectId(e.target.value)} disabled={!workspaceId} className="rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm disabled:opacity-50"><option value="">All projects</option>{projects.data?.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><div className="flex rounded-xl border border-[var(--line)] p-1">{(['month','week'] as View[]).map(v=><button key={v} onClick={()=>setView(v)} className={`rounded-lg px-3 py-1.5 text-sm ${view===v?'bg-indigo-600 text-white':'muted'}`}>{v}</button>)}</div></div></div></section>{items.isError&&<div className="mt-4 rounded-2xl border border-red-300/50 bg-red-500/5 p-4 text-sm text-red-600">Could not load calendar.</div>}<section className={`mt-4 grid gap-px overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--line)] ${view==='month'?'grid-cols-1 sm:grid-cols-7':'grid-cols-1 md:grid-cols-7'}`}>{days.map(day=><div key={day.toISOString()} className="min-h-32 bg-[var(--panel)] p-3"><div className="mb-2 flex items-center justify-between"><span className="text-xs font-semibold">{day.toLocaleDateString(undefined,{weekday:'short'})}</span><span className={`grid h-7 w-7 place-items-center rounded-full text-xs ${day.toDateString()===new Date().toDateString()?'bg-indigo-600 text-white':'muted'}`}>{day.getDate()}</span></div><div className="space-y-1.5">{(grouped.get(day.toDateString())??[]).map(item=>{const body=<div className="rounded-lg border border-[var(--line)] px-2 py-1.5 text-xs"><div className="flex items-center gap-1"><CalendarDays size={12}/><span className="truncate font-medium">{item.title}</span></div><p className="mt-0.5 muted">{item.kind}{item.identifier?` · ${item.identifier}`:''}</p></div>;return item.task_id?<Link key={item.id} href={`/app/tasks/${item.task_id}`}>{body}</Link>:<div key={item.id}>{body}</div>})}</div></div>)}</section>{items.isLoading&&<div className="mt-6 text-center text-sm muted">Loading calendar…</div>}</div></main>
}
