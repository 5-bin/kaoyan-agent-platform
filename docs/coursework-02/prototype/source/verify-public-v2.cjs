const {chromium}=require('../../../../kaoyan-frontend/node_modules/playwright');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const url='https://modao.cc/proto/1tGSwIfito0m4mcLTVKiI2/sharing?view_mode=device&screen=rbpVa4sEZCiOAvssl&canvasId=rcVa4sEZO8ScRh77&device=industrial_hmi_16_10&orientation=portrait';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const base=path.resolve(__dirname,'..'),passed=[];
 const report={date:'2026-11-05',version:'2026-11-05-v2',url,context:'new isolated Edge context, no cookies or saved account state',permissionsChanged:false,passed};
 let page;
 try{
  const context=await browser.newContext({viewport:{width:1700,height:1080}});
  page=await context.newPage();await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});
  let app;
  for(let i=0;i<30;i++){
   for(const frame of page.frames())if(await frame.locator('.proto-badge').filter({hasText:'验收版 v2'}).count().catch(()=>0)){app=frame;break}
   if(app)break;await page.waitForTimeout(1000);
  }
  if(!app)throw Error('Anonymous browser did not find v2 within 30 seconds');
  assert.equal(await app.evaluate(()=>PROTOTYPE_VERSION),'2026-11-05-v2');
  assert.equal(await app.locator('.proto-page').isVisible(),true);
  const act=name=>app.locator(`[data-act="${name}"]`),go=route=>app.evaluate(route=>navigate(route),route);
  const check=async(name,fn)=>{await fn();passed.push(name);console.log('PASS '+name)};
  const shot=name=>page.screenshot({path:path.join(base,'screenshots','墨刀_v2_'+name+'.png')});
  const ready=()=>app.waitForFunction(()=>!S.generating);
  await check('匿名访问 v2 与目录可见',async()=>{await shot('目录')});
  await check('练习判分 → 错题上下文 → Agent 辅导',async()=>{
   await app.locator('[data-go=practice]').filter({hasText:'练习'}).first().click();
   await act('start-practice').click();await app.locator('[data-act=choose][data-value=A]').click();await act('submit-item').click();
   await app.getByText('回答错误 · 标准答案 B',{exact:false}).waitFor();await shot('判分');
   await go('wrong');await act('tutor').first().click();await app.locator('#chat-input').fill('我的选项错在哪里？');await act('send-chat').click();await ready();
   assert.ok((await app.locator('.proto-chat').innerText()).includes('已判分错题 #1 · 折半查找'));assert.ok((await app.locator('#chat-messages').innerText()).includes('每次比较使查找区间减半'));await shot('上下文辅导');
  });
  await check('学情分析 → 确认创建补强练习',async()=>{
   await go('stat');await app.getByRole('button',{name:'查看示例画像'}).click();await app.getByRole('button',{name:'让学情助手分析'}).click();await ready();
   await act('confirm-action').last().click();await act('enter-action').last().click();assert.equal(await app.evaluate(()=>S.route),'practice-session');
  });
  await check('笔记建议预览 → 同一笔记保存 v2',async()=>{
   await go('notes');await act('new-note').click();await app.locator('#note-title').fill('验收：信号量');await app.locator('#note-body').fill('P、V 操作具有原子性。');await act('save-note').click();await act('ask-note').click();await ready();await act('confirm-action').last().click();await shot('笔记建议');await act('save-proposal').click();
   assert.equal(await app.evaluate(()=>S.notes.length),1);assert.equal(await app.evaluate(()=>S.notes[0].version),2);
  });
  await check('后台批量校验 → 整批送审 → 审核通过',async()=>{
   await go('index');await act('admin-demo').click();await act('question-batch').click();await act('fill-batch').click();await act('preview-batch').click();assert.equal(await app.evaluate(()=>S.questions.length),0);await act('submit-batch').click();assert.equal(await app.evaluate(()=>S.questions.length),2);await shot('批量送审');await act('review-question').first().click();await act('approve-question').click();assert.equal(await app.evaluate(()=>S.questions[0].status),'APPROVED');
  });
  await check('后台资料审核确认与取消',async()=>{
   await go('admin-documents');await act('approve-document').first().click();await act('close').click();assert.equal(await app.evaluate(()=>S.documents[0].status),'PENDING');await act('approve-document').first().click();await act('confirm-document').click();assert.equal(await app.evaluate(()=>S.documents[0].status),'PUBLISHED');await shot('资料审核');
  });
  await check('页面规则与目录返回',async()=>{await act('page-rules').click();assert.ok((await app.getByRole('dialog').innerText()).includes('审核'));await act('close').click();await go('index');await shot('验收完成目录')});
  report.anonymousAccess=true;report.result='PASS';
 }catch(e){report.result='FAIL';report.failure=e.stack;if(page)await page.screenshot({path:path.join(base,'screenshots','墨刀_v2_验收失败.png')}).catch(()=>{});throw e}
 finally{fs.writeFileSync(path.join(base,'public-acceptance-validation.json'),JSON.stringify(report,null,2));await browser.close()}
 console.log(JSON.stringify({result:report.result,checks:passed.length,anonymousAccess:report.anonymousAccess},null,2));
})().catch(e=>{console.error(e);process.exit(1)});
