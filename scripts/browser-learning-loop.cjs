const { chromium } = require('playwright');
const { expect } = require('@playwright/test');
const assert = require('node:assert/strict');
const base = process.argv[2];
let activeBrowser;
process.once('SIGTERM', async () => { if(activeBrowser)await activeBrowser.close();process.exit(1); });
const stage = text => process.stderr.write(`stage=${text}\n`);
(async () => {
 const browser = await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
 activeBrowser=browser;const checks=[];
 try {
  for(const [i,width] of [1280,390].entries()) {
   const context=await browser.newContext({viewport:{width,height:900}});const page=await context.newPage();page.setDefaultTimeout(15000);
   page.on('response',response=>{if(response.status()>=400)process.stderr.write(`http=${response.status()} path=${new URL(response.url()).pathname}\n`);});
   stage(`width-${width}-login`);
   const login=await context.request.post(base+'/api/auth/login',{data:{username:`learning_student_${i+1}`,password:'test-only-learning-password'}});
   assert.equal(login.status(),200);const token=(await login.json()).data.accessToken;
   const headers={Authorization:`Bearer ${token}`};
   await page.addInitScript(({token,id})=>{localStorage.setItem('token',token);localStorage.setItem('userInfo',JSON.stringify({id,username:`learning_student_${id}`,role:'STUDENT',status:1}));},{token,id:i+1});
   stage('diagnostic-create');await page.goto(base+'/practice');await page.getByRole('button',{name:'开始单选诊断',exact:true}).click();
   await page.waitForURL(/practice\/session\/L-/);const session=page.url().split('/').pop();
   const get=async(path)=>(await (await context.request.get(base+'/api'+path,{headers})).json()).data;
   let state=await get(`/practice/sessions/${session}/state`);assert.equal(state.items.length,20);
   stage('save-draft');await page.getByText('B. 选择乙',{exact:true}).click();await page.getByRole('status').filter({hasText:'已保存到服务端'}).waitFor();
   await page.reload();assert.equal(await page.getByRole('radio',{name:'B. 选择乙'}).isChecked(),true);
   await page.getByRole('button',{name:'提交本题',exact:true}).click();await page.getByText('已提交：B',{exact:true}).waitFor();
   assert.equal(await page.getByText('标准答案：B',{exact:true}).count(),0);
   state=await get(`/practice/sessions/${session}/state`);assert.equal(state.items[0].isCorrect,null);
   // Submit all except the final item through actual HTTP; verify no pre-finish stats leak.
   stage('http-submissions');for(const item of state.items.slice(1,-1)) {
    const response=await context.request.post(`${base}/api/practice/sessions/${session}/answer`,{headers,data:{questionId:item.questionId,itemId:item.itemId,answer:'B',clientRequestId:`http-item-${item.itemId}`}});
    assert.equal(response.status(),200);assert.equal((await response.json()).data.isCorrect,null);
   }
   assert.equal((await get('/stats/overview')).totalQuestions,0);
   stage('finish');await page.getByRole('button',{name:'结束批次并查看结果',exact:true}).click();await page.getByRole('button',{name:'确定',exact:true}).click();
   await page.getByText('标准答案：B',{exact:true}).waitFor();
   const result=await get(`/practice/sessions/${session}/result`);assert.equal(result.answered,19);assert.equal(result.unanswered,1);assert.equal(result.correct,19);
   assert.equal((await get('/stats/overview')).totalQuestions,19);
   for(let retry=0;retry<15;retry++) {
    if((await get('/learning/profile')).independentSamples===19)break;
    await new Promise(resolve=>setTimeout(resolve,500));
   }
   stage('profile');await page.goto(base+'/stat');await page.getByRole('heading',{name:/学情画像/}).waitFor();
   await expect(page.getByTestId('profile-kpi').locator('.evidence .kpi-value'))
    .toHaveText(/^\s*19\s*条\s*$/, {timeout:10000});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   stage('recommend');await page.goto(base+'/schools');await page.locator('.panel .el-switch').click();await page.getByRole('button',{name:'保存推荐设置',exact:true}).click();
   await new Promise(resolve=>setTimeout(resolve,1500));await page.getByRole('button',{name:'刷新状态',exact:true}).click();
   await page.getByText('推荐依据画像版本：',{exact:false}).waitFor({timeout:15000});
   assert.equal((await get('/learning/recommendation-settings')).status,'CURRENT');
   const history=await get('/recommends');assert.equal(history.length,1);assert.equal(history[0].resultPayload.explanationMode,'rules');
   if(process.argv[3])await page.screenshot({path:`${process.argv[3]}-${width}.png`,fullPage:true});
   checks.push({width,diagnosticCount:20,answered:19,unanswered:1,draftRestored:true,noEarlyGrading:true,profileUpdated:true,automaticRulesRecommendation:true});
   await context.close();
  }
 } finally {await browser.close();}
 process.stdout.write(JSON.stringify({checks}));
})().catch(error=>{process.stderr.write(error.stack||String(error));process.exitCode=1;});
