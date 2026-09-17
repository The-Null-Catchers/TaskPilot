'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

import { request } from '@/lib/api'

export default function ConfirmEmailPage(){
  const [state,setState]=useState<'loading'|'success'|'error'>('loading')
  const [message,setMessage]=useState('Confirming your new email…')
  useEffect(()=>{const token=new URLSearchParams(window.location.search).get('token');if(!token){setState('error');setMessage('Confirmation token is missing.');return}request('/api/v1/auth/change-email/confirm',{method:'POST',body:JSON.stringify({token})}).then(()=>{setState('success');setMessage('Your email was changed and verified. Sign in again on your devices.')}).catch(err=>{setState('error');setMessage(err instanceof Error?err.message:'Could not confirm email')})},[])
  return <main className="grid min-h-screen place-items-center px-6"><section className="panel w-full max-w-md rounded-3xl p-8 text-center shadow-soft"><div className={`mx-auto h-3 w-3 rounded-full ${state==='loading'?'animate-pulse bg-indigo-500':state==='success'?'bg-emerald-500':'bg-red-500'}`}/><h1 className="mt-5 text-2xl font-semibold">Email change</h1><p className="mt-3 text-sm muted">{message}</p><Link href="/login" className="mt-6 inline-block rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white">Sign in</Link></section></main>
}
