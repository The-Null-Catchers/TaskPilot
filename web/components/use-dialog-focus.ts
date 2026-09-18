'use client'

import { RefObject, useEffect, useRef } from 'react'

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function useDialogFocus<T extends HTMLElement>(
  open: boolean,
  onClose: () => void,
): RefObject<T | null> {
  const ref = useRef<T>(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    if (!open || !ref.current) return

    const dialog = ref.current
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousId = previous?.id || null
    const previousAriaLabel = previous?.getAttribute('aria-label') || null
    const previousTagName = previous?.tagName.toLowerCase() || null
    const focusables = () =>
      Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        element => !element.hasAttribute('hidden') && element.getAttribute('aria-hidden') !== 'true',
      )

    const initial = focusables()[0] ?? dialog
    initial.focus()

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab') return

      const items = focusables()
      if (!items.length) {
        event.preventDefault()
        dialog.focus()
        return
      }

      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    dialog.addEventListener('keydown', handleKeyDown)
    return () => {
      dialog.removeEventListener('keydown', handleKeyDown)
      requestAnimationFrame(() => {
        if (previous && document.contains(previous)) {
          previous.focus()
          return
        }

        if (previousId) {
          const replacement = document.getElementById(previousId)
          if (replacement instanceof HTMLElement) {
            replacement.focus()
            return
          }
        }

        if (previousAriaLabel && previousTagName) {
          const replacement = Array.from(
            document.querySelectorAll<HTMLElement>(previousTagName),
          ).find(element => element.getAttribute('aria-label') === previousAriaLabel)
          replacement?.focus()
        }
      })
    }
  }, [open])

  return ref
}
