// Isolated production-build UI checks; API config is stubbed, no accounts are created.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const root = path.resolve(__dirname, '../kaoyan-frontend/dist');
const mime = {'.js':'text/javascript','.css':'text/css','.html':'text/html','.json':'application/json'};
(async () => {
  const server = http.createServer((req,res) => {
    let file = path.join(root, new URL(req.url,'http://localhost').pathname);
    if (!file.startsWith(root + path.sep)) file = path.join(root,'index.html');
    if (!fs.existsSync(file) || !fs.statSync(file).isFile()) file = path.join(root,'index.html');
    res.setHeader('Content-Type',mime[path.extname(file)] || 'application/octet-stream');
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  const browser = await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
  const checks=[];
  try {
    for (const policy of ['open','closed','failed']) {
      const context=await browser.newContext();
      await context.route('**/api/auth/config',route => policy==='failed' ? route.abort() : route.fulfill({contentType:'application/json',body:JSON.stringify({code:0,message:'ok',data:{registrationEnabled:policy==='open'}})}));
      const page=await context.newPage();
      await page.goto(`http://127.0.0.1:${server.address().port}/login`);
      await page.getByText(policy==='open'?'立即注册':policy==='closed'?'当前暂不开放注册':'暂无法获取注册状态',{exact:false}).first().waitFor();
      assert.equal(await page.getByRole('link',{name:'立即注册'}).count(),policy==='open'?1:0);
      assert.equal(await page.getByPlaceholder('用户名',{exact:true}).count(),1);
      await page.goto(`http://127.0.0.1:${server.address().port}/register`);
      await page.getByText(policy==='open'?'注册后自动登录':policy==='closed'?'当前暂不开放注册':'暂无法获取注册状态，请稍后重试',{exact:true}).first().waitFor();
      assert.equal(await page.locator('input').count(),policy==='open'?3:0);
      await page.getByRole('link',{name:'直接登录'}).waitFor();
      checks.push(policy);await context.close();
    }
    process.stdout.write(JSON.stringify({checks,productionBuild:true,businessWrites:0}));
  } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error.message);process.exit(1);});
