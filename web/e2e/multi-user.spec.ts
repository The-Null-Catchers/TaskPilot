import { expect, test, type APIRequestContext, type APIResponse } from '@playwright/test'

const API = 'http://127.0.0.1:8000/api/v1'
const PASSWORD = 'TaskPilot-E2E-2026!'

type Auth = {
  access_token: string
  user: { id: string; email: string; name: string }
}

async function register(api: APIRequestContext, email: string, name: string): Promise<Auth> {
  const response = await api.post(`${API}/auth/register`, {
    data: { email, password: PASSWORD, name },
  })
  expect(response.status(), await response.text()).toBe(201)
  return response.json()
}

function authHeaders(auth: Auth) {
  return { Authorization: `Bearer ${auth.access_token}` }
}

async function expectStatus(response: APIResponse, status: number) {
  expect(response.status(), await response.text()).toBe(status)
  return response
}

test.describe.serial('multi-user collaboration', () => {
  test.setTimeout(120_000)

  test('covers invitations, permissions, collaboration, realtime, archive, and saved views', async ({
    page,
    request,
  }, testInfo) => {
    const run = process.env.GITHUB_RUN_ID
      ? `${process.env.GITHUB_RUN_ID}-${testInfo.retry}`
      : `local-${testInfo.workerIndex}-${testInfo.retry}-${Date.now()}`
    const a = await register(request, `e2e-a-${run}@example.com`, 'E2E User A')
    const b = await register(request, `e2e-b-${run}@example.com`, 'E2E User B')
    const guest = await register(request, `e2e-guest-${run}@example.com`, 'E2E Guest')

    const workspaceResponse = await request.post(`${API}/workspaces`, {
      headers: authHeaders(a),
      data: { name: `E2E Workspace ${run}` },
    })
    await expectStatus(workspaceResponse, 201)
    const workspace = await workspaceResponse.json()

    const inviteBResponse = await request.post(
      `${API}/workspaces/${workspace.id}/invitations`,
      {
        headers: authHeaders(a),
        data: { email: b.user.email, role: 'member' },
      },
    )
    await expectStatus(inviteBResponse, 201)
    const inviteB = await inviteBResponse.json()

    const previewB = await request.get(`${API}/workspaces/invitations/${inviteB.token}`, {
      headers: authHeaders(b),
    })
    expect(previewB.status(), await previewB.text()).toBe(200)

    const acceptB = await request.post(
      `${API}/workspaces/invitations/${inviteB.token}/accept`,
      { headers: authHeaders(b) },
    )
    await expectStatus(acceptB, 200)

    const mobileLogin = await request.post(`${API}/auth/login`, {
      data: {
        email: b.user.email,
        password: PASSWORD,
        client: 'mobile',
        device_name: 'Playwright session device',
      },
    })
    await expectStatus(mobileLogin, 200)
    const mobileAuth = await mobileLogin.json()
    expect(mobileAuth.refresh_token).toBeTruthy()

    const sessionsResponse = await request.get(`${API}/auth/sessions`, {
      headers: authHeaders(b),
    })
    expect(sessionsResponse.status(), await sessionsResponse.text()).toBe(200)
    const sessions = await sessionsResponse.json()
    const mobileSession = sessions.find(
      (item: { device_name?: string; active: boolean }) =>
        item.device_name === 'Playwright session device' && item.active,
    )
    expect(mobileSession).toBeTruthy()

    await expectStatus(
      await request.delete(`${API}/auth/sessions/${mobileSession.id}`, {
        headers: authHeaders(b),
      }),
      204,
    )
    const revokedRefresh = await request.post(`${API}/auth/refresh`, {
      data: { refresh_token: mobileAuth.refresh_token, client: 'mobile' },
    })
    expect(revokedRefresh.status(), await revokedRefresh.text()).toBe(401)

    const memberCannotRename = await request.patch(`${API}/workspaces/${workspace.id}`, {
      headers: authHeaders(b),
      data: { name: 'Member should not rename' },
    })
    expect(memberCannotRename.status(), await memberCannotRename.text()).toBe(403)

    const projectResponse = await request.post(`${API}/projects`, {
      headers: authHeaders(a),
      data: {
        workspace_id: workspace.id,
        name: 'Realtime E2E Project',
        key: `E${String(Date.now()).slice(-8)}`,
        description: 'Deterministic multi-user browser E2E project',
      },
    })
    await expectStatus(projectResponse, 201)
    const project = await projectResponse.json()

    const boardResponse = await request.get(`${API}/projects/${project.id}/board`, {
      headers: authHeaders(a),
    })
    expect(boardResponse.status(), await boardResponse.text()).toBe(200)
    const board = await boardResponse.json()
    expect(board.columns.length).toBeGreaterThanOrEqual(2)

    const taskResponse = await request.post(`${API}/tasks`, {
      headers: authHeaders(a),
      data: {
        project_id: project.id,
        column_id: board.columns[0].id,
        title: 'Multi-user E2E task',
        description: 'Created for permission and realtime regression coverage',
        priority: 'high',
      },
    })
    await expectStatus(taskResponse, 201)
    let task = await taskResponse.json()

    const assignB = await request.post(`${API}/tasks/${task.id}/assignees`, {
      headers: authHeaders(a),
      data: { user_id: b.user.id },
    })
    await expectStatus(assignB, 200)

    const assignees = await request.get(`${API}/tasks/${task.id}/assignees`, {
      headers: authHeaders(b),
    })
    expect(assignees.status(), await assignees.text()).toBe(200)
    expect((await assignees.json()).map((item: { id: string }) => item.id)).toContain(b.user.id)

    const mention = await request.post(`${API}/tasks/${task.id}/comments`, {
      headers: authHeaders(a),
      data: { body: `@[${b.user.id}] please review this task` },
    })
    await expectStatus(mention, 201)

    const bNotifications = await request.get(`${API}/notifications`, {
      headers: authHeaders(b),
    })
    expect(bNotifications.status(), await bNotifications.text()).toBe(200)
    expect(await bNotifications.json()).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ kind: 'task.mention', entity_id: task.id }),
      ]),
    )

    await expectStatus(
      await request.post(`${API}/tasks/${task.id}/watch`, { headers: authHeaders(a) }),
      204,
    )
    const bComment = await request.post(`${API}/tasks/${task.id}/comments`, {
      headers: authHeaders(b),
      data: { body: 'Reviewed from User B.' },
    })
    await expectStatus(bComment, 201)

    const aNotifications = await request.get(`${API}/notifications`, {
      headers: authHeaders(a),
    })
    expect(aNotifications.status(), await aNotifications.text()).toBe(200)
    expect(await aNotifications.json()).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ kind: 'task.comment', entity_id: task.id }),
      ]),
    )

    // Establish a real browser-origin WebSocket and trigger a REST mutation from the browser.
    await page.goto('/login')
    const realtimeEvent = await page.evaluate(
      async ({ api, workspaceId, taskId, token, columnId, version }) => {
        return await new Promise<{ event: string; payload: { id?: string } }>((resolve, reject) => {
          const socket = new WebSocket(
            `ws://127.0.0.1:8000/api/v1/ws/workspaces/${workspaceId}`,
          )
          const timer = window.setTimeout(() => {
            socket.close()
            reject(new Error('Timed out waiting for task.moved realtime event'))
          }, 12_000)

          socket.onerror = () => {
            window.clearTimeout(timer)
            reject(new Error('WebSocket failed'))
          }

          socket.onmessage = (message) => {
            const event = JSON.parse(message.data)
            if (event.event === 'task.moved' && event.payload?.id === taskId) {
              window.clearTimeout(timer)
              socket.close()
              resolve(event)
            }
          }

          socket.onopen = () => {
            socket.send(JSON.stringify({ type: 'auth', token }))
            window.setTimeout(async () => {
              const response = await fetch(`${api}/tasks/${taskId}/move`, {
                method: 'POST',
                headers: {
                  Authorization: `Bearer ${token}`,
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                  column_id: columnId,
                  position: 1000,
                  version,
                }),
              })
              if (!response.ok) {
                window.clearTimeout(timer)
                socket.close()
                reject(new Error(`Move failed: ${response.status} ${await response.text()}`))
              }
            }, 350)
          }
        })
      },
      {
        api: API,
        workspaceId: workspace.id,
        taskId: task.id,
        token: b.access_token,
        columnId: board.columns[1].id,
        version: task.version,
      },
    )
    expect(realtimeEvent.event).toBe('task.moved')

    const taskAfterMoveResponse = await request.get(`${API}/tasks/${task.id}`, {
      headers: authHeaders(a),
    })
    expect(taskAfterMoveResponse.status(), await taskAfterMoveResponse.text()).toBe(200)
    task = await taskAfterMoveResponse.json()
    expect(task.column_id).toBe(board.columns[1].id)

    const stalePatch = await request.patch(`${API}/tasks/${task.id}`, {
      headers: authHeaders(b),
      data: { version: task.version - 1, title: 'Stale overwrite must fail' },
    })
    expect(stalePatch.status(), await stalePatch.text()).toBe(409)

    const doneResponse = await request.patch(`${API}/tasks/${task.id}`, {
      headers: authHeaders(b),
      data: { version: task.version, status: 'done' },
    })
    await expectStatus(doneResponse, 200)
    task = await doneResponse.json()
    expect(task.status).toBe('done')

    const archive = await request.post(`${API}/tasks/${task.id}/archive`, {
      headers: authHeaders(b),
    })
    await expectStatus(archive, 200)

    const archived = await request.get(
      `${API}/workspaces/${workspace.id}/archived-tasks`,
      { headers: authHeaders(b) },
    )
    expect(archived.status(), await archived.text()).toBe(200)
    expect((await archived.json()).map((item: { id: string }) => item.id)).toContain(task.id)

    const restore = await request.post(`${API}/tasks/${task.id}/restore`, {
      headers: authHeaders(b),
    })
    await expectStatus(restore, 200)
    const restoredTask = await restore.json()

    const savedView = await request.post(`${API}/saved-views`, {
      headers: authHeaders(b),
      data: {
        workspace_id: workspace.id,
        project_id: project.id,
        name: 'My high-priority work',
        filters: { priority: ['high'], assignee_id: b.user.id },
        sort_by: 'updated_at',
        sort_direction: 'desc',
        display_mode: 'list',
      },
    })
    await expectStatus(savedView, 201)

    const views = await request.get(`${API}/saved-views?workspace_id=${workspace.id}`, {
      headers: authHeaders(b),
    })
    expect(views.status(), await views.text()).toBe(200)
    expect(await views.json()).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ name: 'My high-priority work', project_id: project.id }),
      ]),
    )

    const apiTokenResponse = await request.post(`${API}/integrations/tokens`, {
      headers: authHeaders(a),
      data: { name: 'Playwright read-only token', scopes: ['read'] },
    })
    await expectStatus(apiTokenResponse, 201)
    const apiToken = await apiTokenResponse.json()
    expect(apiToken.token).toBeTruthy()

    const tokenHeaders = { Authorization: `Bearer ${apiToken.token}` }
    const tokenRead = await request.get(`${API}/workspaces`, { headers: tokenHeaders })
    expect(tokenRead.status(), await tokenRead.text()).toBe(200)
    const tokenWrite = await request.post(`${API}/workspaces`, {
      headers: tokenHeaders,
      data: { name: 'Read-only token must not create this' },
    })
    expect(tokenWrite.status(), await tokenWrite.text()).toBe(403)

    await expectStatus(
      await request.delete(`${API}/integrations/tokens/${apiToken.id}`, {
        headers: authHeaders(a),
      }),
      204,
    )
    const revokedTokenRead = await request.get(`${API}/workspaces`, { headers: tokenHeaders })
    expect(revokedTokenRead.status(), await revokedTokenRead.text()).toBe(401)

    const webhookResponse = await request.post(`${API}/workspaces/${workspace.id}/webhooks`, {
      headers: authHeaders(a),
      data: {
        name: 'Playwright webhook',
        url: 'https://example.com/taskpilot-e2e',
        events: ['task.updated'],
      },
    })
    await expectStatus(webhookResponse, 201)
    const webhook = await webhookResponse.json()
    expect(webhook.secret).toBeTruthy()

    const memberWebhook = await request.post(`${API}/workspaces/${workspace.id}/webhooks`, {
      headers: authHeaders(b),
      data: {
        name: 'Forbidden member webhook',
        url: 'https://example.com/taskpilot-member-e2e',
        events: ['*'],
      },
    })
    expect(memberWebhook.status(), await memberWebhook.text()).toBe(403)

    const rotatedWebhookSecret = await request.post(
      `${API}/workspaces/${workspace.id}/webhooks/${webhook.id}/rotate-secret`,
      { headers: authHeaders(a) },
    )
    await expectStatus(rotatedWebhookSecret, 200)
    expect((await rotatedWebhookSecret.json()).secret).toBeTruthy()

    await expectStatus(
      await request.patch(`${API}/workspaces/${workspace.id}/webhooks/${webhook.id}`, {
        headers: authHeaders(a),
        data: { active: false, name: 'Playwright webhook disabled' },
      }),
      200,
    )
    await expectStatus(
      await request.delete(`${API}/workspaces/${workspace.id}/webhooks/${webhook.id}`, {
        headers: authHeaders(a),
      }),
      204,
    )

    const inviteGuestResponse = await request.post(
      `${API}/workspaces/${workspace.id}/invitations`,
      {
        headers: authHeaders(a),
        data: { email: guest.user.email, role: 'guest' },
      },
    )
    await expectStatus(inviteGuestResponse, 201)
    const inviteGuest = await inviteGuestResponse.json()
    await expectStatus(
      await request.post(`${API}/workspaces/invitations/${inviteGuest.token}/accept`, {
        headers: authHeaders(guest),
      }),
      200,
    )

    const guestProjects = await request.get(`${API}/projects?workspace_id=${workspace.id}`, {
      headers: authHeaders(guest),
    })
    expect(guestProjects.status(), await guestProjects.text()).toBe(200)
    expect(await guestProjects.json()).toEqual([])

    const isolatedBoard = await request.get(`${API}/projects/${project.id}/board`, {
      headers: authHeaders(guest),
    })
    expect(isolatedBoard.status(), await isolatedBoard.text()).toBe(403)

    const addGuest = await request.post(`${API}/projects/${project.id}/members`, {
      headers: authHeaders(a),
      data: { user_id: guest.user.id, role: 'guest' },
    })
    await expectStatus(addGuest, 200)

    const guestBoard = await request.get(`${API}/projects/${project.id}/board`, {
      headers: authHeaders(guest),
    })
    expect(guestBoard.status(), await guestBoard.text()).toBe(200)

    const guestCannotMove = await request.post(`${API}/tasks/${task.id}/move`, {
      headers: authHeaders(guest),
      data: {
        column_id: board.columns[0].id,
        position: 1000,
        version: restoredTask.version,
      },
    })
    expect(guestCannotMove.status(), await guestCannotMove.text()).toBe(403)

    const guestCannotCreateProject = await request.post(`${API}/projects`, {
      headers: authHeaders(guest),
      data: {
        workspace_id: workspace.id,
        name: 'Forbidden Guest Project',
        key: 'NOPE',
        description: '',
      },
    })
    expect(guestCannotCreateProject.status(), await guestCannotCreateProject.text()).toBe(403)
  })
})
