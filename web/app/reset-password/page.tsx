'use client'

import Link from 'next/link'
import { FormEvent, useEffect, useState } from 'react'

import { request } from '@/lib/api'

export default function ResetPasswordPage(){
  const [token,setToken]=useState('')
  const [password,setPassword]=useState('')
  const [confirm,setConfirm]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [done,setDone]=useState(false)
  useEffect(()=>{setToken(new URLSearchParams(window.location.search).get('token')??'')},[])
  async function submit(event:FormEvent){event.preventDefault();setError('');if(password!==confirm){setError('Passwords do not match.');return}setBusy(true);try{await request('/api/v1/auth/reset-password',{method:'POST',body:JSON.stringify({token,password})});setDone(true)}catch(err){setError(err instanceof Error?err.message:'Could not reset password')}finally{setBusy(false)}}
  return <main className="grid min-h-screen place-items-center px-6"><section className="panel w-full max-w-md rounded-3xl p-7 shadow-soft"><h1 className="text-2xl font-semibold">Choose a new password</h1>{done?<div className="mt-6"><p className="rounded-2xl bg-emerald-500/10 p-4 text-sm text-emerald-700 dark:text-emerald-300">Password updated. Existing sessions have been signed out.</p><Link href="/login" className="mt-5 block rounded-xl bg-indigo-600 px-4 py-3 text-center font-semibold text-white">Sign in</Link></div>:<form onSubmit={submit} className="mt-6 space-y-4"><label className="block text-sm font-medium">Reset token<input required value={token} onChange={e=>setToken(e.target.value)} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-3 text-sm outline-none focus:border-indigo-500"/></label><label className="block text-sm font-medium">New password<input required minLength={10} type="password" value={password} onChange={e=>setPassword(e.target.value)} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-3 outline-none focus:border-indigo-500"/></label><label className="block text-sm font-medium">Confirm password<input required minLength={10} type="password" value={confirm} onChange={e=>setConfirm(e.target.value)} className="mt-2 w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-3 outline-none focus:border-indigo-500"/></label>{error&&<p role="alert" className="rounded-xl bg-red-500/10 p-3 text-sm text-red-600">{error}</p>}<button disabled={busy||!token} className="w-full rounded-xl bg-indigo-600 px-4 py-3 font-semibold text-white disabled:opacity-50">{busy?'Updating…':'Reset password'}</button></form>}<Link href="/login" className="mt-5 block text-center text-sm muted">Back to sign in</Link></section></main>
}
