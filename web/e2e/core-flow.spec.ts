import { expect, test } from '@playwright/test'

test('registers, onboards, and creates a task on the real board', async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`

  await page.goto('/login?mode=register')

  await page.getByLabel('Name').fill('E2E User')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill('TaskPilot-E2E-2026!')
  await page.getByRole('button', { name: 'Create account' }).click()

  await expect(page).toHaveURL(/\/app\/onboarding/, { timeout: 15_000 })
  await expect(
    page.getByRole('heading', { name: 'Start with a workflow, not an empty screen.' }),
  ).toBeVisible()

  await page.getByRole('button', { name: /Create project and continue/ }).click()

  await expect(page).toHaveURL(/\/app(?:\?|$)/)
  await expect(page.getByRole('heading', { name: 'Board' })).toBeVisible()

  await page.getByRole('button', { name: /Add task to/ }).first().click()
  await expect(page.getByRole('heading', { name: 'Create task' })).toBeVisible()

  const title = `Browser smoke ${Date.now()}`
  await page.getByPlaceholder('What needs to be done?').fill(title)
  await page.getByRole('button', { name: 'Create', exact: true }).click()

  await expect(page.getByText(title, { exact: true })).toBeVisible()

  const createProject = page.getByRole('button', { name: 'Create project' })
  await createProject.click()
  const dialog = page.getByRole('dialog', { name: 'New project' })
  await expect(dialog).toBeVisible()

  await expect(page.getByRole('button', { name: 'Close new project dialog' })).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(dialog.getByRole('button', { name: 'Create project' })).toBeFocused()

  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(createProject).toBeFocused()
})
