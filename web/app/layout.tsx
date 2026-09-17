import type { Metadata } from 'next'
import './globals.css'
import { Providers } from '@/components/providers'

export const metadata: Metadata = {
  title: 'TaskPilot — Work moves forward',
  description: 'Collaborative project and task management for modern teams.'
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning><body><Providers>{children}</Providers></body></html>
}
