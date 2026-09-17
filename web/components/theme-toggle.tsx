'use client'
import { Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'

export function ThemeToggle(){
  const [dark,setDark]=useState(false)
  useEffect(()=>{ const saved=localStorage.getItem('tp-theme'); const value=saved==='dark'||(!saved&&matchMedia('(prefers-color-scheme: dark)').matches); setDark(value); document.documentElement.classList.toggle('dark',value) },[])
  const toggle=()=>{ const value=!dark; setDark(value); document.documentElement.classList.toggle('dark',value); localStorage.setItem('tp-theme',value?'dark':'light') }
  return <button aria-label="Toggle theme" onClick={toggle} className="focus-ring rounded-xl border border-[var(--line)] p-2 hover:bg-black/5 dark:hover:bg-white/5">{dark?<Sun size={18}/>:<Moon size={18}/>}</button>
}
