/* Actual Vue -> Java -> isolated Redis/H2 export smoke. No model, daily DB, or browser profile. */
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')
const net = require('node:net')
const crypto = require('node:crypto')
const { spawn } = require('node:child_process')
const { chromium, expect } = require('../kaoyan-frontend/node_modules/@playwright/test')
const root = path.resolve(__dirname, '..')

async function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer(); server.on('error', reject)
    server.listen(0, '127.0.0.1', () => { const port = server.address().port; server.close(() => resolve(port)) })
  })
}
async function ready(process, url) {
  for (let i = 0; i < 150; i++) {
    if (process.exitCode !== null) throw new Error('Isolated service exited before ready')
    try { await fetch(url, { signal: AbortSignal.timeout(1000) }); return } catch {}
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error('Isolated service did not become ready')
}
async function stop(process) {
  if (process.exitCode !== null) return
  process.kill('SIGTERM')
  await Promise.race([new Promise(resolve => process.once('exit', resolve)), new Promise(resolve => setTimeout(resolve, 3000))])
  if (process.exitCode === null) process.kill('SIGKILL')
}
async function main() {
  const output = path.resolve(process.argv[2] || '')
  if (!process.argv[2] || fs.existsSync(output)) throw new Error('Provide a new JSON report path')
  const artifacts = output.replace(/\.json$/, '') + '-artifacts'
  if (fs.existsSync(artifacts)) throw new Error('Artifacts path already exists')
  fs.mkdirSync(artifacts, { recursive: true })
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'kaoyan-export-smoke-'))
  const processes = [], handles = []
  let browser
  try {
    const ports = new Set()
    while (ports.size < 3) ports.add(await freePort())
    const [redisPort, javaPort, frontPort] = [...ports]
    const javaBase = `http://127.0.0.1:${javaPort}`, frontBase = `http://127.0.0.1:${frontPort}`
    const env = { ...process.env, JWT_SECRET: crypto.randomBytes(32).toString('hex'), AGENT_INTERNAL_KEY: crypto.randomBytes(32).toString('hex'),
      AGENT_BASE_URL: 'http://127.0.0.1:9', API_PROXY_TARGET: javaBase, LLM_ENABLED: 'false', LLM_API_KEY: '' }
    function launch(name, command, args, cwd) {
      const handle = fs.openSync(path.join(artifacts, name + '.log'), 'w'); handles.push(handle)
      const child = spawn(command, args, { cwd, env, stdio: ['ignore', handle, handle] }); processes.push(child)
      child.on('error', () => {})
      return child
    }
    const redis = launch('redis', process.env.REDIS_SERVER || 'redis-server', ['--bind', '127.0.0.1', '--port', String(redisPort), '--save', '', '--appendonly', 'no'], temporary)
    await new Promise(resolve => setTimeout(resolve, 300))
    if (redis.exitCode !== null) throw new Error('Isolated Redis startup failed')
    const classpath = [path.join(root, 'kaoyan-B/target/test-classes'), path.join(root, 'kaoyan-B/target/classes'), fs.readFileSync(path.join(root, 'kaoyan-B/target/test-classpath.txt'), 'utf8').trim()].join(path.delimiter)
    const java = launch('java', 'java', ['-Djava.awt.headless=true', '-cp', classpath, 'com.kaoyan.ExportSmokeServer', '--server.address=127.0.0.1', `--server.port=${javaPort}`,
      '--spring.datasource.driver-class-name=org.h2.Driver', '--spring.datasource.url=jdbc:h2:mem:export-smoke-browser;MODE=MySQL;DB_CLOSE_DELAY=-1;NON_KEYWORDS=USER',
      '--spring.datasource.username=sa', '--spring.datasource.password=', '--spring.sql.init.mode=always',
      '--spring.sql.init.schema-locations=classpath:schema-test.sql,classpath:schema-practice.sql,classpath:schema-learning-test.sql',
      '--kaoyan.learning.enabled=true', '--kaoyan.learning.initial-delay-ms=3600000', '--spring.data.redis.host=127.0.0.1', `--spring.data.redis.port=${redisPort}`, '--spring.data.redis.password='], temporary)
    await ready(java, javaBase + '/api/users/me')
    const front = launch('frontend', 'node', ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', String(frontPort), '--strictPort'], path.join(root, 'kaoyan-frontend'))
    await ready(front, frontBase)
    browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH, headless: true })
    const checks = []
    for (const [name, viewport] of [['desktop', { width: 1280, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
      const context = await browser.newContext({ viewport, acceptDownloads: true })
      const page = await context.newPage(); page.setDefaultTimeout(15000)
      await page.goto(frontBase + '/login')
      await page.getByPlaceholder('用户名', { exact: true }).fill('export_student_1')
      await page.getByPlaceholder('密码', { exact: true }).fill('test-only-export-password')
      await page.getByRole('button', { name: '登 录' }).click()
      await expect(page).toHaveURL(/\/tasks/)
      await page.goto(frontBase + '/notes')
      await page.getByRole('button', { name: /排序复习笔记/ }).click()
      await expect(page.getByRole('textbox', { name: '笔记正文', exact: true })).toHaveValue(/第二版/)
      const dialog = page.getByRole('dialog', { name: '导出预览', exact: true })
      async function download(label, prefix, allFormats = true) {
        await page.getByRole('button', { name: label, exact: true }).last().click()
        await expect(dialog.getByLabel('文件内容预览')).toBeVisible()
        for (const [format, option] of (allFormats ? [['docx', 'Word（.docx）'], ['pdf', 'PDF（.pdf）'], ['md', 'Markdown（.md）']] : [['pdf', 'PDF（.pdf）']])) {
          await dialog.locator('.el-select').click()
          await page.getByRole('option', { name: option, exact: true }).click()
          const pending = page.waitForEvent('download')
          await dialog.getByRole('button', { name: '下载文件', exact: true }).click()
          const file = await pending
          expect(await file.failure()).toBeNull()
          const destination = path.join(artifacts, `${name}-${prefix}.${format}`)
          await file.saveAs(destination)
          expect(fs.statSync(destination).size).toBeGreaterThan(100)
          checks.push(`${name}: ${prefix}.${format}`)
        }
        await page.screenshot({ path: path.join(artifacts, `${name}-${prefix}.png`), fullPage: false })
        await dialog.getByRole('button', { name: '关闭', exact: true }).click()
        await expect(dialog).not.toBeVisible()
      }
      await download('导出文件', 'note')
      await page.getByRole('button', { name: '历史版本', exact: true }).click()
      await page.getByRole('dialog', { name: '笔记历史版本', exact: true }).getByRole('button', { name: '查看此版本' }).last().click()
      await expect(page.getByRole('dialog', { name: '历史版本（只读）' })).toContainText('第一版')
      await download('导出文件', 'historical-note', false)
      await page.getByRole('dialog', { name: '历史版本（只读）' }).locator('.el-dialog__headerbtn').click()
      await page.getByRole('dialog', { name: '笔记历史版本', exact: true }).locator('.el-dialog__headerbtn').click()
      await page.goto(frontBase + '/stat')
      await download('导出学情报告', 'learning')
      await page.goto(frontBase + '/tasks/history')
      await page.getByRole('button', { name: '查看', exact: true }).first().click()
      await download('导出回答', 'answer')
      await download('导出复习计划', 'plan')
      await download('导出笔记建议', 'proposal')
      await context.close()
    }
    fs.writeFileSync(output, JSON.stringify({ checks, environment: 'isolated H2 + actual Redis + Java + Vue production preview', modelCalls: 0,
      dailyDatabaseAccessed: false, artifacts }, null, 2), { flag: 'wx' })
    console.log(JSON.stringify({ report: output, downloads: checks.length }))
  } finally {
    await browser?.close()
    for (const child of processes.reverse()) await stop(child)
    for (const handle of handles) fs.closeSync(handle)
    fs.rmSync(temporary, { recursive: true, force: true })
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1 })
