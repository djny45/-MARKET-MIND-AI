import { expect, test } from '@playwright/test'

const ownerPassword = 'e2e-only-test-password-2026'
const apiBase = 'http://127.0.0.1:8000'

async function signIn(page: import('@playwright/test').Page) {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Owner sign in' })).toBeVisible()
  await page.getByLabel('Owner password').fill(ownerPassword)
  await page.getByRole('button', { name: 'Sign in securely' }).click()
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
}

test('rejects an incorrect owner password', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Owner password').fill('incorrect-e2e-password')
  await page.getByRole('button', { name: 'Sign in securely' }).click()
  await expect(page.getByRole('alert')).toHaveText('Invalid credentials')
  await expect(page.getByRole('heading', { name: 'Owner sign in' })).toBeVisible()
})

test('restores the authenticated session after a browser reload', async ({ page }) => {
  await signIn(page)
  await page.reload()
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
})

test('rejects a state-changing request without its CSRF header', async ({ page }) => {
  await signIn(page)
  const result = await page.evaluate(async (url) => {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'include',
    })
    return { status: response.status, body: await response.json() }
  }, `${apiBase}/api/auth/logout`)

  expect(result.status).toBe(403)
  expect(result.body.detail).toBe('CSRF validation failed')

  const session = await page.evaluate(async (url) => {
    const response = await fetch(url, { credentials: 'include' })
    return response.status
  }, `${apiBase}/api/auth/session`)
  expect(session).toBe(200)
})

test('logout revokes the session and returns to the sign-in screen', async ({ page }) => {
  await signIn(page)
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('heading', { name: 'Owner sign in' })).toBeVisible()

  const sessionStatus = await page.evaluate(async (url) => {
    const response = await fetch(url, { credentials: 'include' })
    return response.status
  }, `${apiBase}/api/auth/session`)
  expect(sessionStatus).toBe(401)
})
