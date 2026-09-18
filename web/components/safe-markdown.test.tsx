import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { SafeMarkdown } from './safe-markdown'

describe('SafeMarkdown', () => {
  it('ignores raw HTML instead of rendering executable markup', () => {
    const lt = '<'
    const source = '# Safe\\n\\n' + lt + 'script>alert("xss")' + lt + '/script>\\n' + lt + 'img src=x onerror=alert(1)>\\n\\n**content**'
    const html = renderToStaticMarkup(<SafeMarkdown source={source} />)

    expect(html).toContain('Safe')
    expect(html).toContain('<strong>content</strong>')
    expect(html).not.toContain('<script')
    expect(html).not.toContain('<img')
    expect(html).not.toContain('onerror')
  })

  it('does not preserve javascript URLs', () => {
    const html = renderToStaticMarkup(
      <SafeMarkdown source={'[unsafe](javascript:alert(1))'} />,
    )

    expect(html).not.toContain('javascript:')
  })

  it('hardens rendered external links', () => {
    const html = renderToStaticMarkup(
      <SafeMarkdown source={'[TaskPilot](https://example.com/task)'} />,
    )

    expect(html).toContain('href="https://example.com/task"')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it('supports GitHub-flavored Markdown tables', () => {
    const html = renderToStaticMarkup(
      <SafeMarkdown source={'| Item | State |\n| --- | --- |\n| API | Done |'} />,
    )

    expect(html).toContain('<table')
    expect(html).toContain('<th')
    expect(html).toContain('<td')
  })
})
