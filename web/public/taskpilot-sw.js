self.addEventListener('push', event => {
  let payload = {}
  try {
    payload = event.data ? event.data.json() : {}
  } catch (_) {
    payload = { title: 'TaskPilot', body: event.data ? event.data.text() : '' }
  }
  const title = payload.title || 'TaskPilot'
  const options = {
    body: payload.body || '',
    data: payload.data || {},
    tag: payload.data?.notification_id || undefined,
    renotify: false,
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', event => {
  event.notification.close()
  const destination = event.notification.data?.url || '/app/notifications'
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windows => {
      for (const client of windows) {
        if ('focus' in client) {
          client.navigate(destination)
          return client.focus()
        }
      }
      if (clients.openWindow) return clients.openWindow(destination)
      return undefined
    })
  )
})
