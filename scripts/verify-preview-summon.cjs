// Regression: static previews must use the native service, never their own POST route.
const { chromium } = require('../output/qa-tools/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const bridge = 'http://127.0.0.1:8086';
const preview = 'http://127.0.0.1:5500';
const status = async () => (await fetch(bridge + '/api/pet/status')).json();
async function waitState(test) {
  for (let i=0; i<60; i++) { const s=await status(); if(test(s)) return s; await new Promise(r=>setTimeout(r,100)); }
  throw new Error('Desktop state did not synchronize');
}
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  const results=[],errors=[],requests=[];
  const check=(name,ok)=>{assert.ok(ok,name);results.push(name)};
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(r.url().includes('/api/pet/'))requests.push({url:r.url(),method:r.method()})});
    await page.goto(preview + '/index.html',{waitUntil:'networkidle'});
    await page.locator('.cast[data-character="robot"]').click();
    await page.locator('#summonPet').click();
    await page.waitForFunction(()=>document.getElementById('toast').textContent.includes('已来到桌面'));
    const pet=await waitState(s=>s.active&&s.ready&&s.state.character==='robot');
    check('Static preview summons the classic pet',pet.pid>0);
    check('Preview sends POST to port 8086',requests.some(r=>r.method==='POST'&&r.url===bridge+'/api/pet/summon'));
    check('No pet API POST reaches the static server',!requests.some(r=>r.method==='POST'&&r.url.startsWith(preview)));
    await page.locator('#summonPet').click();
    check('Preview reuses the same native instance',(await status()).pid===pet.pid);
    await page.evaluate(()=>EG_MAIN.setEmotion('13'));
    await waitState(s=>s.state.emotion==='13');
    check('Preview expressions synchronize across ports',true);
    await page.locator('.cast[data-character="pink-robot"]').click();
    await waitState(s=>s.state.character==='pink-robot');
    check('Preview character changes synchronize',true);
    await page.locator('#sketchToggle').check(); await waitState(s=>s.state.sketch);
    await page.locator('#sketchToggle').uncheck(); await waitState(s=>!s.state.sketch);
    check('Preview sketch controls synchronize',true);
    await page.locator('.cast[data-character="robot"]').click();
    await page.evaluate(()=>EG_MAIN.setEmotion('02'));
    await waitState(s=>s.state.character==='robot'&&s.state.emotion==='02');
    const mockUrl=bridge+'/api/pet/summon';
    for(const scenario of [
      {name:'Empty success response has a helpful message',code:200,body:'',message:'服务返回异常'},
      {name:'Malformed JSON never exposes a parsing exception',code:200,body:'{bad',message:'服务返回异常'},
      {name:'Empty 405 response explains how to start the service',code:405,body:'',message:'start.bat'},
      {name:'Structured launch errors remain visible',code:503,body:JSON.stringify({ok:false,message:'测试启动失败'}),message:'测试启动失败'},
      {name:'Unavailable service explains how to start it',abort:true,message:'start.bat'}
    ]) {
      await page.route(mockUrl,async route=>{
        if(route.request().method()==='OPTIONS')return route.continue();
        if(scenario.abort)return route.abort('connectionrefused');
        return route.fulfill({status:scenario.code,contentType:'application/json',body:scenario.body,headers:{'Access-Control-Allow-Origin':preview}});
      });
      await page.locator('#summonPet').click();
      await page.waitForFunction(()=>!document.getElementById('summonPet').disabled);
      const toast=await page.locator('#toast').textContent();
      check(scenario.name,toast.includes(scenario.message)&&!/Unexpected|SyntaxError|Failed to execute/.test(toast));
      await page.unroute(mockUrl);
    }
    check('Summon button can be retried after failures',await page.locator('#summonPet').isEnabled());
    check('No uncaught browser errors',errors.length===0);
    const report={passed:results.length,results,errors,desktop_pid:pet.pid};
    fs.writeFileSync('output/preview-summon-verification.json',JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
