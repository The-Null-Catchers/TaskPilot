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
export type Label = { id:string; workspace_id:string; name:string; color:string }
export type TaskCollaborationState = { blocked:boolean; blocking_task_ids:string[]; watching:boolean; watcher_count:number }
export type TaskDependency = { id:string; blocker_task_id:string; blocked_task_id:string; created_by_id:string; created_at:string }
export type TaskDependencies = { blocked_by:TaskDependency[]; blocks:TaskDependency[] }
export type CommentReaction = { id:string; comment_id:string; user_id:string; emoji:string; created_at:string }
export type ActivityItem = { id:string; actor_id:string; action:string; summary:string; created_at:string }
export type DuplicateTaskResult = { task:Task; copied_subtasks:number; copied_checklists:number }
export type Board = { project:Project; columns:Column[]; tasks:Task[] }
export type Attachment = { id:string; workspace_id:string; uploader_id:string; task_id:string|null; comment_id:string|null; project_id:string|null; original_name:string; safe_name:string; mime_type:string; size_bytes:number; sha256:string; has_thumbnail:boolean; created_at:string }
export type AttachmentUrl = { url:string; expires_in:number }
export type StorageUsage = { workspace_id:string; used_bytes:number; quota_bytes:number; remaining_bytes:number }

export type TaskPage = { items:Task[]; total:number; limit:number; offset:number }
export type SavedView = { id:string; workspace_id:string; project_id:string|null; name:string; filters:Record<string,unknown>; sort_by:'due_date'|'priority'|'created_at'|'updated_at'; sort_direction:'asc'|'desc'; display_mode:'list'|'board'|'calendar'; created_at:string; updated_at:string }
export type Favorite = { id:string; workspace_id:string; entity_type:'project'|'board'|'saved_view'; entity_id:string; created_at:string }
export type RecentItem = { id:string; workspace_id:string; entity_type:'task'|'project'|'board'; entity_id:string; viewed_at:string }
export type TimeEntry = { id:string; task_id:string; user_id:string; started_at:string; ended_at:string|null; duration_seconds:number|null; note:string; created_at:string }
export type TimeSummary = { entries:TimeEntry[]; total_seconds:number; running_entry:TimeEntry|null }
export type CustomField = { id:string; workspace_id:string; name:string; field_type:'text'|'number'|'dropdown'|'date'|'checkbox'|'user'|'url'; options:string[]; required:boolean; position:number; created_at:string; updated_at:string }
export type TaskCustomFieldValue = { field:CustomField; value:unknown; updated_at:string|null }
export type CalendarItem = { id:string; kind:'task'|'project'; title:string; starts_at:string; workspace_id:string; project_id:string; task_id:string|null; identifier:string|null; priority:string|null; status:string|null }
export type TimelineTask = { id:string; identifier:string; title:string; status:string; priority:string; start_at:string; due_at:string|null; blocked_by:string[] }
export type Timeline = { project_id:string; tasks:TimelineTask[] }
export type Notification = { id:string; kind:string; title:string; body:string; entity_type:string|null; entity_id:string|null; read_at:string|null; created_at:string }
export type SearchResults = {
  workspaces:{id:string;name:string;slug:string}[]
  projects:{id:string;workspace_id:string;name:string;key:string}[]
  tasks:{id:string;workspace_id:string;project_id:string;identifier:string;title:string;priority:string;status:string}[]
  comments:{id:string;task_id:string;project_id:string;workspace_id:string;task_identifier:string;body:string}[]
  labels:{id:string;workspace_id:string;name:string;color:string}[]
}

export class ApiError extends Error {
  constructor(public status:number, message:string) { super(message) }
}

export async function request<T>(path:string, init:RequestInit = {}, token?:string|null):Promise<T> {
  const headers = new Headers(init.headers)
  const isFormData = typeof FormData !== 'undefined' && init.body instanceof FormData
  if (!headers.has('Content-Type') && init.body && !isFormData) headers.set('Content-Type','application/json')
  if (token) headers.set('Authorization',`Bearer ${token}`)
  const response = await fetch(`${API_URL}${path}`, { ...init, headers, credentials:'include', cache:'no-store' })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new ApiError(response.status, data.detail ?? data.error?.message ?? `Request failed (${response.status})`)
  }
  if (response.status === 204) return undefined as T
  return response.json()
}
