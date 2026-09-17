'use client'

import { useQuery } from '@tanstack/react-query'
import { Bell, FolderKanban, ListTodo, Plus, Search } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useEffect, useRef, useState } from 'react'

import { request, SearchResults } from '@/lib/api'

export function CommandPalette({token,onCreateProject,onSelectProject}:{token:string;onCreateProject:()=>void;onSelectProject:(projectId:string)=>void}) {
  const router=useRouter()
  const [open,setOpen]=useState(false)
  const [query,setQuery]=useState('')
  const inputRef=useRef<HTMLInputElement|null>(null)
  const search=useQuery({
    queryKey:['global-search',query],
    queryFn:()=>request<SearchResults>(`/api/v1/search?q=${encodeURIComponent(query.trim())}`,{},token),
    enabled:open&&query.trim().length>=2,
    staleTime:15_000,
  })

  useEffect(()=>{
    const handler=(event:KeyboardEvent)=>{
      if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){
        event.preventDefault()
        setOpen(value=>!value)
      }
    }
    window.addEventListener('keydown',handler)
    return()=>window.removeEventListener('keydown',handler)
  },[])
  useEffect(()=>{if(open)setTimeout(()=>inputRef.current?.focus(),0);else setQuery('')},[open])

  function act(action:()=>void) { action(); setOpen(false) }

  return <>
    <button onClick={()=>setOpen(true)} className="hidden items-center gap-2 rounded-xl border border-[var(--line)] px-3 py-2 text-sm muted sm:flex"><Search size={16}/>Search <kbd className="ml-4 text-xs">⌘K</kbd></button>
    {open&&<div className="fixed inset-0 z-[70] flex justify-center bg-black/45 px-4 pt-[12vh]" onMouseDown={()=>setOpen(false)}>
      <section onMouseDown={event=>event.stopPropagation()} className="panel h-fit w-full max-w-2xl overflow-hidden rounded-2xl shadow-2xl">
        <div className="flex items-center gap-3 border-b border-[var(--line)] px-4"><Search size={18} className="muted"/><input ref={inputRef} value={query} onChange={event=>setQuery(event.target.value)} onKeyDown={event=>{if(event.key==='Escape')setOpen(false)}} placeholder="Search tasks, projects, comments, labels…" className="h-14 min-w-0 flex-1 bg-transparent text-sm outline-none"/><kbd className="rounded border border-[var(--line)] px-1.5 py-0.5 text-[10px] muted">ESC</kbd></div>
        <div className="max-h-[62vh] overflow-y-auto p-2">
          {query.trim().length<2&&<div className="space-y-1"><p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider muted">Quick actions</p><button onClick={()=>act(onCreateProject)} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm hover:bg-black/5 dark:hover:bg-white/5"><Plus size={17}/>Create project</button><button onClick={()=>act(()=>router.push('/app/my-tasks'))} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm hover:bg-black/5 dark:hover:bg-white/5"><ListTodo size={17}/>Open My Tasks</button><button onClick={()=>act(()=>router.push('/app/notifications'))} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm hover:bg-black/5 dark:hover:bg-white/5"><Bell size={17}/>Open notifications</button></div>}
          {query.trim().length>=2&&search.isLoading&&<p className="p-6 text-center text-sm muted">Searching…</p>}
          {query.trim().length>=2&&search.data&&<div className="space-y-4">
            {search.data.tasks.length>0&&<div><p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider muted">Tasks</p>{search.data.tasks.map(task=><button key={task.id} onClick={()=>act(()=>router.push(`/app/tasks/${task.id}`))} className="flex w-full items-center justify-between gap-4 rounded-xl px-3 py-2.5 text-left hover:bg-black/5 dark:hover:bg-white/5"><div className="min-w-0"><p className="truncate text-sm font-medium">{task.title}</p><p className="text-xs muted">{task.identifier}</p></div><span className="rounded-full bg-black/5 px-2 py-1 text-[11px] muted dark:bg-white/5">{task.priority}</span></button>)}</div>}
            {search.data.projects.length>0&&<div><p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider muted">Projects</p>{search.data.projects.map(project=><button key={project.id} onClick={()=>act(()=>onSelectProject(project.id))} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-black/5 dark:hover:bg-white/5"><FolderKanban size={16}/><div><p className="text-sm font-medium">{project.name}</p><p className="text-xs muted">{project.key}</p></div></button>)}</div>}
            {search.data.comments.length>0&&<div><p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider muted">Comments</p>{search.data.comments.map(comment=><button key={comment.id} onClick={()=>act(()=>router.push(`/app/tasks/${comment.task_id}`))} className="w-full rounded-xl px-3 py-2.5 text-left hover:bg-black/5 dark:hover:bg-white/5"><p className="line-clamp-2 text-sm">{comment.body}</p><p className="mt-1 text-xs muted">in {comment.task_identifier}</p></button>)}</div>}
            {search.data.labels.length>0&&<div><p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wider muted">Labels</p><div className="flex flex-wrap gap-2 px-3 pb-2">{search.data.labels.map(label=><span key={label.id} className="rounded-full border border-[var(--line)] px-2.5 py-1 text-xs">{label.name}</span>)}</div></div>}
            {search.data.tasks.length+search.data.projects.length+search.data.comments.length+search.data.labels.length===0&&<p className="p-8 text-center text-sm muted">No accessible results for “{query}”.</p>}
          </div>}
        </div>
      </section>
    </div>}
  </>
}
