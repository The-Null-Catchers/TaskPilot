'use client'

import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export function SafeMarkdown({source}:{source:string}) {
  return <ReactMarkdown
    remarkPlugins={[remarkGfm]}
    skipHtml
    components={{
      a:({node: _node,...props})=><a {...props} target="_blank" rel="noopener noreferrer" className="text-indigo-600 underline underline-offset-2"/>,
      h1:({node: _node,...props})=><h1 {...props} className="mb-3 mt-4 text-2xl font-semibold"/>,
      h2:({node: _node,...props})=><h2 {...props} className="mb-2 mt-4 text-xl font-semibold"/>,
      h3:({node: _node,...props})=><h3 {...props} className="mb-2 mt-3 text-lg font-semibold"/>,
      p:({node: _node,...props})=><p {...props} className="my-2"/>,
      ul:({node: _node,...props})=><ul {...props} className="my-2 list-disc pl-6"/>,
      ol:({node: _node,...props})=><ol {...props} className="my-2 list-decimal pl-6"/>,
      blockquote:({node: _node,...props})=><blockquote {...props} className="my-3 border-l-4 border-indigo-500/40 pl-4 muted"/>,
      code:({node: _node,...props})=><code {...props} className="rounded bg-black/5 px-1 py-0.5 font-mono text-[.92em] dark:bg-white/10"/>,
      table:({node: _node,...props})=><div className="my-3 overflow-x-auto"><table {...props} className="w-full border-collapse text-left"/></div>,
      th:({node: _node,...props})=><th {...props} className="border border-[var(--line)] bg-black/[.025] px-3 py-2 font-semibold dark:bg-white/[.035]"/>,
      td:({node: _node,...props})=><td {...props} className="border border-[var(--line)] px-3 py-2"/>,
    }}
  >{source || '*No description yet.*'}</ReactMarkdown>
}
