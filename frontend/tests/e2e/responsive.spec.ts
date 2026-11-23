import { test, expect } from '@playwright/test'

test('terminal renders without horizontal overflow at each viewport', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Help' })).toBeVisible()
  await expect(page.locator('.side-tabs button').first()).toBeVisible()

  const fits = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth + 1,
  )
  expect(fits, 'page overflows the viewport horizontally').toBe(true)
})

test('Help dialog opens and closes in a real browser', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Help' }).click()
  const dialog = page.getByRole('dialog', { name: /HELP/ })
  await expect(dialog).toBeVisible()
  await expect(dialog).toHaveAttribute('aria-modal', 'true')
  await dialog.getByRole('button', { name: /Close help/ }).click()
  await expect(dialog).toBeHidden()
})

test('screener tab opens a real stored-data panel', async ({ page }) => {
  await page.goto('/')
  // Backend is absent in the static server; the panel must still show an
  // explicit error/empty state rather than fabricated market data.
  await page.getByRole('button', { name: 'SCREENER' }).click()
  await expect(page.locator('section[aria-label="Research observation screener"]').first()).toBeVisible()
  await expect(page.getByText(/NOT LIVE MARKET DATA/).first()).toBeVisible()
})
