'use client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { request, User } from '@/lib/api'

type AuthValue = { user:User|null; token:string|null; loading:boolean; login:(email:string,password:string)=>Promise<void>; register:(name:string,email:string,password:string)=>Promise<void>; logout:()=>Promise<void> }
const AuthContext = createContext<AuthValue | null>(null)

type AuthPayload = { access_token:string; user:User }

function AuthProvider({children}:{children:React.ReactNode}) {
  const [user,setUser] = useState<User|null>(null)
  const [token,setToken] = useState<string|null>(null)
  const [loading,setLoading] = useState(true)
  const accept = useCallback((data:AuthPayload) => { setUser(data.user); setToken(data.access_token) }, [])
  useEffect(() => {
    request<AuthPayload>('/api/v1/auth/refresh',{method:'POST',body:JSON.stringify({client:'web'})}).then(accept).catch(()=>{}).finally(()=>setLoading(false))
  },[accept])
  const login = useCallback(async(email:string,password:string)=>accept(await request<AuthPayload>('/api/v1/auth/login',{method:'POST',body:JSON.stringify({email,password,client:'web'})})),[accept])
  const register = useCallback(async(name:string,email:string,password:string)=>accept(await request<AuthPayload>('/api/v1/auth/register',{method:'POST',body:JSON.stringify({name,email,password})})),[accept])
  const logout = useCallback(async()=>{ await request('/api/v1/auth/logout',{method:'POST'}).catch(()=>{}); setUser(null); setToken(null) },[])
  return <AuthContext.Provider value={{user,token,loading,login,register,logout}}>{children}</AuthContext.Provider>
}

export function useAuth(){ const value=useContext(AuthContext); if(!value) throw new Error('AuthProvider missing'); return value }

export function Providers({children}:{children:React.ReactNode}) {
  const [client] = useState(()=>new QueryClient({defaultOptions:{queries:{staleTime:15_000,retry:1}}}))
  return <QueryClientProvider client={client}><AuthProvider>{children}</AuthProvider></QueryClientProvider>
}
