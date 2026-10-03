'use client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { request, User } from '@/lib/api'

export type UserSettings = {
  theme:'light'|'dark'|'system'
  density:'comfortable'|'compact'
  week_start:number
  default_home:'home'|'my_tasks'|'calendar'
}

type AuthValue = {
  user:User|null
  token:string|null
  loading:boolean
  settings:UserSettings|null
  login:(email:string,password:string)=>Promise<UserSettings>
  register:(name:string,email:string,password:string)=>Promise<void>
  logout:()=>Promise<void>
  reloadSettings:()=>Promise<UserSettings|null>
}
const AuthContext = createContext<AuthValue | null>(null)

type AuthPayload = { access_token:string; user:User }
const defaultSettings:UserSettings={theme:'system',density:'comfortable',week_start:1,default_home:'home'}

export function applyUserSettings(settings:UserSettings){
  localStorage.setItem('tp-theme',settings.theme)
  localStorage.setItem('tp-density',settings.density)
  localStorage.setItem('tp-week-start',String(settings.week_start))
  localStorage.setItem('tp-default-home',settings.default_home)
  const dark=settings.theme==='dark'||(settings.theme==='system'&&matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark',dark)
  document.documentElement.dataset.density=settings.density
}

function landingPath(home:UserSettings['default_home']){
  if(home==='my_tasks')return '/app/my-tasks'
  if(home==='calendar')return '/app/calendar'
  return '/app'
}

export function defaultLandingPath(settings?:UserSettings|null){
  if(settings)return landingPath(settings.default_home)
  if(typeof window==='undefined')return '/app'
  const value=localStorage.getItem('tp-default-home') as UserSettings['default_home']|null
  return landingPath(value??'home')
}

function AuthProvider({children}:{children:React.ReactNode}) {
  const [user,setUser] = useState<User|null>(null)
  const [token,setToken] = useState<string|null>(null)
  const [settings,setSettings] = useState<UserSettings|null>(null)
  const [loading,setLoading] = useState(true)
  const accept = useCallback((data:AuthPayload) => { setUser(data.user); setToken(data.access_token) }, [])
  const loadSettings=useCallback(async(accessToken:string)=>{
    const next=await request<UserSettings>('/api/v1/settings/user',{},accessToken)
    setSettings(next)
    applyUserSettings(next)
    return next
  },[])
  const reloadSettings=useCallback(async()=>{
    if(!token)return null
    try{return await loadSettings(token)}catch{return null}
  },[token,loadSettings])
  useEffect(() => {
    request<AuthPayload>('/api/v1/auth/refresh',{method:'POST',body:JSON.stringify({client:'web'})})
      .then(data=>{accept(data);void loadSettings(data.access_token).catch(()=>{})})
      .catch(()=>{})
      .finally(()=>setLoading(false))
  },[accept,loadSettings])
  const login = useCallback(async(email:string,password:string)=>{
    const data=await request<AuthPayload>('/api/v1/auth/login',{method:'POST',body:JSON.stringify({email,password,client:'web'})})
    accept(data)
    try{return await loadSettings(data.access_token)}catch{return defaultSettings}
  },[accept,loadSettings])
  const register = useCallback(async(name:string,email:string,password:string)=>{
    const data=await request<AuthPayload>('/api/v1/auth/register',{method:'POST',body:JSON.stringify({name,email,password})})
    accept(data)
    void loadSettings(data.access_token).catch(()=>{})
  },[accept,loadSettings])
  const logout = useCallback(async()=>{
    await request('/api/v1/auth/logout',{method:'POST'}).catch(()=>{})
    setUser(null);setToken(null);setSettings(null)
  },[])
  return <AuthContext.Provider value={{user,token,loading,settings,login,register,logout,reloadSettings}}>{children}</AuthContext.Provider>
}

export function useAuth(){ const value=useContext(AuthContext); if(!value) throw new Error('AuthProvider missing'); return value }

export function Providers({children}:{children:React.ReactNode}) {
  const [client] = useState(()=>new QueryClient({defaultOptions:{queries:{staleTime:15_000,retry:1}}}))
  return <QueryClientProvider client={client}><AuthProvider>{children}</AuthProvider></QueryClientProvider>
}
