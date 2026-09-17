export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export type User = { id:string; email:string; name:string; is_admin:boolean }
export type Workspace = { id:string; name:string; slug:string; owner_id:string; created_at:string }
export type WorkspaceMember = { user_id:string; email:string; name:string; role:'owner'|'admin'|'member'|'guest'; created_at:string }
export type Project = { id:string; workspace_id:string; owner_id:string; name:string; key:string; description:string; status:string; due_date:string|null; created_at:string }
export type Column = { id:string; project_id:string; name:string; position:number }
export type Task = { id:string; workspace_id:string; project_id:string; column_id:string; reporter_id:string; identifier:string; title:string; description:string; priority:'urgent'|'high'|'medium'|'low'|'none'; status:string; position:number; due_date:string|null; version:number; created_at:string; updated_at:string }
export type Comment = { id:string; task_id:string; author_id:string; body:string; edited_at:string|null; created_at:string }
export type Subtask = { id:string; task_id:string; title:string; status:'open'|'done'; assignee_id:string|null; due_date:string|null; position:number; version:number; created_at:string; updated_at:string }
export type Checklist = { id:string; task_id:string; title:string; position:number; created_at:string }
export type ChecklistItem = { id:string; checklist_id:string; title:string; completed:boolean; assignee_id:string|null; position:number; version:number; created_at:string; updated_at:string }
export type UserSummary = { id:string; email:string; name:string }
export type Board = { project:Project; columns:Column[]; tasks:Task[] }

export class ApiError extends Error {
  constructor(public status:number, message:string) { super(message) }
}

export async function request<T>(path:string, init:RequestInit = {}, token?:string|null):Promise<T> {
  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && init.body) headers.set('Content-Type','application/json')
  if (token) headers.set('Authorization',`Bearer ${token}`)
  const response = await fetch(`${API_URL}${path}`, { ...init, headers, credentials:'include', cache:'no-store' })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new ApiError(response.status, data.detail ?? data.error?.message ?? `Request failed (${response.status})`)
  }
  if (response.status === 204) return undefined as T
  return response.json()
}
