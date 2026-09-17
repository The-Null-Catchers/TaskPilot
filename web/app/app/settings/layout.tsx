import Link from 'next/link'

export default function SettingsLayout({children}:{children:React.ReactNode}){
  return <>
    <nav className="sticky top-0 z-30 border-b border-[var(--line)] bg-[var(--panel)]/95 backdrop-blur">
      <div className="mx-auto flex max-w-5xl gap-2 overflow-x-auto px-4 py-2 sm:px-6">
        <Link href="/app/settings/account" className="whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium hover:bg-black/5 dark:hover:bg-white/5">Account & security</Link>
        <Link href="/app/settings/workspaces" className="whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium hover:bg-black/5 dark:hover:bg-white/5">Workspaces</Link>
      </div>
    </nav>
    {children}
  </>
}
