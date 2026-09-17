'use client'

import Link from 'next/link'
import { FormEvent, useState } from 'react'

import { request } from '@/lib/api'

type Result={message:string;development_token?:string}

export default function ForgotPasswordPage(){
  const [email,setEmail]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [result,setResult]=useState<Result|null>(null)
  async function submit(event:FormEvent){event.preventDefault();setBusy(true);setError('');try{setResult(await request<Result>('/api/v1/auth/forgot-password',{method:'POST',body:JSON.stringify({email})}))}catch(err){setError(err instanceof Error?err.message:'Could not submit request')}finally{setBusy(false)}}
  return <main className="grid min-h-screen place-items-center px-6"><div className="w-full max-w-md"><Link href="/" className="mb-8 inline-flex items-center gap-2 text-xl font-semibold"><span className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-600 text-white">T</span>TaskPilot</Link><section className="panel rounded-3xl p-7 shadow-soft"><h1 className="text-2xl font-semibold">Reset your password</h1><p className="mt-2 text-sm muted">Enter your account email. For privacy, TaskPilot shows the same result whether or not the address exists.</p>{result?<div className="mt-6 rounded-2xl border border-[var(--line)] p-4"><p className="text-sm">{result.message}</p>{result.development_token&&<Link className="mt-3 inline-block text-sm font-medium text-indigo-600" href={`/reset-password?token=${encodeURIComponent(result.development_token)}`}>Open development reset link</Link>}<button onClick={()=>setResult(null)} className="mt-4 block text-sm muted">Use another email</button></div>:<form onSubmit={submit} className="mt-7 space-y-4"><label className="block text-sm font-medium">Email<input required type="email" value={email} onChange={e=>setEmail(e.target.value)} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-3 outline-none focus:border-indigo-500"/></label>{error&&<p role="alert" className="rounded-xl bg-red-500/10 p-3 text-sm text-red-600">{error}</p>}<button disabled={busy} className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-semibold text-white disabled:opacity-50">{busy?'Sending…':'Send reset link'}</button></form>}<Link href="/login" className="mt-5 block text-center text-sm muted">Back to sign in</Link></section></div></main>
}
