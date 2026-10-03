'use client'

import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft, LayoutTemplate, MonitorCog } from 'lucide-react'
import Link from 'next/link'
import { FormEvent, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

import { applyUserSettings, useAuth } from '@/components/providers'
import { request } from '@/lib/api'

type UserSettings={
  theme:'light'|'dark'|'system'
  density:'comfortable'|'compact'
  week_start:number
  default_home:'home'|'my_tasks'|'calendar'
  updated_at:string
}

export default function PreferencesPage(){
  const {token,loading,reloadSettings}=useAuth()
  const router=useRouter()
  const [notice,setNotice]=useState('')
  const [error,setError]=useState('')
  useEffect(()=>{if(!loading&&!token)router.replace('/login')},[loading,token,router])

  const settings=useQuery({
    queryKey:['user-settings'],
    queryFn:()=>request<UserSettings>('/api/v1/settings/user',{},token),
    enabled:!!token,
  })
  const save=useMutation({
    mutationFn:(payload:Partial<UserSettings>)=>request<UserSettings>('/api/v1/settings/user',{
      method:'PATCH',
      body:JSON.stringify(payload),
    },token),
    onSuccess:(data)=>{
      setError('');setNotice('Preferences saved across your TaskPilot devices.')
      applyUserSettings(data)
      void reloadSettings()
      void settings.refetch()
    },
    onError:(err)=>{setNotice('');setError(err instanceof Error?err.message:'Could not save preferences.')},
  })

  async function submit(event:FormEvent<HTMLFormElement>){
    event.preventDefault()
    const form=new FormData(event.currentTarget)
    await save.mutateAsync({
      theme:String(form.get('theme')) as UserSettings['theme'],
      density:String(form.get('density')) as UserSettings['density'],
      week_start:Number(form.get('week_start')),
      default_home:String(form.get('default_home')) as UserSettings['default_home'],
    }).catch(()=>undefined)
  }

  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading preferences…</div>
  if(settings.isLoading)return <div className="grid min-h-screen place-items-center muted">Loading preferences…</div>
  if(!settings.data)return <div className="grid min-h-screen place-items-center text-red-600">Could not load preferences.</div>

  return <main className="min-h-screen bg-[var(--bg)]">
    <header className="border-b border-[var(--line)] bg-[var(--panel)]">
      <div className="mx-auto flex h-16 max-w-4xl items-center gap-3 px-4 sm:px-6">
        <Link href="/app" className="rounded-xl border border-[var(--line)] p-2" aria-label="Back to TaskPilot"><ArrowLeft size={18}/></Link>
        <div><p className="text-xs muted">Settings</p><h1 className="font-semibold">Preferences</h1></div>
      </div>
    </header>
    <div className="mx-auto max-w-4xl p-4 sm:p-6">
      {notice&&<div className="mb-4 rounded-2xl bg-emerald-500/10 p-4 text-sm text-emerald-700 dark:text-emerald-300">{notice}</div>}
      {error&&<div role="alert" className="mb-4 rounded-2xl bg-red-500/10 p-4 text-sm text-red-600">{error}</div>}
      <form onSubmit={submit} className="panel rounded-2xl p-5 sm:p-6" key={settings.data.updated_at}>
        <div className="flex items-start gap-3"><MonitorCog className="mt-0.5 text-indigo-600"/><div><h2 className="font-semibold">Personal experience</h2><p className="mt-1 text-sm muted">These preferences follow your account instead of being tied to one browser.</p></div></div>
        <div className="mt-6 grid gap-5 sm:grid-cols-2">
          <label className="text-sm font-medium">Theme<select name="theme" defaultValue={settings.data.theme} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5"><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label>
          <label className="text-sm font-medium">Density<select name="density" defaultValue={settings.data.density} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5"><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label>
          <label className="text-sm font-medium">Week starts on<select name="week_start" defaultValue={settings.data.week_start} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5"><option value={0}>Sunday</option><option value={1}>Monday</option><option value={6}>Saturday</option></select></label>
          <label className="text-sm font-medium">Default landing page<select name="default_home" defaultValue={settings.data.default_home} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5"><option value="home">Projects</option><option value="my_tasks">My Tasks</option><option value="calendar">Calendar</option></select></label>
        </div>
        <div className="mt-6 flex items-center justify-between gap-4 rounded-xl bg-black/[.025] p-4 dark:bg-white/[.025]"><div className="flex items-center gap-3"><LayoutTemplate size={18}/><p className="text-sm muted">Theme, density, week layout, and landing page apply to the signed-in experience.</p></div><button disabled={save.isPending} className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{save.isPending?'Saving…':'Save preferences'}</button></div>
      </form>
    </div>
  </main>
}
