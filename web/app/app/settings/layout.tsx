'use client'

import Link from 'next/link'

import { useAuth } from '@/components/providers'

export default function SettingsLayout({children}:{children:React.ReactNode}){
  const {user}=useAuth()
  return <>
    <nav className="sticky top-0 z-30 border-b border-[var(--line)] bg-[var(--panel)]/95 backdrop-blur">
      <div className="mx-auto flex max-w-5xl gap-2 overflow-x-auto px-4 py-2 sm:px-6">
        <Link href="/app/settings/account" className="whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium hover:bg-black/5 dark:hover:bg-white/5">Account & security</Link>
        <Link href="/app/settings/workspaces" className="whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium hover:bg-black/5 dark:hover:bg-white/5">Workspaces</Link>
        {user?.is_admin&&<Link href="/app/admin" className="whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium text-indigo-600 hover:bg-indigo-500/10">Admin</Link>}
      </div>
    </nav>
    {children}
  </>
}
