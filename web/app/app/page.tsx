'use client'

import { useQuery } from '@tanstack/react-query'
import { Bell, ChevronDown, LayoutDashboard, ListTodo, LogOut, Menu, Plus, Settings2, X } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { FormEvent, useEffect, useRef, useState } from 'react'

import { CommandPalette } from '@/components/command-palette'
import { KanbanBoard } from '@/components/kanban-board'
import { useAuth } from '@/components/providers'
import { ThemeToggle } from '@/components/theme-toggle'
import { API_URL, Board, Project, request, Workspace } from '@/lib/api'

export default function AppHome(){
 const {user,token,loading,logout}=useAuth()
 const router=useRouter()
 const [workspaceId,setWorkspaceId]=useState('')
 const [projectId,setProjectId]=useState('')
 const [localBoard,setLocalBoard]=useState<Board|null>(null)
 const [newProject,setNewProject]=useState(false)
 const [mobileNav,setMobileNav]=useState(false)
 const retryRef=useRef<ReturnType<typeof setTimeout>|null>(null)

 useEffect(()=>{if(!loading&&!token) router.replace('/login')},[loading,token,router])
 const workspaces=useQuery({queryKey:['workspaces'],queryFn:()=>request<Workspace[]>('/api/v1/workspaces',{},token),enabled:!!token})
 useEffect(()=>{if(!workspaceId&&workspaces.data?.[0]) setWorkspaceId(workspaces.data[0].id)},[workspaceId,workspaces.data])
 const projects=useQuery({queryKey:['projects',workspaceId],queryFn:()=>request<Project[]>(`/api/v1/projects?workspace_id=${workspaceId}`,{},token),enabled:!!token&&!!workspaceId})
 useEffect(()=>{if(projects.data?.length&&!projects.data.some(p=>p.id===projectId)) setProjectId(projects.data[0].id)},[projects.data,projectId])
 const board=useQuery({queryKey:['board',projectId],queryFn:()=>request<Board>(`/api/v1/projects/${projectId}/board`,{},token),enabled:!!token&&!!projectId})
 useEffect(()=>{if(board.data) setLocalBoard(board.data)},[board.data])
 useEffect(()=>{
   if(!token||!workspaceId)return
   let disposed=false
   let socket:WebSocket|undefined
   const connect=()=>{
     if(disposed)return
     const wsBase=API_URL.replace(/^http/,'ws')
     socket=new WebSocket(`${wsBase}/api/v1/ws/workspaces/${workspaceId}?token=${encodeURIComponent(token)}`)
     socket.onmessage=(event)=>{
       try{
         const data=JSON.parse(event.data) as {event?:string}
         if(data.event?.startsWith('task.')||data.event?.startsWith('comment.')||data.event?.startsWith('subtask.')||data.event?.startsWith('checklist.'))void board.refetch()
       }catch{}
     }
     socket.onclose=()=>{if(!disposed)retryRef.current=setTimeout(connect,2000)}
   }
   connect()
   return()=>{disposed=true;if(retryRef.current)clearTimeout(retryRef.current);socket?.close()}
 },[token,workspaceId,projectId])

 async function createProject(e:FormEvent<HTMLFormElement>){
   e.preventDefault()
   if(!token)return
   const f=new FormData(e.currentTarget)
   const project=await request<Project>('/api/v1/projects',{method:'POST',body:JSON.stringify({workspace_id:workspaceId,name:f.get('name'),key:f.get('key')})},token)
   setNewProject(false)
   await projects.refetch()
   setProjectId(project.id)
 }

 if(loading||!token) return <div className="grid min-h-screen place-items-center muted">Loading TaskPilot…</div>

 const navigation=<>
   <div className="mb-6 flex items-center gap-2 px-2 text-lg font-semibold"><span className="grid h-8 w-8 place-items-center rounded-xl bg-indigo-600 text-white">T</span>TaskPilot</div>
   <label className="block text-xs font-medium muted">Workspace<select value={workspaceId} onChange={e=>{setWorkspaceId(e.target.value);setProjectId('')}} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5 text-sm text-[var(--fg)]">{workspaces.data?.map(workspace=><option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}</select></label>
   <nav className="mt-5 space-y-1 text-sm">
     <Link href="/app" className="flex items-center gap-3 rounded-xl bg-indigo-500/10 px-3 py-2.5 font-medium text-indigo-600" onClick={()=>setMobileNav(false)}><LayoutDashboard size={17}/>Projects</Link>
     <Link href="/app/my-tasks" className="flex items-center gap-3 rounded-xl px-3 py-2.5 muted hover:bg-black/5 dark:hover:bg-white/5" onClick={()=>setMobileNav(false)}><ListTodo size={17}/>My Tasks</Link>
     <Link href="/app/notifications" className="flex items-center gap-3 rounded-xl px-3 py-2.5 muted hover:bg-black/5 dark:hover:bg-white/5" onClick={()=>setMobileNav(false)}><Bell size={17}/>Notifications</Link>
     <span className="flex items-center gap-3 rounded-xl px-3 py-2.5 muted"><Settings2 size={17}/>Settings</span>
   </nav>
   <div className="mt-7 flex items-center justify-between px-2"><p className="text-xs font-semibold uppercase tracking-wider muted">Projects</p><button onClick={()=>{setNewProject(true);setMobileNav(false)}} aria-label="Create project"><Plus size={16}/></button></div>
   <div className="mt-2 space-y-1">{projects.data?.map(p=><button key={p.id} onClick={()=>{setProjectId(p.id);setMobileNav(false)}} className={`w-full rounded-xl px-3 py-2 text-left text-sm ${p.id===projectId?'bg-black/5 font-medium dark:bg-white/5':'muted'}`}>{p.name}</button>)}</div>
   <div className="mt-auto flex items-center gap-3 border-t border-[var(--line)] pt-4"><span className="grid h-9 w-9 place-items-center rounded-full bg-indigo-500/15 text-sm font-semibold text-indigo-600">{user?.name?.slice(0,2).toUpperCase()}</span><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{user?.name}</p><p className="truncate text-xs muted">{user?.email}</p></div><button onClick={()=>void logout()} aria-label="Sign out"><LogOut size={17}/></button></div>
 </>

 return <main className="flex min-h-screen">
   <aside className="hidden w-64 shrink-0 border-r border-[var(--line)] bg-[var(--panel)] p-4 lg:flex lg:flex-col">{navigation}</aside>
   {mobileNav&&<div className="fixed inset-0 z-50 bg-black/35 lg:hidden" onMouseDown={()=>setMobileNav(false)}><aside onMouseDown={e=>e.stopPropagation()} className="flex h-full w-[min(86vw,320px)] flex-col border-r border-[var(--line)] bg-[var(--panel)] p-4 shadow-2xl"><div className="mb-1 flex justify-end"><button onClick={()=>setMobileNav(false)} className="rounded-xl border border-[var(--line)] p-2" aria-label="Close navigation"><X size={17}/></button></div>{navigation}</aside></div>}
   <section className="min-w-0 flex-1">
     <header className="flex h-16 items-center justify-between border-b border-[var(--line)] bg-[var(--panel)] px-4 sm:px-6"><div className="flex min-w-0 items-center gap-3"><button onClick={()=>setMobileNav(true)} className="rounded-xl border border-[var(--line)] p-2 lg:hidden" aria-label="Open navigation"><Menu size={18}/></button><div className="min-w-0"><p className="text-xs muted">Project</p><h1 className="truncate font-semibold">{localBoard?.project.name??'Create a project'}</h1></div></div><div className="flex items-center gap-2"><CommandPalette token={token} onCreateProject={()=>setNewProject(true)} onSelectProject={setProjectId}/><ThemeToggle/><Link href="/app/notifications" className="rounded-xl border border-[var(--line)] p-2" aria-label="Notifications"><Bell size={18}/></Link></div></header>
     <div className="p-4 sm:p-6">{localBoard?<><div className="mb-6 flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm muted">{localBoard.project.key}</p><h2 className="text-2xl font-semibold tracking-tight">Board</h2></div><span className="rounded-full border border-[var(--line)] bg-[var(--panel)] px-3 py-1.5 text-xs muted">{localBoard.tasks.length} tasks</span></div><KanbanBoard initial={localBoard} token={token} onChanged={setLocalBoard}/></>:<div className="panel mx-auto mt-20 max-w-lg rounded-3xl p-10 text-center"><div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-indigo-500/10 text-indigo-600"><LayoutDashboard/></div><h2 className="mt-4 text-xl font-semibold">Your first project starts here</h2><p className="mt-2 text-sm muted">Create a project and TaskPilot will prepare a five-column board automatically.</p><button onClick={()=>setNewProject(true)} className="mt-6 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white">Create project</button></div>}</div>
   </section>
   {newProject&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/35 p-4" onMouseDown={()=>setNewProject(false)}><form onSubmit={createProject} onMouseDown={e=>e.stopPropagation()} className="panel w-full max-w-md rounded-2xl p-6"><h2 className="text-lg font-semibold">New project</h2><label className="mt-5 block text-sm">Name<input required name="name" className="mt-2 w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-3"/></label><label className="mt-4 block text-sm">Key<input required name="key" minLength={2} maxLength={12} placeholder="DEV" className="mt-2 w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-3 uppercase"/></label><div className="mt-6 flex justify-end gap-2"><button type="button" onClick={()=>setNewProject(false)} className="rounded-xl px-4 py-2 text-sm">Cancel</button><button className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">Create project</button></div></form></div>}
 </main>
}
