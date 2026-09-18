'use client'

import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Check, LayoutTemplate, Sparkles } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { FormEvent, useEffect, useState } from 'react'

import { useAuth } from '@/components/providers'
import { Project, request, Workspace } from '@/lib/api'

type Template={key:string;name:string;description:string}
type Catalog={project_templates:Template[];task_templates:{key:string;name:string}[]}

export default function OnboardingPage(){
  const {token,loading,user}=useAuth()
  const router=useRouter()
  const [template,setTemplate]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')

  useEffect(()=>{if(!loading&&!token)router.replace('/login')},[loading,token,router])
  const workspaces=useQuery({queryKey:['onboarding-workspaces'],queryFn:()=>request<Workspace[]>('/api/v1/workspaces',{},token),enabled:!!token})
  const templates=useQuery({queryKey:['onboarding-templates'],queryFn:()=>request<Catalog>('/api/v1/templates',{},token),enabled:!!token})
  useEffect(()=>{if(!template&&templates.data?.project_templates[0])setTemplate(templates.data.project_templates[0].key)},[template,templates.data])

  async function create(e:FormEvent<HTMLFormElement>){
    e.preventDefault()
    const workspace=workspaces.data?.[0]
    if(!token||!workspace){setError('Your personal workspace is not ready yet.');return}
    const f=new FormData(e.currentTarget)
    setBusy(true);setError('')
    try{
      const project=await request<Project>('/api/v1/templates/projects/apply',{method:'POST',body:JSON.stringify({workspace_id:workspace.id,template_key:template,name:String(f.get('name')??'').trim(),key:String(f.get('key')??'').trim().toUpperCase()})},token)
      router.replace('/app?project='+encodeURIComponent(project.id))
    }catch(err){setError(err instanceof Error?err.message:'Could not create your first project')}finally{setBusy(false)}
  }

  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Preparing your workspace…</div>
  return <main className="min-h-screen bg-[var(--bg)] px-4 py-10 sm:px-6"><div className="mx-auto max-w-5xl">
    <div className="flex items-center justify-between gap-4"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-2xl bg-indigo-600 font-semibold text-white">T</span><div><p className="text-xs font-semibold uppercase tracking-[.18em] text-indigo-600">Welcome to TaskPilot</p><p className="text-sm muted">Your workspace is ready.</p></div></div><button onClick={()=>router.replace('/app')} className="rounded-xl px-3 py-2 text-sm muted hover:bg-black/5 dark:hover:bg-white/5">Skip for now</button></div>
    <section className="mt-10 grid gap-8 lg:grid-cols-[.8fr_1.2fr] lg:items-start"><div>
      <div className="inline-flex items-center gap-2 rounded-full bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-600"><Sparkles size={14}/> First project</div>
      <h1 className="mt-5 text-4xl font-semibold tracking-[-.04em] sm:text-5xl">Start with a workflow, not an empty screen.</h1>
      <p className="mt-4 max-w-xl text-base leading-7 muted">Choose the closest starting point. TaskPilot creates the board structure, useful labels, and starter tasks; you can change everything later.</p>
      <div className="mt-7 space-y-3 text-sm">{['Choose a proven project structure','Create starter tasks and labels automatically','Open the board and start collaborating'].map(item=><div key={item} className="flex items-center gap-3"><span className="grid h-7 w-7 place-items-center rounded-full bg-emerald-500/10 text-emerald-600"><Check size={15}/></span><span>{item}</span></div>)}</div>
    </div>
    <form onSubmit={create} className="panel rounded-3xl p-5 shadow-soft sm:p-7">
      <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-2xl bg-indigo-500/10 text-indigo-600"><LayoutTemplate size={20}/></span><div><h2 className="font-semibold">Choose a template</h2><p className="text-sm muted">Pick the workflow that matches your work.</p></div></div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">{templates.data?.project_templates.map(item=><button type="button" key={item.key} onClick={()=>setTemplate(item.key)} className={`rounded-2xl border p-4 text-left transition ${template===item.key?'border-indigo-500 bg-indigo-500/[.07] ring-2 ring-indigo-500/10':'border-[var(--line)] hover:bg-black/[.025] dark:hover:bg-white/[.025]'}`}><div className="flex items-start justify-between gap-3"><p className="font-medium">{item.name}</p>{template===item.key&&<Check size={17} className="shrink-0 text-indigo-600"/>}</div><p className="mt-2 text-xs leading-5 muted">{item.description}</p></button>)}{templates.isLoading&&<p className="text-sm muted">Loading templates…</p>}</div>
      <div className="mt-6 grid gap-4 sm:grid-cols-[1fr_120px]"><label className="text-sm font-medium">Project name<input required name="name" defaultValue={(user?.name?.split(' ')[0]??'My')+' Project'} maxLength={160} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-3 outline-none focus:border-indigo-500"/></label><label className="text-sm font-medium">Key<input required name="key" defaultValue="FIRST" minLength={2} maxLength={12} pattern="[A-Za-z][A-Za-z0-9]*" className="mt-2 w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-3 uppercase outline-none focus:border-indigo-500"/></label></div>
      {error&&<p role="alert" className="mt-4 rounded-xl bg-red-500/10 p-3 text-sm text-red-600">{error}</p>}
      <button disabled={busy||!template||workspaces.isLoading} className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 font-semibold text-white disabled:opacity-50">{busy?'Creating your project…':'Create project and continue'}<ArrowRight size={17}/></button>
      <p className="mt-3 text-center text-xs muted">Templates are only a starting point. Columns, labels, and tasks remain fully editable.</p>
    </form></section>
  </div></main>
}
