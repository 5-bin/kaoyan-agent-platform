import { test, expect, type Page } from '@playwright/test'

async function mockAuthConfig(page: Page, registrationEnabled = true) {
  await page.route('http://127.0.0.1:4173/api/**', route =>
    route.fulfill({ json: { code: 0, message: 'ok', data: { registrationEnabled } } }))
}

test('login form stays usable with decorative layers and no horizontal overflow', async ({ page }) => {
  await mockAuthConfig(page)
  await page.goto('/login')
  await expect(page.getByPlaceholder('用户名')).toBeVisible()
  await expect(page.getByPlaceholder('密码')).toBeVisible()
  await expect(page.getByRole('button', { name: '登 录', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: '立即注册' })).toBeVisible()
  await expect(page.locator('canvas.pixel-field')).toHaveAttribute('aria-hidden', 'true')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)

  // Decoration never intercepts input: the field is directly clickable and typable.
  await page.getByPlaceholder('用户名').click()
  await page.keyboard.type('student')
  await expect(page.getByPlaceholder('用户名')).toHaveValue('student')
})

test('typewriter is hidden from assistive tech while the full phrases stay readable', async ({ page }) => {
  await mockAuthConfig(page)
  await page.goto('/login')
  const typer = page.locator('.typer')
  await expect(typer.locator('[aria-hidden="true"]')).toHaveCount(1)
  await expect(typer.locator('.sr-only')).toHaveText('来源可查的课程习题、错题自动归集、实时解析、按科目和难度抽题')
  // The visible line actually types over time.
  await expect(typer.locator('[aria-hidden="true"]')).not.toHaveText('', { timeout: 3000 })
})

test('closed registration keeps the explanation instead of the register link', async ({ page }) => {
  await mockAuthConfig(page, false)
  await page.goto('/login')
  await expect(page.getByText('当前暂不开放注册，已有账号可正常登录。')).toBeVisible()
  await expect(page.getByRole('link', { name: '立即注册' })).toHaveCount(0)
})

test('register page shares the layout and keeps exactly its own three fields when open', async ({ page }) => {
  await mockAuthConfig(page, true)
  await page.goto('/register')
  await expect(page.getByText('注册后自动登录', { exact: true })).toBeVisible()
  await expect(page.locator('canvas.pixel-field')).toHaveAttribute('aria-hidden', 'true')
  await expect(page.locator('input')).toHaveCount(3)
  const button = page.getByRole('button', { name: '注 册', exact: true })
  const panel = await page.locator('.panel').boundingBox()
  const box = await button.boundingBox()
  expect(box!.width).toBeGreaterThan(panel!.width * 0.7)
  await expect(page.getByRole('link', { name: '直接登录' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('closed registration renders no form fields on the register page', async ({ page }) => {
  await mockAuthConfig(page, false)
  await page.goto('/register')
  await expect(page.getByText('当前暂不开放注册', { exact: true })).toBeVisible()
  await expect(page.locator('input')).toHaveCount(0)
  await expect(page.getByRole('link', { name: '直接登录' })).toBeVisible()
})

test.describe('reduced motion', () => {
  test('shows full static text and runs no animations', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await mockAuthConfig(page)
    await page.goto('/login')
    await expect(page.locator('.typer [aria-hidden="true"]')).toHaveText('来源可查的课程习题 · 错题自动归集 · 实时解析 · 按科目和难度抽题')
    await expect(page.locator('canvas.pixel-field')).toHaveAttribute('data-running', 'false')
    await expect(page.locator('.reveal').first()).toHaveCSS('opacity', '1')
    const running = await page.evaluate(() => document.getAnimations().filter(a => a.playState === 'running').length)
    expect(running).toBe(0)
  })
})
