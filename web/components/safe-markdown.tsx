'use client'

import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export function SafeMarkdown({source}:{source:string}) {
  return <ReactMarkdown
    remarkPlugins={[remarkGfm]}
    skipHtml
    components={{
      a:({node,...props})=>{void node;return <a {...props} target="_blank" rel="noopener noreferrer" className="text-indigo-600 underline underline-offset-2"/>},
      h1:({node,...props})=>{void node;return <h1 {...props} className="mb-3 mt-4 text-2xl font-semibold"/>},
      h2:({node,...props})=>{void node;return <h2 {...props} className="mb-2 mt-4 text-xl font-semibold"/>},
      h3:({node,...props})=>{void node;return <h3 {...props} className="mb-2 mt-3 text-lg font-semibold"/>},
      p:({node,...props})=>{void node;return <p {...props} className="my-2"/>},
      ul:({node,...props})=>{void node;return <ul {...props} className="my-2 list-disc pl-6"/>},
      ol:({node,...props})=>{void node;return <ol {...props} className="my-2 list-decimal pl-6"/>},
      blockquote:({node,...props})=>{void node;return <blockquote {...props} className="my-3 border-l-4 border-indigo-500/40 pl-4 muted"/>},
      code:({node,...props})=>{void node;return <code {...props} className="rounded bg-black/5 px-1 py-0.5 font-mono text-[.92em] dark:bg-white/10"/>},
      table:({node,...props})=>{void node;return <div className="my-3 overflow-x-auto"><table {...props} className="w-full border-collapse text-left"/></div>},
      th:({node,...props})=>{void node;return <th {...props} className="border border-[var(--line)] bg-black/[.025] px-3 py-2 font-semibold dark:bg-white/[.035]"/>},
      td:({node,...props})=>{void node;return <td {...props} className="border border-[var(--line)] px-3 py-2"/>},
    }}
  >{source || '*No description yet.*'}</ReactMarkdown>
}
