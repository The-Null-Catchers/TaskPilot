'use client'

import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, BellRing, Laptop, Mail, Smartphone } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

import { useAuth } from '@/components/providers'
import { request } from '@/lib/api'

type Preference={
  user_id:string
  in_app_enabled:boolean
  email_enabled:boolean
  browser_enabled:boolean
  mobile_enabled:boolean
  digest_frequency:'instant'|'hourly'|'daily'|'off'
  assignments_enabled:boolean
  mentions_enabled:boolean
  comments_enabled:boolean
  deadlines_enabled:boolean
  dependencies_enabled:boolean
  created_at:string
  updated_at:string
}
type PreferenceBooleanField=
  'in_app_enabled'|'email_enabled'|'browser_enabled'|'mobile_enabled'|
  'assignments_enabled'|'mentions_enabled'|'comments_enabled'|'deadlines_enabled'|'dependencies_enabled'
type ProviderConfig={web_push_enabled:boolean;web_push_public_key:string|null;fcm_enabled:boolean;apns_enabled:boolean}
type Subscription={id:string;channel:string;device_name:string|null;platform:string|null;last_used_at:string;revoked_at:string|null;created_at:string}

function vapidKey(value:string){
  const padding='='.repeat((4-value.length%4)%4)
  const base64=(value+padding).replace(/-/g,'+').replace(/_/g,'/')
  const raw=window.atob(base64)
  return Uint8Array.from([...raw].map(char=>char.charCodeAt(0)))
}

export default function NotificationSettingsPage(){
  const {token,loading}=useAuth()
  const router=useRouter()
  const [busy,setBusy]=useState('')
  const [notice,setNotice]=useState('')
  const [error,setError]=useState('')

  useEffect(()=>{if(!loading&&!token)router.replace('/login?next=%2Fapp%2Fsettings%2Fnotifications')},[loading,token,router])

  const preference=useQuery({
    queryKey:['notification-preferences'],
    queryFn:()=>request<Preference>('/api/v1/notifications/preferences',{},token),
    enabled:!!token,
  })
  const providers=useQuery({
    queryKey:['notification-provider-config'],
    queryFn:()=>request<ProviderConfig>('/api/v1/notifications/provider-config',{},token),
    enabled:!!token,
  })
  const subscriptions=useQuery({
    queryKey:['notification-subscriptions'],
    queryFn:()=>request<Subscription[]>('/api/v1/notifications/subscriptions',{},token),
    enabled:!!token,
  })

  async function refresh(){await Promise.all([preference.refetch(),providers.refetch(),subscriptions.refetch()])}

  async function patch(values:Partial<Preference>){
    if(!token)return
    setBusy('preferences');setError('');setNotice('')
    try{
      await request<Preference>('/api/v1/notifications/preferences',{
        method:'PATCH',
        body:JSON.stringify(values),
      },token)
      setNotice('Notification preferences saved.')
      await preference.refetch()
    }catch(err){
      setError(err instanceof Error?err.message:'Could not update notification preferences.')
    }finally{setBusy('')}
  }

  async function enableBrowser(){
    if(!token||!providers.data?.web_push_enabled||!providers.data.web_push_public_key)return
    setBusy('browser');setError('');setNotice('')
    try{
      if(!('serviceWorker'in navigator)||!('PushManager'in window))throw new Error('This browser does not support Web Push')
      const permission=await globalThis.Notification.requestPermission()
      if(permission!=='granted')throw new Error('Browser notification permission was not granted')
      const registration=await navigator.serviceWorker.register('/taskpilot-sw.js')
      await navigator.serviceWorker.ready
      let subscription=await registration.pushManager.getSubscription()
      if(!subscription){
        subscription=await registration.pushManager.subscribe({
          userVisibleOnly:true,
          applicationServerKey:vapidKey(providers.data.web_push_public_key) as BufferSource,
        })
      }
      const serialized=subscription.toJSON()
      await request('/api/v1/notifications/subscriptions',{
        method:'POST',
        body:JSON.stringify({
          channel:'web_push',
          target:subscription.endpoint,
          config:{keys:serialized.keys??{}},
          device_name:navigator.userAgent.slice(0,160),
          platform:navigator.platform?.slice(0,40)||'web',
        }),
      },token)
      await request('/api/v1/notifications/preferences',{
        method:'PATCH',
        body:JSON.stringify({browser_enabled:true}),
      },token)
      setNotice('Browser notifications are enabled for this device.')
      await refresh()
    }catch(err){
      setError(err instanceof Error?err.message:'Could not enable browser notifications.')
    }finally{setBusy('')}
  }

  async function disableBrowser(){
    if(!token)return
    setBusy('browser');setError('');setNotice('')
    try{
      for(const item of subscriptions.data?.filter(item=>item.channel==='web_push'&&!item.revoked_at)??[]){
        await request(`/api/v1/notifications/subscriptions/${item.id}`,{method:'DELETE'},token)
      }
      if('serviceWorker'in navigator){
        const registration=await navigator.serviceWorker.getRegistration()
        const push=await registration?.pushManager.getSubscription()
        await push?.unsubscribe()
      }
      await request('/api/v1/notifications/preferences',{
        method:'PATCH',
        body:JSON.stringify({browser_enabled:false}),
      },token)
      setNotice('Browser notifications are disabled.')
      await refresh()
    }catch(err){
      setError(err instanceof Error?err.message:'Could not disable browser notifications.')
    }finally{setBusy('')}
  }

  async function revokeSubscription(id:string){
    if(!token)return
    setBusy(`subscription:${id}`);setError('');setNotice('')
    try{
      await request(`/api/v1/notifications/subscriptions/${id}`,{method:'DELETE'},token)
      setNotice('Push endpoint revoked.')
      await subscriptions.refetch()
    }catch(err){
      setError(err instanceof Error?err.message:'Could not revoke push endpoint.')
    }finally{setBusy('')}
  }

  if(loading||!token)return <div className="grid min-h-screen place-items-center muted">Loading notification settings…</div>
  if(preference.isLoading||providers.isLoading||subscriptions.isLoading)return <div className="grid min-h-screen place-items-center muted">Loading notification settings…</div>
  if(!preference.data)return <div className="grid min-h-screen place-items-center text-red-600">Could not load notification settings.</div>

  const activeWeb=subscriptions.data?.some(item=>item.channel==='web_push'&&!item.revoked_at)??false
  const activeSubscriptions=subscriptions.data?.filter(item=>!item.revoked_at)??[]
  const toggle=(field:PreferenceBooleanField,label:string,description:string)=><label className="flex items-start justify-between gap-4 rounded-xl border border-[var(--line)] p-4"><span><span className="block text-sm font-medium">{label}</span><span className="mt-1 block text-xs leading-5 muted">{description}</span></span><input type="checkbox" checked={preference.data[field]} disabled={!!busy} onChange={e=>void patch({[field]:e.target.checked} as Partial<Preference>)} className="mt-1 h-4 w-4"/></label>

  return <main className="min-h-screen bg-[var(--bg)]">
    <header className="border-b border-[var(--line)] bg-[var(--panel)]">
      <div className="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4 sm:px-6">
        <Link href="/app" className="rounded-xl border border-[var(--line)] p-2" aria-label="Back to TaskPilot"><ArrowLeft size={18}/></Link>
        <div><p className="text-xs muted">Settings</p><h1 className="font-semibold">Notifications</h1></div>
      </div>
    </header>

    <div className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6">
      {notice&&<div className="rounded-2xl bg-emerald-500/10 p-4 text-sm text-emerald-700 dark:text-emerald-300">{notice}</div>}
      {error&&<div role="alert" className="rounded-2xl bg-red-500/10 p-4 text-sm text-red-600">{error}</div>}

      <section className="panel rounded-2xl p-5 sm:p-6">
        <div className="flex items-start gap-3"><BellRing className="mt-0.5 text-indigo-600"/><div><h2 className="font-semibold">Delivery channels</h2><p className="mt-1 text-sm muted">Choose where TaskPilot can reach you. Server-side providers must be configured before external delivery is available.</p></div></div>
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {toggle('in_app_enabled','In-app inbox','Store and show relevant notifications inside TaskPilot.')}
          {toggle('email_enabled','Email','Allow instant or digest email delivery.')}
          {toggle('mobile_enabled','Mobile push','Allow registered Flutter devices to receive FCM or APNs push.')}
          <div className="rounded-xl border border-[var(--line)] p-4">
            <div className="flex items-start justify-between gap-3"><span><span className="block text-sm font-medium">Browser push</span><span className="mt-1 block text-xs leading-5 muted">{providers.data?.web_push_enabled?'VAPID is configured on the server.':'VAPID keys are not configured on the server.'}</span></span><Laptop size={18} className="muted"/></div>
            <button disabled={!providers.data?.web_push_enabled||busy==='browser'} onClick={()=>void(activeWeb?disableBrowser():enableBrowser())} className="mt-4 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40">{busy==='browser'?'Updating…':activeWeb?'Disable on this browser':'Enable on this browser'}</button>
          </div>
        </div>
        <label className="mt-4 block text-sm font-medium">Email frequency<select value={preference.data.digest_frequency} disabled={!!busy} onChange={e=>void patch({digest_frequency:e.target.value as Preference['digest_frequency']})} className="mt-2 w-full max-w-md rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5"><option value="instant">Instant</option><option value="hourly">Hourly digest</option><option value="daily">Daily digest</option><option value="off">Off</option></select></label>
      </section>

      <section className="panel rounded-2xl p-5 sm:p-6">
        <h2 className="font-semibold">Event preferences</h2>
        <p className="mt-1 text-sm muted">Fine-tune which collaboration events can trigger notification delivery.</p>
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {toggle('assignments_enabled','Assignments','When work is assigned to you.')}
          {toggle('mentions_enabled','Mentions','When a collaborator mentions you.')}
          {toggle('comments_enabled','Comments','Relevant task comments and watched-task activity.')}
          {toggle('deadlines_enabled','Deadlines','Upcoming task deadlines.')}
          {toggle('dependencies_enabled','Dependencies','Blockers and dependency resolution changes.')}
        </div>
      </section>

      <section className="panel rounded-2xl p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold">Registered push endpoints</h2><p className="mt-1 text-sm muted">Revoke stale browsers or mobile devices without signing out the account.</p></div><div className="flex gap-2 text-xs"><span className="rounded-full bg-black/5 px-2.5 py-1 muted dark:bg-white/5">FCM {providers.data?.fcm_enabled?'ready':'off'}</span><span className="rounded-full bg-black/5 px-2.5 py-1 muted dark:bg-white/5">APNs {providers.data?.apns_enabled?'ready':'off'}</span></div></div>
        <div className="mt-5 divide-y divide-[var(--line)]">
          {activeSubscriptions.map(item=><div key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-4"><div className="flex min-w-0 items-start gap-3">{item.channel==='web_push'?<Laptop size={18} className="mt-0.5 muted"/>:<Smartphone size={18} className="mt-0.5 muted"/>}<div className="min-w-0"><p className="truncate text-sm font-medium">{item.device_name||item.platform||'Push endpoint'}</p><p className="mt-1 text-xs muted">{item.channel.replace('_',' ')} · last used {new Date(item.last_used_at).toLocaleString()}</p></div></div><button disabled={busy===`subscription:${item.id}`} onClick={()=>void revokeSubscription(item.id)} className="rounded-xl border border-red-500/20 px-3 py-2 text-xs font-medium text-red-600 disabled:opacity-40">Revoke</button></div>)}
          {activeSubscriptions.length===0&&<div className="py-8 text-center"><Mail className="mx-auto muted"/><p className="mt-3 text-sm font-medium">No active push endpoints</p><p className="mt-1 text-xs muted">Enable browser notifications here or sign into the Flutter app after push providers are configured.</p></div>}
        </div>
      </section>

      <div className="flex justify-end"><Link href="/app/notifications" className="rounded-xl border border-[var(--line)] px-4 py-2.5 text-sm font-medium">Open notification inbox</Link></div>
    </div>
  </main>
}
