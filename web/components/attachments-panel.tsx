'use client'

import { useQuery } from '@tanstack/react-query'
import { Download, FileText, Loader2, Paperclip, Trash2, Upload, X } from 'lucide-react'
import { useRef, useState } from 'react'

import { ApiError, Attachment, AttachmentUrl, request } from '@/lib/api'

type EntityType = 'task'|'comment'|'project'

function formatBytes(value:number) {
  if(value < 1024) return `${value} B`
  if(value < 1024*1024) return `${(value/1024).toFixed(1)} KB`
  return `${(value/1024/1024).toFixed(1)} MB`
}

export function AttachmentsPanel({entityType,entityId,token,compact=false}:{entityType:EntityType;entityId:string;token:string;compact?:boolean}) {
  const [open,setOpen]=useState(!compact)
  const [uploading,setUploading]=useState(false)
  const [error,setError]=useState('')
  const [confirmDelete,setConfirmDelete]=useState<string|null>(null)
  const inputRef=useRef<HTMLInputElement>(null)
  const query=useQuery({
    queryKey:['attachments',entityType,entityId],
    queryFn:()=>request<Attachment[]>(`/api/v1/attachments?entity_type=${entityType}&entity_id=${entityId}`,{},token),
    enabled:open,
  })

  async function upload(file:File) {
    setUploading(true); setError('')
    const body=new FormData()
    body.set('entity_type',entityType)
    body.set('entity_id',entityId)
    body.set('file',file)
    try {
      await request<Attachment>('/api/v1/attachments',{method:'POST',body},token)
      await query.refetch()
    } catch (value) {
      setError(value instanceof ApiError ? value.message : 'Upload failed')
    } finally {
      setUploading(false)
      if(inputRef.current) inputRef.current.value=''
    }
  }

  async function download(item:Attachment) {
    setError('')
    try {
      const result=await request<AttachmentUrl>(`/api/v1/attachments/${item.id}/download`,{},token)
      window.open(result.url,'_blank','noopener,noreferrer')
    } catch (value) {
      setError(value instanceof ApiError ? value.message : 'Download failed')
    }
  }

  async function remove(item:Attachment) {
    setError('')
    try {
      await request<void>(`/api/v1/attachments/${item.id}`,{method:'DELETE'},token)
      setConfirmDelete(null)
      await query.refetch()
    } catch (value) {
      setError(value instanceof ApiError ? value.message : 'Delete failed')
    }
  }

  if(compact&&!open) return <button type="button" onClick={()=>setOpen(true)} className="inline-flex items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2 text-sm shadow-sm" aria-label="Open attachments"><Paperclip size={16}/>Attachments</button>

  return <section className="panel w-full rounded-2xl border border-[var(--line)] p-4 shadow-xl">
    <div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><Paperclip size={17}/><h3 className="font-medium">Attachments</h3><span className="rounded-full bg-black/5 px-2 py-0.5 text-xs muted dark:bg-white/10">{query.data?.length??0}</span></div>{compact&&<button type="button" onClick={()=>setOpen(false)} className="rounded-lg p-1.5 hover:bg-black/5 dark:hover:bg-white/10" aria-label="Close attachments"><X size={16}/></button>}</div>
    <div className="mt-3"><input ref={inputRef} type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.md,.csv,.json,.docx,.xlsx,.pptx" onChange={event=>{const file=event.target.files?.[0];if(file)void upload(file)}}/><button type="button" disabled={uploading} onClick={()=>inputRef.current?.click()} className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-60">{uploading?<Loader2 size={16} className="animate-spin"/>:<Upload size={16}/>} {uploading?'Uploading…':'Upload file'}</button><p className="mt-2 text-xs muted">PDF, images, text, Markdown, CSV, JSON, DOCX, XLSX or PPTX · max 20 MB</p></div>
    {error&&<p role="alert" className="mt-3 rounded-xl border border-red-500/20 bg-red-500/5 px-3 py-2 text-xs text-red-600 dark:text-red-300">{error}</p>}
    <div className="mt-4 space-y-2">{query.isLoading&&<div className="space-y-2">{[0,1].map(item=><div key={item} className="h-12 animate-pulse rounded-xl bg-black/5 dark:bg-white/5"/>)}</div>}{query.isError&&<p className="text-sm muted">Attachments could not be loaded.</p>}{!query.isLoading&&!query.isError&&query.data?.length===0&&<div className="rounded-xl border border-dashed border-[var(--line)] p-5 text-center"><Paperclip size={20} className="mx-auto muted"/><p className="mt-2 text-sm font-medium">No attachments yet</p><p className="mt-1 text-xs muted">Upload files that belong with this {entityType}.</p></div>}{query.data?.map(item=><div key={item.id} className="flex items-center gap-3 rounded-xl border border-[var(--line)] px-3 py-2"><div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-black/5 dark:bg-white/10"><FileText size={17}/></div><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium" title={item.safe_name}>{item.safe_name}</p><p className="text-xs muted">{formatBytes(item.size_bytes)} · {item.mime_type}</p></div><button type="button" onClick={()=>void download(item)} className="rounded-lg p-2 hover:bg-black/5 dark:hover:bg-white/10" aria-label={`Download ${item.safe_name}`}><Download size={16}/></button>{confirmDelete===item.id?<div className="flex items-center gap-1"><button type="button" onClick={()=>void remove(item)} className="rounded-lg bg-red-600 px-2 py-1 text-xs font-medium text-white">Confirm</button><button type="button" onClick={()=>setConfirmDelete(null)} className="rounded-lg px-2 py-1 text-xs muted">Cancel</button></div>:<button type="button" onClick={()=>setConfirmDelete(item.id)} className="rounded-lg p-2 text-red-600 hover:bg-red-500/10" aria-label={`Delete ${item.safe_name}`}><Trash2 size={16}/></button>}</div>)}</div>
  </section>
}
