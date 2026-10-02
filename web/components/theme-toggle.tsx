'use client'
import { Monitor, Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'

type ThemeMode='light'|'dark'|'system'

function apply(mode:ThemeMode){
  const dark=mode==='dark'||(mode==='system'&&matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark',dark)
}

export function ThemeToggle(){
  const [mode,setMode]=useState<ThemeMode>('system')
  useEffect(()=>{
    const saved=localStorage.getItem('tp-theme')
    const value:ThemeMode=saved==='dark'||saved==='light'||saved==='system'?saved:'system'
    setMode(value)
    apply(value)
    const media=matchMedia('(prefers-color-scheme: dark)')
    const listener=()=>{if((localStorage.getItem('tp-theme')??'system')==='system')apply('system')}
    media.addEventListener('change',listener)
    return()=>media.removeEventListener('change',listener)
  },[])
  const cycle=()=>{
    const next:ThemeMode=mode==='system'?'light':mode==='light'?'dark':'system'
    setMode(next)
    localStorage.setItem('tp-theme',next)
    apply(next)
  }
  const label=`Theme: ${mode}. Click to switch.`
  return <button aria-label={label} title={label} onClick={cycle} className="focus-ring rounded-xl border border-[var(--line)] p-2 hover:bg-black/5 dark:hover:bg-white/5">{mode==='light'?<Sun size={18}/>:mode==='dark'?<Moon size={18}/>:<Monitor size={18}/>}</button>
}
