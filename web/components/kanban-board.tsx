'use client'

import { DndContext, DragEndEvent, KeyboardSensor, PointerSensor, useDroppable, useSensor, useSensors } from '@dnd-kit/core'
import { SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { ChevronLeft, ChevronRight, GripVertical, Pencil, Plus, Trash2, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { TaskDrawer } from '@/components/task-drawer'
import { useDialogFocus } from '@/components/use-dialog-focus'
import { Board, Column, request, Task } from '@/lib/api'

type TemplateCatalog={task_templates:{key:string;name:string}[];project_templates:{key:string;name:string;description:string}[]}
type ColumnDialog={mode:'create'|'rename';column?:Column}

function Card({task,onOpen}:{task:Task;onOpen:()=>void}){
 const {attributes,listeners,setNodeRef,transform,isDragging}=useSortable({id:task.id,data:{task}})
 return <article ref={setNodeRef} style={{transform:CSS.Translate.toString(transform)}} {...attributes} className={`rounded-xl border border-[var(--line)] bg-[var(--panel)] p-4 shadow-sm ${isDragging?'opacity-60':''}`}>
   <div className="mb-4 flex items-center justify-between">
     <button {...listeners} onClick={e=>e.stopPropagation()} className="-ml-2 rounded-lg p-1.5 muted hover:bg-black/5 dark:hover:bg-white/5" aria-label={`Drag ${task.identifier}`}><GripVertical size={16}/></button>
     <span className="text-xs font-medium muted">{task.identifier}</span>
     <span className={`h-2 w-2 rounded-full ${task.priority==='urgent'?'bg-red-500':task.priority==='high'?'bg-orange-500':task.priority==='medium'?'bg-amber-400':'bg-slate-300'}`} aria-label={`Priority ${task.priority}`}/>
   </div>
   <button onClick={onOpen} className="w-full text-left"><h3 className="text-sm font-medium leading-5">{task.title}</h3>{task.due_date&&<p className="mt-3 text-xs muted">Due {new Date(task.due_date).toLocaleDateString()}</p>}</button>
 </article>
}

function ColumnBox({
 id,name,tasks,index,total,onAdd,onOpen,onRename,onDelete,onMove,
}:{id:string;name:string;tasks:Task[];index:number;total:number;onAdd:()=>void;onOpen:(task:Task)=>void;onRename:()=>void;onDelete:()=>void;onMove:(direction:-1|1)=>void}){
 const {setNodeRef,isOver}=useDroppable({id})
 return <section ref={setNodeRef} className={`min-h-[360px] w-[290px] shrink-0 rounded-2xl border border-[var(--line)] bg-black/[.025] p-3 dark:bg-white/[.025] ${isOver?'ring-2 ring-indigo-500/30':''}`}>
   <div className="mb-3 flex items-center justify-between gap-2 px-1">
     <div className="flex min-w-0 items-center gap-2"><h2 className="truncate text-sm font-semibold">{name}</h2><span className="rounded-full bg-black/5 px-2 py-0.5 text-xs muted dark:bg-white/5">{tasks.length}</span></div>
     <div className="flex items-center">
       <button disabled={index===0} onClick={()=>onMove(-1)} className="rounded-lg p-1 muted hover:bg-black/5 disabled:opacity-30 dark:hover:bg-white/5" aria-label={`Move ${name} left`}><ChevronLeft size={14}/></button>
       <button disabled={index===total-1} onClick={()=>onMove(1)} className="rounded-lg p-1 muted hover:bg-black/5 disabled:opacity-30 dark:hover:bg-white/5" aria-label={`Move ${name} right`}><ChevronRight size={14}/></button>
       <button onClick={onRename} className="rounded-lg p-1 muted hover:bg-black/5 dark:hover:bg-white/5" aria-label={`Rename ${name}`}><Pencil size={14}/></button>
       <button onClick={onDelete} className="rounded-lg p-1 text-red-600 hover:bg-red-500/10" aria-label={`Delete ${name}`}><Trash2 size={14}/></button>
       <button onClick={onAdd} className="rounded-lg p-1 hover:bg-black/5 dark:hover:bg-white/5" aria-label={`Add task to ${name}`}><Plus size={16}/></button>
     </div>
   </div>
   <SortableContext items={tasks.map(t=>t.id)} strategy={verticalListSortingStrategy}><div className="space-y-2">{tasks.map(t=><Card key={t.id} task={t} onOpen={()=>onOpen(t)}/>)}</div></SortableContext>
 </section>
}

export function KanbanBoard({initial,token,onChanged}:{initial:Board;token:string;onChanged:(b:Board)=>void}){
 const [creating,setCreating]=useState<string|null>(null)
 const [title,setTitle]=useState('')
 const [templateKey,setTemplateKey]=useState('')
 const [selected,setSelected]=useState<Task|null>(null)
 const [columnDialog,setColumnDialog]=useState<ColumnDialog|null>(null)
 const [columnName,setColumnName]=useState('')
 const [columnBusy,setColumnBusy]=useState(false)
 const [columnError,setColumnError]=useState('')
 const sensors=useSensors(useSensor(PointerSensor,{activationConstraint:{distance:6}}),useSensor(KeyboardSensor,{coordinateGetter:sortableKeyboardCoordinates}))
 const createTaskDialogRef=useDialogFocus<HTMLDivElement>(!!creating,()=>setCreating(null))
 const columnDialogRef=useDialogFocus<HTMLDivElement>(!!columnDialog,()=>setColumnDialog(null))
 const templates=useQuery({queryKey:['task-templates'],queryFn:()=>request<TemplateCatalog>('/api/v1/templates',{},token),enabled:!!creating})
 const byColumn=useMemo(()=>Object.fromEntries(initial.columns.map(c=>[c.id,initial.tasks.filter(t=>t.column_id===c.id).sort((a,b)=>a.position-b.position)])),[initial])

 async function add(columnId:string){
   if(!title.trim()&&!templateKey)return
   let task:Task
   if(templateKey){
     const created=await request<{id:string}>('/api/v1/templates/tasks/apply',{method:'POST',body:JSON.stringify({project_id:initial.project.id,column_id:columnId,template_key:templateKey,title:title.trim()||null})},token)
     task=await request<Task>(`/api/v1/tasks/${created.id}`,{},token)
   }else{
     task=await request<Task>('/api/v1/tasks',{method:'POST',body:JSON.stringify({project_id:initial.project.id,column_id:columnId,title:title.trim()})},token)
   }
   onChanged({...initial,tasks:[...initial.tasks,task]})
   setTitle('');setTemplateKey('');setCreating(null)
 }

 async function moved(e:DragEndEvent){
   const task=e.active.data.current?.task as Task|undefined
   if(!task||!e.over||String(e.over.id)===task.id)return
   const overId=String(e.over.id)
   const target=initial.tasks.find(t=>t.id===overId)
   const destination=initial.columns.find(c=>c.id===overId)?.id??target?.column_id
   if(!destination)return
   const destinationTasks=(byColumn[destination]??[]).filter(t=>t.id!==task.id)
   let position=(destinationTasks.at(-1)?.position??0)+1000
   if(target){
     const index=destinationTasks.findIndex(t=>t.id===target.id)
     const previous=index>0?destinationTasks[index-1]:undefined
     position=previous?((previous.position+target.position)/2):target.position-1000
   }
   const optimistic={...task,column_id:destination,position,version:task.version+1}
   onChanged({...initial,tasks:initial.tasks.map(t=>t.id===task.id?optimistic:t)})
   try{
     const updated=await request<Task>(`/api/v1/tasks/${task.id}/move`,{method:'POST',body:JSON.stringify({column_id:destination,position,version:task.version})},token)
     onChanged({...initial,tasks:initial.tasks.map(t=>t.id===task.id?updated:t)})
     if(selected?.id===updated.id)setSelected(updated)
   }catch{onChanged(initial)}
 }

 function updateTask(updated:Task){
   onChanged({...initial,tasks:initial.tasks.map(t=>t.id===updated.id?updated:t)})
   setSelected(updated)
 }

 function openCreateColumn(){setColumnError('');setColumnName('');setColumnDialog({mode:'create'})}
 function openRenameColumn(column:Column){setColumnError('');setColumnName(column.name);setColumnDialog({mode:'rename',column})}

 async function saveColumn(){
   const name=columnName.trim()
   if(!name||!columnDialog)return
   setColumnBusy(true);setColumnError('')
   try{
     if(columnDialog.mode==='create'){
       const created=await request<Column>(`/api/v1/projects/${initial.project.id}/columns`,{method:'POST',body:JSON.stringify({name})},token)
       onChanged({...initial,columns:[...initial.columns,created].sort((a,b)=>a.position-b.position)})
     }else if(columnDialog.column){
       const updated=await request<Column>(`/api/v1/projects/${initial.project.id}/columns/${columnDialog.column.id}`,{method:'PATCH',body:JSON.stringify({name})},token)
       onChanged({...initial,columns:initial.columns.map(column=>column.id===updated.id?updated:column)})
     }
     setColumnDialog(null);setColumnName('')
   }catch(err){setColumnError(err instanceof Error?err.message:'Could not save column.')}
   finally{setColumnBusy(false)}
 }

 async function reorderColumn(columnId:string,direction:-1|1){
   const index=initial.columns.findIndex(column=>column.id===columnId)
   const next=index+direction
   if(index<0||next<0||next>=initial.columns.length)return
   const optimistic=[...initial.columns]
   ;[optimistic[index],optimistic[next]]=[optimistic[next],optimistic[index]]
   const normalized=optimistic.map((column,position)=>({...column,position}))
   onChanged({...initial,columns:normalized})
   setColumnError('')
   try{
     const saved=await request<Column[]>(`/api/v1/projects/${initial.project.id}/columns/reorder`,{method:'PUT',body:JSON.stringify({column_ids:normalized.map(column=>column.id)})},token)
     onChanged({...initial,columns:saved})
   }catch(err){
     onChanged(initial)
     setColumnError(err instanceof Error?err.message:'Could not reorder columns.')
   }
 }

 async function deleteColumn(column:Column){
   const tasks=byColumn[column.id]??[]
   if(tasks.length){
     setColumnError(`Move the ${tasks.length} task${tasks.length===1?'':'s'} out of "${column.name}" before deleting it.`)
     return
   }
   if(initial.columns.length<=1){setColumnError('A board must keep at least one column.');return}
   if(!confirm(`Delete "${column.name}"? This cannot be undone.`))return
   setColumnError('')
   try{
     await request(`/api/v1/projects/${initial.project.id}/columns/${column.id}`,{method:'DELETE'},token)
     onChanged({...initial,columns:initial.columns.filter(item=>item.id!==column.id).map((item,position)=>({...item,position}))})
   }catch(err){setColumnError(err instanceof Error?err.message:'Could not delete column.')}
 }

 return <>
   {columnError&&<div role="alert" className="mb-3 flex items-start justify-between gap-3 rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-700 dark:text-red-300"><span>{columnError}</span><button onClick={()=>setColumnError('')} aria-label="Dismiss column error"><X size={15}/></button></div>}
   <DndContext sensors={sensors} onDragEnd={moved}>
     <div className="scrollbar flex gap-3 overflow-x-auto pb-4">
       {initial.columns.map((column,index)=><ColumnBox key={column.id} id={column.id} name={column.name} tasks={byColumn[column.id]??[]} index={index} total={initial.columns.length} onAdd={()=>setCreating(column.id)} onOpen={setSelected} onRename={()=>openRenameColumn(column)} onDelete={()=>void deleteColumn(column)} onMove={direction=>void reorderColumn(column.id,direction)}/>)}
       <button onClick={openCreateColumn} className="grid min-h-[120px] w-[220px] shrink-0 place-items-center rounded-2xl border border-dashed border-[var(--line)] bg-[var(--panel)] px-4 text-sm font-medium muted hover:border-indigo-500/40 hover:text-indigo-600"><span className="inline-flex items-center gap-2"><Plus size={17}/>Add column</span></button>
     </div>
   </DndContext>

   {creating&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/35 p-4" onMouseDown={()=>setCreating(null)}><div ref={createTaskDialogRef} role="dialog" aria-modal="true" aria-labelledby="create-task-title" tabIndex={-1} className="panel w-full max-w-md rounded-2xl p-5 shadow-soft" onMouseDown={e=>e.stopPropagation()}><h2 id="create-task-title" className="font-semibold">Create task</h2><label className="mt-4 block text-xs font-medium muted">Template<select value={templateKey} onChange={e=>setTemplateKey(e.target.value)} className="mt-1.5 w-full rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2.5 text-sm"><option value="">Blank task</option>{templates.data?.task_templates.map(item=><option key={item.key} value={item.key}>{item.name}</option>)}</select></label><label className="mt-3 block text-xs font-medium muted">Title {templateKey&&'(optional override)'}<input autoFocus value={title} onChange={e=>setTitle(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')void add(creating)}} placeholder={templateKey?'Use template default title':'What needs to be done?'} className="mt-1.5 w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-3 text-sm outline-none"/></label><p className="mt-3 text-xs muted">Templates add a structured Markdown description, labels, priority, and checklist automatically.</p><div className="mt-4 flex justify-end gap-2"><button onClick={()=>setCreating(null)} className="rounded-xl px-4 py-2 text-sm">Cancel</button><button onClick={()=>void add(creating)} disabled={!title.trim()&&!templateKey} className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Create</button></div></div></div>}

   {columnDialog&&<div className="fixed inset-0 z-50 grid place-items-center bg-black/35 p-4" onMouseDown={()=>setColumnDialog(null)}><div ref={columnDialogRef} role="dialog" aria-modal="true" aria-labelledby="column-dialog-title" tabIndex={-1} className="panel w-full max-w-md rounded-2xl p-5 shadow-soft" onMouseDown={e=>e.stopPropagation()}><div className="flex items-center justify-between"><h2 id="column-dialog-title" className="font-semibold">{columnDialog.mode==='create'?'Add board column':'Rename board column'}</h2><button onClick={()=>setColumnDialog(null)} className="rounded-lg p-1 muted" aria-label="Close"><X size={17}/></button></div><label className="mt-4 block text-xs font-medium muted">Column name<input autoFocus value={columnName} onChange={e=>setColumnName(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')void saveColumn()}} maxLength={80} className="mt-1.5 w-full rounded-xl border border-[var(--line)] bg-transparent px-3 py-3 text-sm outline-none"/></label>{columnError&&<p className="mt-3 text-sm text-red-600">{columnError}</p>}<div className="mt-4 flex justify-end gap-2"><button onClick={()=>setColumnDialog(null)} className="rounded-xl px-4 py-2 text-sm">Cancel</button><button onClick={()=>void saveColumn()} disabled={columnBusy||!columnName.trim()} className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{columnBusy?'Saving…':'Save'}</button></div></div></div>}

   {selected&&<TaskDrawer task={selected} token={token} onClose={()=>setSelected(null)} onUpdated={updateTask}/>}
 </>
}
