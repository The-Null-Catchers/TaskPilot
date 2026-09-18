'use client'

import { useQuery } from '@tanstack/react-query'
import { MessageSquare, Pencil, Trash2, X } from 'lucide-react'
import { FormEvent, useMemo, useState } from 'react'

import { AttachmentsPanel } from '@/components/attachments-panel'
import { useAuth } from '@/components/providers'
import { Comment, CommentReaction, request, Task, WorkspaceMember } from '@/lib/api'

const REACTIONS=['👍','👎','❤️','🎉','😄','🚀','👀'] as const

function ReactionBar({taskId,commentId,token,currentUserId}:{taskId:string;commentId:string;token:string;currentUserId?:string}) {
  const query=useQuery({
    queryKey:['comment-reactions',commentId],
    queryFn:()=>request<CommentReaction[]>(`/api/v1/tasks/${taskId}/comments/${commentId}/reactions`,{},token),
  })

  async function toggle(emoji:string) {
    const mine=query.data?.find(item=>item.user_id===currentUserId&&item.emoji===emoji)
    if(mine) {
      await request<void>(`/api/v1/tasks/${taskId}/comments/${commentId}/reactions/${mine.id}`,{method:'DELETE'},token)
    } else {
      await request<CommentReaction>(`/api/v1/tasks/${taskId}/comments/${commentId}/reactions`,{method:'POST',body:JSON.stringify({emoji})},token)
    }
    await query.refetch()
  }

  const counts=useMemo(()=>{
    const result=new Map<string,number>()
    for(const item of query.data??[])result.set(item.emoji,(result.get(item.emoji)??0)+1)
    return result
  },[query.data])

  return <div className="mt-3 flex flex-wrap items-center gap-1.5">
    {REACTIONS.map(emoji=>{
      const mine=query.data?.some(item=>item.user_id===currentUserId&&item.emoji===emoji)
      const count=counts.get(emoji)??0
      return <button key={emoji} type="button" onClick={()=>void toggle(emoji)} className={`rounded-full border px-2 py-1 text-xs transition ${mine?'border-indigo-500 bg-indigo-500/10':'border-[var(--line)] hover:bg-black/5 dark:hover:bg-white/5'}`} aria-label={`React ${emoji}`}><span>{emoji}</span>{count>0&&<span className="ml-1 muted">{count}</span>}</button>
    })}
  </div>
}

function MentionBody({body,members}:{body:string;members:WorkspaceMember[]}) {
  const byId=useMemo(()=>new Map(members.map(member=>[member.user_id,member.name])),[members])
  const parts=body.split(/(@\[[0-9a-fA-F-]{36}\])/g)
  return <p className="whitespace-pre-wrap text-sm leading-6">{parts.map((part,index)=>{
    const match=part.match(/^@\[([0-9a-fA-F-]{36})\]$/)
    if(!match)return <span key={index}>{part}</span>
    return <span key={index} className="rounded bg-indigo-500/10 px-1 py-0.5 font-medium text-indigo-700 dark:text-indigo-300">@{byId.get(match[1])??'member'}</span>
  })}</p>
}

export function CommentThread({task,token}:{task:Task;token:string}) {
  const {user}=useAuth()
  const [body,setBody]=useState('')
  const [mentionId,setMentionId]=useState('')
  const [editingId,setEditingId]=useState<string|null>(null)
  const [editBody,setEditBody]=useState('')
  const [confirmDelete,setConfirmDelete]=useState<string|null>(null)
  const comments=useQuery({queryKey:['comments',task.id],queryFn:()=>request<Comment[]>(`/api/v1/tasks/${task.id}/comments`,{},token)})
  const members=useQuery({queryKey:['members',task.workspace_id],queryFn:()=>request<WorkspaceMember[]>(`/api/v1/workspaces/${task.workspace_id}/members`,{},token)})

  async function addComment(e:FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const value=body.trim()
    if(!value)return
    await request<Comment>(`/api/v1/tasks/${task.id}/comments`,{method:'POST',body:JSON.stringify({body:value})},token)
    setBody('')
    setMentionId('')
    await comments.refetch()
  }

  async function saveEdit(commentId:string) {
    const value=editBody.trim()
    if(!value)return
    await request<Comment>(`/api/v1/tasks/${task.id}/comments/${commentId}`,{method:'PATCH',body:JSON.stringify({body:value})},token)
    setEditingId(null)
    setEditBody('')
    await comments.refetch()
  }

  async function remove(commentId:string) {
    await request<void>(`/api/v1/tasks/${task.id}/comments/${commentId}`,{method:'DELETE'},token)
    setConfirmDelete(null)
    await comments.refetch()
  }

  function addMention(id:string) {
    setMentionId(id)
    if(!id)return
    setBody(current=>`${current}${current&& !current.endsWith(' ')?' ':''}@[${id}] `)
  }

  return <section className="mt-10 border-t border-[var(--line)] pt-6">
    <h2 className="flex items-center gap-2 font-semibold"><MessageSquare size={18}/>Discussion</h2>
    <form onSubmit={addComment} className="mt-4">
      <textarea value={body} onChange={e=>setBody(e.target.value)} required rows={3} placeholder="Write a comment…" className="w-full rounded-2xl border border-[var(--line)] bg-transparent p-3 outline-none focus:border-indigo-500"/>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <label className="flex min-w-0 items-center gap-2 text-xs muted"><span>Mention</span><select value={mentionId} onChange={e=>addMention(e.target.value)} className="max-w-56 rounded-lg border border-[var(--line)] bg-[var(--panel)] px-2 py-1.5 text-xs text-[var(--fg)]"><option value="">Choose member…</option>{members.data?.map(member=><option key={member.user_id} value={member.user_id}>{member.name}</option>)}</select></label>
        <button className="rounded-xl border border-[var(--line)] px-4 py-2 text-sm font-semibold">Comment</button>
      </div>
    </form>
    <div className="mt-5 space-y-3">
      {comments.data?.map(comment=>{
        const own=comment.author_id===user?.id
        const editing=editingId===comment.id
        return <article key={comment.id} className="rounded-2xl bg-black/[.035] p-4 dark:bg-white/[.035]">
          <div className="mb-2 flex items-start justify-between gap-3">
            <div><span className="text-xs font-medium muted">{members.data?.find(member=>member.user_id===comment.author_id)?.name??comment.author_id.slice(0,8)}</span>{comment.edited_at&&<span className="ml-2 text-[11px] muted">edited</span>}</div>
            <div className="flex items-center gap-1">
              <time className="mr-1 text-xs muted">{new Date(comment.created_at).toLocaleString()}</time>
              {own&&<button type="button" onClick={()=>{setEditingId(comment.id);setEditBody(comment.body)}} className="rounded-lg p-1.5 hover:bg-black/5 dark:hover:bg-white/10" aria-label="Edit comment"><Pencil size={14}/></button>}
              {own&&(confirmDelete===comment.id?<div className="flex items-center gap-1"><button type="button" onClick={()=>void remove(comment.id)} className="rounded-lg bg-red-600 px-2 py-1 text-[11px] font-medium text-white">Delete</button><button type="button" onClick={()=>setConfirmDelete(null)} className="rounded-lg p-1.5" aria-label="Cancel delete"><X size={14}/></button></div>:<button type="button" onClick={()=>setConfirmDelete(comment.id)} className="rounded-lg p-1.5 text-red-600 hover:bg-red-500/10" aria-label="Delete comment"><Trash2 size={14}/></button>)}
            </div>
          </div>
          {editing?<div><textarea value={editBody} onChange={e=>setEditBody(e.target.value)} rows={3} className="w-full rounded-xl border border-[var(--line)] bg-transparent p-3 text-sm outline-none"/><div className="mt-2 flex justify-end gap-2"><button type="button" onClick={()=>setEditingId(null)} className="rounded-lg px-3 py-1.5 text-xs">Cancel</button><button type="button" onClick={()=>void saveEdit(comment.id)} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white">Save</button></div></div>:<MentionBody body={comment.body} members={members.data??[]}/>}
          <ReactionBar taskId={task.id} commentId={comment.id} token={token} currentUserId={user?.id}/>
          <div className="mt-3"><AttachmentsPanel entityType="comment" entityId={comment.id} token={token} compact/></div>
        </article>
      })}
      {comments.isLoading&&<p className="text-sm muted">Loading comments…</p>}
      {comments.data?.length===0&&<p className="text-sm muted">No comments yet.</p>}
    </div>
  </section>
}
