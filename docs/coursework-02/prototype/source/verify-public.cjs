const {chromium}=require('../../../../kaoyan-frontend/node_modules/playwright');
const fs=require('fs'),path=require('path');
const url='https://modao.cc/proto/1tGSwIfito0m4mcLTVKiI2/sharing?view_mode=device&screen=rbpVa4sEZCiOAvssl&canvasId=rcVa4sEZO8ScRh77&device=industrial_hmi_16_10&orientation=portrait';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 const page=await context.newPage();await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});
 let app;
 for(let i=0;i<25;i++){
  for(const frame of page.frames())if(await frame.locator('.proto-page').count().catch(()=>0)){app=frame;break}
  if(app)break;await page.waitForTimeout(1000);
 }
 if(!app)throw Error('Anonymous browser did not find the interactive prototype within 25 seconds');
 await app.locator('[data-go=practice]').filter({hasText:'练习'}).first().click();
 await app.locator('[data-act=start-practice]').click();
 await app.locator('[data-act=choose][data-value=A]').click();
 await app.locator('[data-act=submit-item]').click();
 await app.getByText('回答错误 · 标准答案 B',{exact:false}).waitFor();
 await page.screenshot({path:path.resolve(__dirname,'../screenshots/墨刀_非成员预览判分.png')});
 await app.locator('[data-go=index]').first().click();
 await page.screenshot({path:path.resolve(__dirname,'../screenshots/墨刀_非成员预览目录.png')});
 const report={date:'2026-11-05',url,context:'new isolated Edge context, no cookies or saved account state',anonymousAccess:true,interaction:'practice create → select A → submit → incorrect answer and standard B visible',permissionsChanged:false};
 fs.writeFileSync(path.resolve(__dirname,'../public-validation.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exit(1)});
