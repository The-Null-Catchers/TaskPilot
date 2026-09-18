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

test('uses real MinIO for browser attachment upload and download', async ({ page, request }, testInfo) => {
  test.setTimeout(90_000)
  const run = process.env.GITHUB_RUN_ID
    ? `${process.env.GITHUB_RUN_ID}-${testInfo.retry}`
    : `local-${Date.now()}`
  const owner = await register(request, `storage-owner-${run}@example.com`, 'Storage Owner')
  const outsider = await register(request, `storage-outsider-${run}@example.com`, 'Storage Outsider')

  const workspaceResponse = await request.post(`${API}/workspaces`, {
    headers: authHeaders(owner),
    data: { name: `Storage E2E ${run}` },
  })
  await expectStatus(workspaceResponse, 201)
  const workspace = await workspaceResponse.json()

  const projectResponse = await request.post(`${API}/projects`, {
    headers: authHeaders(owner),
    data: {
      workspace_id: workspace.id,
      name: 'Storage E2E Project',
      key: `S${String(Date.now()).slice(-8)}`,
      description: 'Real object-storage browser coverage',
    },
  })
  await expectStatus(projectResponse, 201)
  const project = await projectResponse.json()

  const boardResponse = await request.get(`${API}/projects/${project.id}/board`, {
    headers: authHeaders(owner),
  })
  await expectStatus(boardResponse, 200)
  const board = await boardResponse.json()

  const taskResponse = await request.post(`${API}/tasks`, {
    headers: authHeaders(owner),
    data: {
      project_id: project.id,
      column_id: board.columns[0].id,
      title: 'Attachment storage E2E',
      description: 'Upload and signed-download coverage',
      priority: 'medium',
    },
  })
  await expectStatus(taskResponse, 201)
  const task = await taskResponse.json()

  await page.goto('/login')
  await page.getByLabel('Email').fill(owner.user.email)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/app/, { timeout: 15_000 })

  await page.goto(`/app/tasks/${task.id}`)
  await expect(page.getByLabel('Task title')).toHaveValue('Attachment storage E2E')
  await page.getByRole('button', { name: 'Open attachments' }).click()

  const filename = `storage-${run}.txt`
  await page.locator('input[type="file"]').setInputFiles({
    name: filename,
    mimeType: 'text/plain',
    buffer: Buffer.from(`TaskPilot real MinIO E2E ${run}\n`),
  })
  await expect(page.getByText(filename, { exact: true })).toBeVisible({ timeout: 15_000 })

  const listResponse = await request.get(
    `${API}/attachments?entity_type=task&entity_id=${task.id}`,
    { headers: authHeaders(owner) },
  )
  await expectStatus(listResponse, 200)
  const attachment = (await listResponse.json()).find(
    (item: { safe_name: string }) => item.safe_name === filename,
  )
  expect(attachment).toBeTruthy()

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: `Download ${filename}` }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe(filename)
  expect(await download.path()).toBeTruthy()

  const denied = await request.get(`${API}/attachments/${attachment.id}/download`, {
    headers: authHeaders(outsider),
  })
  expect([403, 404]).toContain(denied.status())

  await page.getByRole('button', { name: `Delete ${filename}` }).click()
  await page.getByRole('button', { name: 'Confirm', exact: true }).click()
  await expect(page.getByText(filename, { exact: true })).toBeHidden()
})
