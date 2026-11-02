// Real disposable MySQL/Java/Vue verification; only synthetic accounts and fresh contexts.
const { chromium, expect } = require('../kaoyan-frontend/node_modules/@playwright/test')
const path = require('node:path')

async function main() {
  const [base, artifacts] = process.argv.slice(2)
  const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
  try {
    for (const [name, viewport] of [['desktop', { width: 1280, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
      const context = await browser.newContext({ viewport })
      const login = await context.request.post(base + '/api/auth/login', { data: {
        username: 'school_lookup_smoke', password: 'synthetic-school-password'
      } })
      expect(login.ok()).toBe(true)
      const token = (await login.json()).data.accessToken
      const current = await context.request.get(base + '/api/users/me', { headers: { Authorization: 'Bearer ' + token } })
      const user = (await current.json()).data
      await context.addInitScript(({ token, user }) => {
        localStorage.setItem('token', token)
        localStorage.setItem('userInfo', JSON.stringify(user))
      }, { token, user })
      const page = await context.newPage()
      await page.goto(base + '/schools/11')
      await expect(page.getByRole('heading', { name: '四川大学', exact: true })).toBeVisible()
      await expect(page.locator('.el-loading-mask')).toHaveCount(0)
      await expect(page.locator('.el-table__body-wrapper tbody tr').first()).toBeVisible()
      await page.screenshot({ path: path.join(artifacts, `${name}-school-11.png`), fullPage: false })
      await page.goto(base + '/tasks')
      await expect(page.getByRole('region', { name: '库内院校信息' })).toBeVisible()
      await expect(page.getByRole('region', { name: '招生官网链接' })).toBeVisible()
      expect(await page.evaluate(() => Boolean(document.querySelector('.school-catalog')
        .compareDocumentPosition(document.querySelector('.admission-links')) & Node.DOCUMENT_POSITION_FOLLOWING))).toBe(true)
      await page.reload()
      await expect(page.getByRole('region', { name: '库内院校信息' })).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await page.screenshot({ path: path.join(artifacts, `${name}-catalog-chat.png`), fullPage: false })
      await context.close()
    }
  } finally {
    await browser.close()
  }
}

main().catch(error => { console.error(error.message); process.exitCode = 1 })
