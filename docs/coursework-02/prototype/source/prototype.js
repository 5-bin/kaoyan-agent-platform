/* Offline prototype. All records and consent below are simulated, in memory only. */
'use strict';
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>Array.from(r.querySelectorAll(s));
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const btn=(text,act,cls='',extra='')=>`<button type="button" class="proto-btn ${cls}" data-act="${act}" ${extra}>${text}</button>`;
const goBtn=(text,path,cls='')=>`<button type="button" class="proto-btn ${cls}" data-go="${path}">${text}</button>`;
const tag=(text,cls='')=>`<span class="proto-tag ${cls}">${esc(text)}</span>`;
const notice=(text,cls='')=>`<div class="proto-notice ${cls}">${text}</div>`;
const field=(label,id,value='',type='text',wide=false)=>`<label class="proto-field ${wide?'wide':''}">${label}<input id="${id}" type="${type}" value="${esc(value)}"></label>`;
const Q=[
 {id:1,subject:'数据结构',point:'折半查找',q:'对长度为 n 的有序顺序表进行折半查找，最坏情况下关键字比较次数的数量级是？',options:['O(1)','O(log n)','O(n)','O(n log n)'],answer:'B',analysis:'每次比较使查找区间减半。最坏比较次数约为 ⌊log₂n⌋ + 1，因此数量级为 O(log n)。',hint:['关注每次查找后候选区间如何变化。','设比较 k 次后区间长度约为 n / 2ᵏ，再考虑区间缩小到 1 的条件。']},
 {id:2,subject:'操作系统',point:'信号量',q:'下列关于信号量的说法中，正确的是？',options:['P 操作只用于释放资源','信号量的值始终大于零','P、V 操作应当以原子方式执行','信号量不能用于进程同步'],answer:'C',analysis:'P、V 操作需要保证原子性，才能安全协调并发进程。具体信号量定义可能允许负值。',hint:['先考虑多个进程同时修改同一个计数值会发生什么。','资源计数的读取和修改不能被另一个进程穿插执行。']},
 {id:3,subject:'计算机网络',point:'TCP 可靠传输',q:'TCP 主要通过哪组机制实现可靠传输？',options:['仅依赖 IP 网络层','序号、确认与超时重传','广播与静态路由','仅扩大接收缓存'],answer:'B',analysis:'序号用于标识数据位置，确认反映接收进展，超时重传用于处理丢失。',hint:['可靠传输需要知道哪些数据已收到、哪些可能丢失。','比较“识别数据、确认接收、处理丢失”三个环节。']},
 {id:4,subject:'计算机组成原理',point:'程序计数器',q:'程序计数器 PC 通常保存什么信息？',options:['下一条将要执行的指令地址','当前指令的运算结果','所有通用寄存器的内容','外存中全部程序的长度'],answer:'A',analysis:'程序计数器通常保存下一条将执行指令的地址。跳转等指令会改变控制流。',hint:['考虑 CPU 应当如何知道下一步去哪里取指令。','区分指令地址与指令运算得到的数据。']},
 {id:5,subject:'数据结构',point:'排序稳定性',q:'在通常的实现中，下列哪种排序算法是稳定的？',options:['直接选择排序','归并排序','堆排序','快速排序'],answer:'B',analysis:'归并时在关键字相等的情况下优先选择左侧元素，可保留相等关键字的原始相对次序。',hint:['稳定性指相等关键字记录的相对次序是否保持。','考察合并两个有序序列时，如何选择相等关键字。']}
];
const LABELS={index:'原型演示目录',login:'登录',register:'注册',home:'首页',profile:'个人中心',practice:'开始刷题','practice-session':'练习作答','practice-session-answered':'已判分作答',diagnostic:'单选诊断',result:'批次结果',wrong:'错题本',favorite:'我的收藏',assistant:'Agent 助手',stat:'学习统计',schools:'院校库','school-detail':'院校详情',documents:'备考资料',notes:'个人笔记','admin-questions':'题目录入与审核','admin-documents':'资料审核',history:'助手任务历史'};
const S={route:'index',role:'STUDENT',profile:{school:'示例大学 A',major:'计算机科学与技术',year:2027,degree:'academic',background:'408 备考中'},cfg:{source:'NORMAL',subject:'数据结构',difficulty:'MEDIUM',count:5},session:null,wrong:new Set([1,2]),favorite:new Set([1,2]),history:{1:{user:'A',correct:false},2:{user:'A',correct:false}},sessions:[],profileReady:false,model:false,scopes:[],chat:[],context:'',generation:0,generating:false,action:null,notes:[],noteId:null,dirty:false,noteDraft:null,proposal:null,questions:[],documents:[{id:1,title:'示例资料：数据结构复习要点',subject:'数据结构',status:'PENDING'},{id:2,title:'示例资料：操作系统进程管理',subject:'操作系统',status:'PENDING'}],batch:null,schoolId:1,schoolFilter:'',documentFilter:''};
const PROTOTYPE_VERSION='2026-11-05-v2';
let toastTimer;
function gradedItems(){return [...new Set([...S.sessions,...(S.session?[S.session]:[])])].flatMap(s=>s.items).filter(i=>i.submitted&&i.correct!==null)}
function markdown(text){return esc(text).split(/\n{2,}/).map(part=>{if(/^#{1,3} /.test(part)){const level=part.match(/^#+/)[0].length;return `<h${level+2}>${part.replace(/^#+ /,'')}</h${level+2}>`}return '<p>'+part.replace(/\n/g,'<br>')+'</p>'}).join('')}
function showRules(){const rules=S.route.includes('session')||['practice','diagnostic','result'].includes(S.route)?['选择仅保存草稿，提交后才计作答。','普通练习提交本题后判分；诊断结束后统一判分，诊断不提供提示。','未答不计错题，提示辅助不计入独立正确率。']:S.route==='assistant'?['未授权时使用本地规则；模型与记录类别均授权后才展示模拟模型解释。','创建练习、保存笔记前需要确认，取消不执行。','解释不能改变标准答案；缺少资料时明确说明覆盖范围。']:S.route==='notes'?['手动保存才产生新版本；未保存离开需确认。','助手读取选定的已保存版本，建议经确认后保存新版本。','历史版本只读；版本冲突时保留编辑并提示核对。']:S.route.startsWith('admin')?['录入与批量送审后处于待审核，预览不会写入题库。','审核通过才发布；驳回必须填写意见。','资料审核通过与拒绝均需明确确认。']:['所有账号、题目、招生信息与模型结果均为模拟。','缺失来源、人数和分数明确标为未登记或待核实。','本次演示记录保存在当前组件中；刷新恢复初始状态。'];modal('当前页面规则', '<ul>'+rules.map(r=>'<li>'+r+'</li>').join('')+'</ul>')}
function toast(text){const e=$('#proto-toast');e.textContent=text;e.style.display='block';clearTimeout(toastTimer);toastTimer=setTimeout(()=>e.style.display='none',2400)}
function modal(title,body,footer=btn('关闭','close')){$('#proto-modal-root').innerHTML=`<div class="proto-overlay"><section role="dialog" aria-modal="true" aria-label="${esc(title)}" class="proto-dialog"><h3>${esc(title)}</h3>${body}<div class="proto-actions">${footer}</div></section></div>`}
function close(){$('#proto-modal-root').innerHTML=''}
function page(title,body,sub=''){return `<div class="proto-page"><h2>${title}</h2><p class="proto-subtitle">${sub}</p>${body}</div>`}
function card(body){return `<section class="proto-card">${body}</section>`}
function navigate(route,force=false){
 if(S.route==='notes'&&S.dirty&&!force){modal('尚有未保存的笔记','<p>离开后将丢失本次未保存编辑。</p>',btn('继续编辑','close')+btn('放弃本次编辑并离开','leave-note','primary',`data-target="${route}"`));return}
 close();S.route=route;render();
}
function shell(route){
 const base=SNAPSHOTS[route]||SNAPSHOTS.home;
 $('#prototype-root').innerHTML=base;
 const top=$('.topbar');
 if(top){const tools=document.createElement('div');tools.className='proto-toptools';tools.innerHTML=`<span class="proto-badge">验收版 v2 · 模拟数据</span>${btn('页面规则','page-rules','small')}${goBtn('演示目录','index','small')}${btn('退出演示','logout','small')}`;top.insertBefore(tools,$('.user',top)?.parentElement||null);const crumb=$('.crumb');if(crumb)crumb.textContent=LABELS[route]||'原型演示';}
 else{const e=document.createElement('div');e.className='proto-auth-tools';e.innerHTML=`<span class="proto-badge">模拟账号，请勿输入真实密码</span>${goBtn('演示目录','index','small')}`;$('#prototype-root').append(e)}
 const nav={'首页':'home','刷题':'practice','Agent 助手':'assistant','个人笔记':'notes','错题本':'wrong','我的收藏':'favorite','学习统计':'stat','院校库':'schools','备考资料':'documents'};
 $$('.el-menu-item').forEach(e=>{const path=nav[e.textContent.trim()];if(path){e.dataset.go=path;e.classList.toggle('is-active',route===path)}});
 const menu=$('.menu');if(menu&&S.role==='ADMIN'){menu.insertAdjacentHTML('beforeend',`<div class="menu-group"><div class="group-label">管理</div>${goBtn('题目录入与审核','admin-questions')}${goBtn('资料审核','admin-documents')}</div>`)}
 const user=$('.user');if(user){user.dataset.go='profile';user.title='个人中心'}
 $$('button.assistant-launch').forEach(e=>{e.dataset.go='assistant'});
 $$('input[type=password]').forEach(e=>e.autocomplete='new-password');
}
function main(html){const m=$('main.content');if(m)m.innerHTML=html}
function tile(code,title,desc,route){return `<button class="proto-tile" data-go="${route}"><span class="proto-step">${code}</span><b>${title}</b><small>${desc}</small></button>`}
function renderIndex(){main(page('考研 Agent 平台 · 交互原型',notice('T01 学习闭环 + T02 账号资源与后台。沿用现有 HTML 样式，所有记录在本次演示中模拟；刷新后恢复初始状态。')+
 card(`<h3>从业务路径开始</h3><div class="proto-grid">${tile('路径 01','练习 → 错题 → 辅导','开始练习，第一题选 A 提交，再到错题继续辅导。','practice')}${tile('路径 02','学情 → 分析 → 补强','查看画像，生成补强建议，确认后创建练习。','stat')}${tile('路径 03','账号 → 资源 → 笔记','模拟登录、查询院校、阅读资料、保存笔记。','login')}</div><div class="proto-actions">${btn('演示管理员流程','admin-demo','primary')}${btn('重置本次演示','reset')}</div>`)+
 `<h3>T01 学习页面</h3><div class="proto-grid">${tile('L01','练习首页','配置练习与单选诊断','practice')}${tile('L02','答题未判分','选择、保存与提交','practice-session')}${tile('L03','答题已判分','判分、解析与辅导','practice-session-answered')}${tile('L04','错题本','收藏、移出与追问','wrong')}${tile('L05','我的收藏','收藏回看与重练','favorite')}${tile('L06','Agent 助手','授权、生成、确认与停止','assistant')}${tile('L07','学习统计','画像、样本与补强','stat')}${tile('L08','单选诊断','结束前隐藏判分','diagnostic')}${tile('L09','批次结果','已答、未答与辅助口径','result')}</div>`+
 `<h3 style="margin-top:28px">T02 账号、资源与后台</h3><div class="proto-grid">${tile('A01','登录','模拟表单校验','login')}${tile('A02','注册','密码确认与学生身份','register')}${tile('A03','首页','学习与资源入口','home')}${tile('A04','个人中心','保存备考档案','profile')}${tile('A05','院校列表','筛选并查看详情','schools')}${tile('A06','备考资料','筛选与阅读正文','documents')}${tile('A07','个人笔记','编辑、预览和版本','notes')}${tile('A08','院校详情','年份、专业与来源口径','school-detail')}${tile('M01','题目录入与审核','录入／批量预览 → 送审','admin-questions')}${tile('M02','资料审核','通过与拒绝','admin-documents')}</div>`,'设计基线 94b8a9f · 2026 年 11 月 · 桌面演示'))}
function render(){
 shell(S.route);
 switch(S.route){
 case 'index':renderIndex();break;
 case 'home':{const items=gradedItems();const nums=$$('main.content .stats .num');if(nums[0])nums[0].textContent=items.length;if(nums[1])nums[1].textContent=items.filter(i=>i.correct).length;$$('main.content .stats .lbl').slice(0,2).forEach((n,i)=>n.textContent=i?'本次答对':'本次已答');break}
 case 'login':case 'register':break;
 case 'profile':renderProfile();break;
 case 'practice':renderPractice();break;
 case 'practice-session':if(!S.session)startSession(false,false,[1,5]);renderSession();break;
 case 'practice-session-answered':if(!S.session||!S.session.items[0].submitted){startSession(false,false,[1,5]);S.session.items[0].user='A';submitItem(false)}renderSession();break;
 case 'diagnostic':if(!S.session||S.session.kind!=='DIAGNOSTIC')startSession(true,false);renderSession();break;
 case 'result':if(!S.session){startSession(false,false,[1,5]);S.session.items[0].user='A';submitItem(false);finishSession(false)}renderResult();break;
 case 'wrong':case 'favorite':renderMarks();break;
 case 'stat':renderStats();break;
 case 'assistant':renderAssistant();break;
 case 'history':main(page('助手任务历史',S.chat.filter(x=>x.role!=='user').map(x=>card(`<p>${esc(x.text)}</p>${goBtn('回到助手继续','assistant')}`)).join('')||notice('暂无助手记录。'),'只展示本次模拟会话'));break;
 case 'notes':renderNotes();break;
 case 'schools':renderSchools();break;
 case 'school-detail':renderSchoolDetail();break;
 case 'documents':renderDocuments();break;
 case 'admin-questions':case 'admin-documents':if(S.role!=='ADMIN'){main(page('管理员演示入口',notice('学生身份无法操作管理页面。此处可切换为预设的管理员演示身份。','warn')+btn('进入管理员演示','admin-demo','primary',`data-target="${S.route}"`)))}else if(S.route==='admin-questions')renderQuestions();else renderAdminDocuments();break;
 default:break;
 }
}
function renderProfile(){main(page('个人中心',card(`<div class="proto-row"><div class="proto-schoolletter">示</div><div><h3>示例考生</h3>${tag(S.role==='ADMIN'?'管理员演示':'学生演示')}</div></div>`)+card(`<h3>备考档案</h3><div class="proto-fields">${field('目标院校','p-school',S.profile.school)}${field('目标专业','p-major',S.profile.major)}${field('考试年份','p-year',S.profile.year,'number')}<label class="proto-field">学位类型<select id="p-degree"><option value="academic" ${S.profile.degree==='academic'?'selected':''}>学硕</option><option value="professional" ${S.profile.degree==='professional'?'selected':''}>专硕</option></select></label><label class="proto-field wide">背景说明<textarea id="p-background" rows="3">${esc(S.profile.background)}</textarea></label></div><div class="proto-actions">${btn('保存档案','save-profile','primary')}</div>`),'管理账号信息与备考档案'))}
function renderPractice(){
 const c=S.cfg;main(page('开始刷题',card(`<h3>建立学情画像</h3><p>默认四科各 5 道单选题，缺题时进行局部诊断，结束后统一判分。</p>${btn('开始单选诊断','start-diagnostic','primary')}`)+card(`<h3>练习设置</h3><div class="proto-fields"><label class="proto-field">范围<select id="cfg-source"><option value="NORMAL" ${c.source==='NORMAL'?'selected':''}>普通练习</option><option value="WRONG" ${c.source==='WRONG'?'selected':''}>我的错题</option><option value="FAVORITE" ${c.source==='FAVORITE'?'selected':''}>我的收藏</option></select></label><label class="proto-field">科目<select id="cfg-subject">${['数据结构','操作系统','计算机网络','计算机组成原理'].map(x=>`<option ${c.subject===x?'selected':''}>${x}</option>`).join('')}</select></label><label class="proto-field">难度<select id="cfg-difficulty">${[['MEDIUM','中等'],['EASY','简单'],['HARD','困难']].map(([v,l])=>`<option value="${v}" ${c.difficulty===v?'selected':''}>${l}</option>`).join('')}</select></label>${field('题量（1—50）','cfg-count',c.count,'number')}</div>${notice('演示题库包含 5 道自编题，各科可用题数有限；不足时返回实际数量，不补造题目。')}<div class="proto-actions">${btn('开始刷题','start-practice','primary')}</div>`)+card(`<h3>练习记录</h3>${S.sessions.length?`<table class="proto-table"><tr><th>批次</th><th>已答</th><th>正确</th><th>正确率</th><th>操作</th></tr>${S.sessions.map((s,i)=>`<tr><td>${s.kind==='DIAGNOSTIC'?'单选诊断':'普通练习'} ${i+1}</td><td>${metrics(s).answered}</td><td>${metrics(s).correct}</td><td>${pct(metrics(s).accuracy)}</td><td>${btn('查看详情','open-session','small',`data-index="${i}"`)}</td></tr>`).join('')}</table>`:'<p class="proto-muted">本次演示尚无完成的练习记录。</p>'}`),'选择范围、科目、难度和题量，创建固定题序的模拟练习'))}
function startSession(diagnostic=false,nav=true,ids=null){
 let list=ids?Q.filter(q=>ids.includes(q.id)):diagnostic?Q.slice(0,3):Q.filter(q=>q.subject===S.cfg.subject&&S.cfg.difficulty==='MEDIUM');
 if(!diagnostic&&!ids&&S.cfg.source!=='NORMAL'){const marks=S.cfg.source==='WRONG'?S.wrong:S.favorite;list=list.filter(q=>marks.has(q.id))}
 list=list.slice(0,S.cfg.count);if(!list.length){toast('当前条件没有可练题目，请调整范围或科目');return false}
 S.session={id:'DEMO-'+(S.sessions.length+1),kind:diagnostic?'DIAGNOSTIC':'PRACTICE',state:'RUNNING',index:0,items:list.map(q=>({q,user:'',submitted:false,correct:null,hint:0})),saved:false};
 if(nav)navigate(diagnostic?'diagnostic':'practice-session');return true;
}
function current(){return S.session.items[S.session.index]}
function pct(v){return v==null?'暂无数据':Math.round(v*100)+'%'}
function metrics(s=S.session){const a=s.items.filter(i=>i.submitted),correct=a.filter(i=>i.correct).length,ind=a.filter(i=>!i.hint);return{total:s.items.length,answered:a.length,correct,wrong:a.length-correct,unanswered:s.items.length-a.length,assisted:a.filter(i=>i.hint).length,accuracy:a.length?correct/a.length:null,independentAccuracy:ind.length?ind.filter(i=>i.correct).length/ind.length:null}}
function renderSession(){
 const s=S.session,i=current(),reveal=i.submitted&&(s.kind!=='DIAGNOSTIC'||s.state==='FINISHED');
 main(page(s.kind==='DIAGNOSTIC'?'单选诊断':'练习作答',`<div class="proto-row proto-between">${goBtn('← 返回练习','practice')}${tag(s.state==='RUNNING'?'进行中':'已结束')}</div>`+
 (s.kind==='DIAGNOSTIC'?notice('局部诊断：演示中三科各 1 题，其他配额缺题。结束前不展示正误与解析，也不提供提示；不据此估计完整 408 分数。','warn'):'')+
 `<div class="proto-answercard">${s.items.map((x,n)=>`<button data-act="move-item" data-index="${n}" class="${n===s.index?'active ':''}${x.submitted?'done':''}">${n+1}${x.hint?'*':''}</button>`).join('')}</div>`+
 card(`<div class="proto-row proto-between"><span>第 ${s.index+1} / ${s.items.length} 题</span><span>${tag(i.q.subject)} ${tag(i.q.point)} ${i.hint?tag('提示辅助','warn'):''}</span></div><h3 style="margin-top:22px">${esc(i.q.q)}</h3>${i.q.options.map((v,n)=>{const key='ABCD'[n];return `<button class="proto-choice ${i.user===key?'picked ':''}${reveal&&i.q.answer===key?'correct ':''}${reveal&&i.user===key&&!i.correct?'wrong':''}" data-act="choose" data-value="${key}" ${i.submitted||s.state!=='RUNNING'?'disabled':''}><span class="key">${key}</span><span>${esc(v)}</span></button>`}).join('')}
 ${i.submitted?notice(reveal?`${i.correct?'回答正确':'回答错误'} · 标准答案 ${i.q.answer}<br>${esc(i.q.analysis)}`:'已提交本题，诊断结束后统一展示正误与解析。',reveal&&!i.correct?'warn':''):`<p class="proto-muted" role="status">${i.user?'已选择 '+i.user+' · 模拟草稿已保存':'请选择一个选项，选择不等于提交。'}</p>`}
 ${i.hint&&!i.submitted?notice('提示：'+esc(i.q.hint[i.hint-1])):''}
 <div class="proto-actions">${!i.submitted&&s.state==='RUNNING'?btn('提交本题','submit-item','primary',!i.user?'disabled':''):''}${i.submitted&&s.index<s.items.length-1?btn('下一题','next-item','primary'):''}${s.kind!=='DIAGNOSTIC'&&!i.submitted&&s.state==='RUNNING'?btn(i.hint?'查看解题方向':'查看概念提示','hint','',i.hint>=2?'disabled':''):''}${btn(S.favorite.has(i.q.id)?'取消收藏':'收藏本题','toggle-favorite','',`data-id="${i.q.id}"`)}${s.state==='RUNNING'?btn('结束批次并查看结果','ask-finish'):goBtn('查看批次结果','result')}${reveal&&!i.correct?btn('到助手继续辅导','tutor','',`data-id="${i.q.id}"`):''}</div>`),'题目与判分均为预设模拟；演示标准答案不受助手解释影响'))
}
function submitItem(redraw=true){const s=S.session,i=current();if(!i.user||i.submitted||s.state!=='RUNNING')return;i.submitted=true;if(s.kind!=='DIAGNOSTIC'){i.correct=i.user===i.q.answer;S.history[i.q.id]={user:i.user,correct:i.correct};if(!i.correct)S.wrong.add(i.q.id)}if(s.items.every(x=>x.submitted)){finishSession(false);if(redraw){navigate('result');return}}if(redraw)renderSession()}
function finishSession(nav=true){const s=S.session;if(s.state!=='FINISHED'){s.items.filter(x=>x.submitted).forEach(i=>{i.correct=i.user===i.q.answer;S.history[i.q.id]={user:i.user,correct:i.correct};if(!i.correct)S.wrong.add(i.q.id)});s.state='FINISHED';if(!s.saved){S.sessions.push(s);s.saved=true}S.profileReady=S.profileReady||s.items.some(i=>i.submitted)}if(nav)navigate('result')}
function renderResult(){const s=S.session;if(s.state==='RUNNING'){main(page('批次尚未结束',notice('请先结束批次，再查看最终统计；诊断进行中不展示判分结果。','warn')+goBtn('返回继续作答','practice-session','primary')+btn('结束批次并查看结果','ask-finish')));return}const m=metrics();main(page('批次结果',notice(s.kind==='DIAGNOSTIC'?'诊断已结束，现已统一判分。局部诊断不输出完整 408 参考分。':'批次已结束；未提交选择不计作答，未答不计错题。')+`<div class="proto-kpis">${[['有效已答',m.answered],['未答',m.unanswered],['正确',m.correct],['正确率',pct(m.accuracy)]].map(([a,b])=>`<div class="proto-kpi"><strong>${b}</strong><span>${a}</span></div>`).join('')}</div>`+card(`<p>实际题数 ${m.total} · 撤回 0 · 提示辅助 ${m.assisted} · 独立正确率 ${pct(m.independentAccuracy)}</p><p class="proto-muted">分母为有效已提交作答；独立正确率排除使用提示的作答。本次无撤回题。</p><table class="proto-table"><tr><th>题目</th><th>你的答案</th><th>结果</th><th>操作</th></tr>${s.items.map((i,n)=>`<tr><td>${n+1}. ${esc(i.q.point)}</td><td>${i.submitted?i.user:'未提交'}</td><td>${!i.submitted?tag('未答','warn'):tag(i.correct?'正确':'错误',i.correct?'good':'bad')}</td><td>${btn('回顾','review-item','small',`data-index="${n}"`)}</td></tr>`).join('')}</table><div class="proto-actions">${goBtn('查看错题本','wrong','primary')}${goBtn('查看学情画像','stat')}${goBtn('再练一批','practice')}</div>`),'学习画像正在模拟更新；所有数值均由本次固定题目计算'))}
function renderMarks(){const wrong=S.route==='wrong',marks=wrong?S.wrong:S.favorite;const items=Q.filter(q=>marks.has(q.id));main(page(wrong?'错题本':'我的收藏',`<div class="proto-row proto-between"><p>共 ${items.length} 道题目</p>${btn('从当前集合开始重练','practice-marks','primary')}</div>`+(items.map(q=>{const h=S.history[q.id];return card(`<div class="proto-row">${tag(q.subject)} ${tag(q.point)} ${tag(wrong?'历史错答':'已收藏',wrong?'bad':'warn')}</div><h3 style="margin-top:14px">${esc(q.q)}</h3>${h?`<p>历史作答：${h.user} · 标准答案：${q.answer}</p><p>${esc(q.analysis)}</p>`:notice('尚未提交本题，答案与解析隐藏。')}<div class="proto-actions">${btn(S.favorite.has(q.id)?'取消收藏':'收藏','toggle-favorite','',`data-id="${q.id}"`)}${wrong?btn('移出错题','ask-remove-wrong','danger',`data-id="${q.id}"`):''}${wrong&&h&&!h.correct?btn('到助手继续辅导','tutor','primary',`data-id="${q.id}"`):''}</div>`)}).join('')||card('<p class="proto-muted">当前集合为空，可以先完成练习。</p>')),'历史解析对应历史作答；重新练习进入独立批次'))}
function renderStats(){const records=gradedItems();const correct=records.filter(i=>i.correct).length;main(page('学习统计',card(`<div class="proto-row proto-between"><h3>学情画像</h3>${btn('刷新画像','refresh-profile')}</div>${notice(S.profileReady?'模拟画像已更新 · v2 · 仍有样本不足分组':'尚未诊断。可先完成单选诊断，或查看示例画像后演示补强流程。',S.profileReady?'':'warn')}<div class="proto-kpis"><div class="proto-kpi"><strong>证据不足</strong><span>408 参考分 · 不估计完整考试成绩</span></div><div class="proto-kpi"><strong>${S.profileReady?'局部覆盖':'暂无画像'}</strong><span>蓝图覆盖不等于学习进度</span></div><div class="proto-kpi"><strong>${records.filter(i=>!i.hint).length}</strong><span>本次独立作答证据</span></div><div class="proto-kpi"><strong>样本不足</strong><span>按知识点去重的独立证据</span></div></div>${S.profileReady?`<h3>薄弱知识点（示例）</h3>${[['折半查找',35],['信号量',48],['TCP 可靠传输',62]].map(([p,n])=>`<div class="proto-progress-row"><span>${p}</span><div class="proto-bar"><i style="width:${n}%"></i></div><span>${n}/100</span></div>`).join('')}<p class="proto-muted">以上为预置画像示意，非由少量演示作答估计的真实掌握度。</p>`:''}<div class="proto-actions">${btn('让学情助手分析','analyze-study','primary')}${btn('查看示例画像','example-profile')}${btn('开始单选诊断','start-diagnostic')}</div>`)+card(`<h3>本次演示作答统计</h3><div class="proto-kpis">${[['有效作答次数',records.length],['正确次数',correct],['正确率',pct(records.length?correct/records.length:null)],['学习时长','未记录']].map(([a,b])=>`<div class="proto-kpi"><strong>${b}</strong><span>${a}</span></div>`).join('')}</div><p>区间统计按有效提交次数计算，画像按去重独立证据计算，分母不同。</p>${btn('导出模拟学情报告','export-report')}`),'近 30 天按上海日期展示；本原型仅计算本次会话的模拟练习'))}
function renderAssistant(){
 if(S.route!=='assistant')return;
 main(`<div class="proto-chat"><aside class="proto-chat-history">${btn('新建会话','new-chat','primary')}${goBtn('任务历史','history')}<p class="proto-muted">本次演示会话</p>${S.chat.filter(x=>x.role==='user').slice(-6).map(x=>`<div class="proto-notice">${esc(x.text).slice(0,45)}</div>`).join('')}${goBtn('个人笔记','notes')}</aside><section class="proto-chat-main"><header class="proto-chat-head"><h2>考研助手</h2><div class="proto-row">${btn('隐私设置','privacy','small')}${btn('演示生成失败','simulate-failure','small')}</div></header><p class="proto-muted">${S.model?'外部模型已模拟授权 · 不发出真实请求':'外部模型未授权 · 使用本地规则'}</p>${S.context?notice('当前上下文：'+esc(S.context)):''}<div class="proto-chat-messages" id="chat-messages">${!S.chat.length?`<div class="proto-chat-welcome"><h3>今天想解决什么问题？</h3><p class="proto-muted">查知识、分析学情、安排练习，也可以整理复习笔记。</p><div class="proto-chat-prompts">${btn('分析学情并安排复习','prompt-study')}${btn('安排题库练习','prompt-practice')}${btn('整理一份复习笔记','prompt-note')}</div></div>`:S.chat.map(m=>`<article class="proto-message ${m.role}">${esc(m.text).replace(/\n/g,'<br>')}${m.mode?`<small>${m.mode} · 演示内容</small>`:''}</article>`).join('')}${S.generating?card(`<p role="status">正在生成解释与操作建议…</p>${btn('停止生成','stop-generation')}`):''}${S.action?renderAction():''}${S.chat.at(-1)?.mode==='失败'||S.chat.at(-1)?.mode==='已停止'?btn('重试本次生成','retry-chat','primary'):''}</div><div class="proto-chat-compose"><textarea id="chat-input" aria-label="聊天输入" placeholder="输入问题，或要求安排练习、整理笔记" ${S.generating?'disabled':''}></textarea><div class="proto-actions"><span class="proto-muted">Enter 发送 · Shift+Enter 换行</span>${btn('发送','send-chat','primary',S.generating?'disabled':'')}</div></div></section></div>`);
 const messages=$('#chat-messages');if(messages)messages.scrollTop=messages.scrollHeight;
}
function renderAction(){const a=S.action;return card(`<h3>${a.type==='NOTE'?'笔记建议':'建议创建补强练习'}</h3><p>${a.type==='NOTE'?'建议需预览后确认保存，原笔记不会被直接覆盖。':'包含 '+a.ids.length+' 道可练题；开始前需要你确认。'}</p>${a.status==='PENDING'?`<div class="proto-actions">${btn(a.type==='NOTE'?'预览笔记建议':'开始练习','confirm-action','primary')}${btn('取消','cancel-action')}</div>`:a.status==='SUCCESS'?notice('操作已完成。')+(a.type==='NOTE'?goBtn('查看已保存笔记','notes'):btn('进入已创建练习','enter-action','primary')):notice('操作已取消，没有创建记录。','warn')}`)}
function sendChat(text,fail=false){
 text=(text??$('#chat-input')?.value??'').trim();if(!text||S.generating)return;
 S.lastFailed=text;S.chat.push({role:'user',text});S.generating=true;S.action=null;
 const token=++S.generation,context=S.context,note=S.contextNote?{...S.contextNote}:null;
 renderAssistant();
 setTimeout(()=>{
  if(token!==S.generation)return;S.generating=false;
  if(fail){S.chat.push({role:'assistant',text:'本次生成失败，未创建练习或修改笔记。可以重试，也可以继续使用本地规则。',mode:'失败'});renderAssistant();return}
  const focused=Number(context.match(/#(\d+)/)?.[1]);
  const match=Q.find(q=>text.includes(q.point)||text.includes(q.subject))||(focused?Q.find(q=>q.id===focused):null);
  let answer;
  if(/笔记|整理/.test(text)){
   const q=match||Q[0];const title=note?.title||q.point+'复习要点';
   const body=note?note.body+'\n\n## 复习检查\n\n1. 用自己的话复述核心概念。\n2. 完成对应知识点练习并回看错误原因。':'# '+title+'\n\n'+q.analysis+'\n\n## 自测\n\n'+q.hint[0];
   S.action={type:'NOTE',status:'PENDING',text:body,title,noteId:note?.id,baseVersion:note?.version};
   answer=note?'已基于选定笔记 v'+note.version+' 提出补充建议。请核对原文与建议，确认后保存为新版本。':'已整理一份复习笔记建议，请先预览再确认保存。';
  }else if(/练习|补强|学情|复习/.test(text)){
   const ids=match?Q.filter(q=>q.point===match.point).map(q=>q.id):[1,5];
   answer='当前证据不足以估计完整 408 成绩。可先复习'+(match?.point||'折半查找与排序稳定性')+'，再完成对应的补强练习；题目不足时保持实际数量。';
   S.action={type:'PRACTICE',status:'PENDING',ids};
  }else if(match){
   answer=(context.includes('错题')?'这次作答的标准答案和判分保持不变。':'')+match.analysis+'\n请复述关键概念，并比较各个选项。';
  }else{
   answer='当前演示仅覆盖折半查找、信号量、TCP 可靠传输、程序计数器与排序稳定性。这个问题缺少可核对的资料，暂不生成结论；可以补充知识点或选择现有练习。';
  }
  const allowed=S.model&&(!context.includes('错题')||S.scopes.includes('错题'))&&(!context.includes('学习统计')||S.scopes.includes('学情画像'))&&(!note||S.scopes.includes('个人笔记'));
  S.chat.push({role:'assistant',text:answer,mode:allowed?'模拟模型解释':'本地规则说明'});renderAssistant();
 },750);
}
function privacy(){modal('考研助手隐私设置',`<p>接收服务：演示服务（本原型不会发送真实请求）。本轮提问和必要历史仅用于页面演示。</p><label><input type="checkbox" id="privacy-model" ${S.model?'checked':''}>允许调用外部模型（模拟）</label><h4>允许使用的私人记录类别</h4>${['备考档案','作答记录','错题','收藏','学情画像','个人笔记'].map(x=>`<label><input type="checkbox" name="privacy-scope" value="${x}" ${S.scopes.includes(x)?'checked':''}>${x}</label>`).join('')}<p class="proto-muted">个人笔记仍需逐份选择。关闭类别后不再外发该类历史；已发送数据无法追溯收回。正式助手记录保留规则以现有实现为准。</p>`,btn('关闭','close')+btn('保存隐私设置','save-privacy','primary'))}
function notePreview(){const v=$('#note-body')?.value||'';const e=$('#note-preview');if(e)e.innerHTML=markdown(v)}
function currentNote(){return S.notes.find(n=>n.id===S.noteId)}
function renderNotes(){const n=currentNote(),d=S.noteDraft||(n?{title:n.title,body:n.body}:null);main(page('个人笔记',`<div class="proto-note-grid"><aside class="proto-card proto-note-list">${btn('新建笔记','new-note','primary')}${S.notes.map(n=>btn(esc(n.title)+' · v'+n.version,'open-note','',`data-id="${n.id}"`)).join('')||'<p class="proto-muted">暂无个人笔记</p>'}</aside><section class="proto-card">${d?`<div class="proto-row proto-between"><h3>${n?'编辑笔记 · v'+n.version:'新建笔记'}</h3>${n?btn('历史版本','note-history'):''}</div><p id="note-save-state" class="proto-muted">${S.dirty?'有尚未保存的修改':'已保存版本'}</p><div class="proto-fields">${field('笔记标题','note-title',d.title,'text',true)}<label class="proto-field wide">Markdown 正文<textarea id="note-body" rows="10">${esc(d.body)}</textarea></label></div><h4>正文预览</h4><div class="proto-preview" id="note-preview">${markdown(d.body)}</div><div class="proto-actions">${btn('保存新版本','save-note','primary')}${n?btn('让助手修改','ask-note'):''}${n?btn('演示版本冲突','note-conflict'):''}</div>`:'<p class="proto-muted">选择一份笔记，或新建笔记。</p>'}</section></div>`,'手动编辑或让助手提出建议；确认后保存新版本'))}
function renderSchools(){const schools=['示例大学 A','示例大学 B'].filter(x=>!S.schoolFilter||x.includes(S.schoolFilter));main(page('院校库',notice('以下院校名称、招生条件和指标均为演示，不是真实招生信息。年份、专业和统计口径应逐项核对。','warn')+card(`<div class="proto-row"><input id="school-query" class="proto-input" style="max-width:300px" placeholder="搜索院校名称" value="${esc(S.schoolFilter)}">${btn('搜索院校库','search-school','primary')}${btn('条件推荐','recommend-schools')}${goBtn('维护报考档案','profile')}</div>`)+`<div class="proto-grid two">${schools.map(n=>`<button class="proto-tile" data-act="school-detail" data-id="${n.endsWith('A')?1:2}"><div class="proto-schoolletter">${n.slice(-1)}</div><b>${n}</b><p>示例省 · 层次未登记</p><small>查看专业、年份与数据口径 →</small></button>`).join('')||notice('当前条件没有匹配院校，可清空搜索条件重试。')}</div>`,'按明确条件比较候选，逐条核对来源依据'))}
function renderSchoolDetail(){main(page('院校详情',goBtn('← 返回院校库','schools')+notice('招生计划、年份与来源需逐项核对。缺失值不代表零；往年复试线不代表当年分数线。','warn')+card(`<div class="proto-row"><div class="proto-schoolletter">${S.schoolId===1?'A':'B'}</div><div><h3>示例大学 ${S.schoolId===1?'A':'B'}</h3><p class="proto-muted">示例省 · 层次未登记</p></div></div>`)+card(`<h3>招生专业信息</h3><table class="proto-table"><tr><th>专业</th><th>专业代码</th><th>年份</th><th>学院／方式</th><th>招生计划</th><th>往年参考线</th></tr><tr><td>计算机科学与技术</td><td>081200</td><td>2027</td><td>示例学院／全日制</td><td>待核实</td><td>未登记</td></tr></table><p>备注：原型演示资料，不用于报考决策。来源尚未登记，不提供虚构官方链接。</p>`),'院校列表 → 详情 → 返回列表'))}
function renderDocuments(){const docs=[{title:'示例资料：数据结构复习要点',subject:'数据结构',content:'有序顺序表可使用折半查找。每次比较将查找区间减半，最坏时间复杂度为 O(log n)。'},{title:'示例资料：操作系统进程管理',subject:'操作系统',content:'并发进程需要同步与互斥。P、V 操作应以原子方式执行，以避免对共享计数状态的竞争。'}];main(page('备考资料',card(`<div class="proto-row"><select class="proto-input" style="max-width:220px" id="document-subject"><option value="">全部科目</option>${['数据结构','操作系统'].map(v=>`<option ${S.documentFilter===v?'selected':''}>${v}</option>`).join('')}</select>${btn('筛选资料','filter-documents')}</div>`)+docs.filter(d=>!S.documentFilter||d.subject===S.documentFilter).map(d=>card(`${tag(d.subject)}<h3 style="margin-top:12px">${d.title}</h3><p>示例内容 · 平台已发布的复习资料</p>${btn('阅读正文','read-document','primary',`data-subject="${d.subject}"`)}<span class="proto-muted" style="margin-left:14px">来源链接未登记</span>`)).join(''),'按科目查找已发布资料，阅读时核对来源与版本'))}
function renderQuestions(){main(page('题目录入与审核',`<div class="proto-row">${btn('录入题目','question-entry','primary')}${btn('批量导入','question-batch')}</div>`+notice('录入或整批送审后进入待审核；只有审核通过的题目才能进入正式学生题池。本页使用模拟审核记录。')+card(`<h3>题目列表（${S.questions.length}）</h3>${S.questions.length?`<table class="proto-table"><tr><th>ID／版本</th><th>题干</th><th>状态</th><th>操作</th></tr>${S.questions.map(q=>`<tr><td>#${q.id} · v${q.version}</td><td>${esc(q.content)}</td><td>${tag({PENDING_REVIEW:'待审核',APPROVED:'审核通过',REJECTED:'已驳回'}[q.status],q.status==='APPROVED'?'good':q.status==='REJECTED'?'bad':'warn')}</td><td>${btn('查看与审核','review-question','small',`data-id="${q.id}"`)}</td></tr>`).join('')}</table>`:'<p class="proto-muted">暂无待审核题目。可以录入或批量导入。</p>'}`),'核对题目、来源与使用权限后再发布'))}
function questionEntry(id){const q=S.questions.find(q=>q.id===Number(id));S.editQuestionId=q?.id||null;modal(q?'修改未发布题目':'录入单选题',`<div class="proto-fields"><label class="proto-field">科目<select id="q-subject">${['数据结构','操作系统','计算机网络','计算机组成原理'].map(x=>`<option ${q?.subject===x?'selected':''}>${x}</option>`).join('')}</select></label><label class="proto-field">难度<select id="q-difficulty">${['中等','简单','困难'].map(v=>`<option ${q?.difficulty===v?'selected':''}>${v}</option>`).join('')}</select></label>${field('知识点','q-point',q?.point||'折半查找','text',true)}${field('题干','q-content',q?.content||Q[0].q,'text',true)}${Q[0].options.map((v,n)=>field('选项 '+'ABCD'[n],'q-option'+n,q?.options?.[n]||v)).join('')}<label class="proto-field">标准答案<select id="q-answer">${['A','B','C','D'].map(x=>`<option ${x===(q?.answer||'B')?'selected':''}>${x}</option>`).join('')}</select></label><label class="proto-field">来源类别<select id="q-source-type"><option value="ORIGINAL" ${q?.sourceType!=='REAL_EXAM'?'selected':''}>自编题</option><option value="REAL_EXAM" ${q?.sourceType==='REAL_EXAM'?'selected':''}>真题</option></select></label>${field('解析','q-analysis',q?.analysis||Q[0].analysis,'text',true)}${field('来源名称','q-source',q?.source||'408 小组自编演示题')}${field('来源定位','q-locator',q?.locator||'原型自编题第 1 题')}${field('年份（真题必填）','q-year',q?.year||'','number')}${field('原题号（真题必填）','q-number',q?.number||'')}${field('使用权限说明','q-permission',q?.permission||'小组自编，仅用于课程原型演示','text',true)}</div>`,btn('取消录入','close')+btn('保存并送审','save-question','primary'))}
function batchEntry(){S.batch=null;modal('批量导入题目',`<p>每批 1—50 道单选题，先校验预览，再整批送审。演示输入不写入正式题库。</p>${btn('填入自编题示例','fill-batch')}<label class="proto-field" style="margin-top:14px">题目 JSON<textarea id="batch-json" rows="10" class="proto-code" placeholder='{"questions":[...]}'></textarea></label><div id="batch-preview"></div>`,btn('关闭','close')+btn('校验并预览','preview-batch')+btn('确认整批送审','submit-batch','primary','id="submit-batch" disabled'))}
function reviewQuestion(id){const q=S.questions.find(q=>q.id===id);S.reviewId=id;modal('题目 #'+id+' · v'+q.version,`${tag(q.status==='PENDING_REVIEW'?'待审核':q.status==='APPROVED'?'审核通过':'已驳回')}<h4>${esc(q.content)}</h4>${q.options.map((o,i)=>`<p>${'ABCD'[i]}. ${esc(o)}</p>`).join('')}<p>标准答案 ${q.answer} · ${esc(q.analysis)}</p><p>来源：${esc(q.source)}<br>定位：${esc(q.locator)}<br>权限：${esc(q.permission)}</p>${q.comment?notice('审核意见：'+esc(q.comment),'warn'):''}<label class="proto-field">审核意见<textarea id="review-comment" rows="2" placeholder="驳回时必填"></textarea></label>`,btn('关闭','close')+(q.status==='PENDING_REVIEW'?btn('补充／修改','question-entry','',`data-id="${id}"`)+btn('驳回题目','reject-question','danger')+btn('审核通过','approve-question','primary'):q.status==='REJECTED'?btn('修改后重新送审','question-entry','primary',`data-id="${id}"`):''))}
function renderAdminDocuments(){main(page('资料审核',notice('审核前请核对资料内容、科目和使用权限；确认后更新发布状态。')+card(`<table class="proto-table"><tr><th>标题</th><th>科目</th><th>状态</th><th>操作</th></tr>${S.documents.map(d=>`<tr><td>${d.title}</td><td>${d.subject}</td><td>${tag({PENDING:'待审核',PUBLISHED:'已发布',REJECTED:'已拒绝'}[d.status],d.status==='PUBLISHED'?'good':d.status==='REJECTED'?'bad':'warn')}</td><td>${btn('通过','approve-document','small',`data-id="${d.id}" ${d.status!=='PENDING'?'disabled':''}`)} ${btn('拒绝','reject-document','small danger',`data-id="${d.id}" ${d.status!=='PENDING'?'disabled':''}`)}</td></tr>`).join('')}</table>`),'后台管理资料 · 模拟状态'))}
function clickAction(act,e){
 switch(act){
 case 'close':close();break;
 case 'page-rules':showRules();break;
 case 'logout':S.role='STUDENT';navigate('login');break;
 case 'reset':location.reload();break;
 case 'admin-demo':S.role='ADMIN';navigate(e.dataset.target||'admin-questions');break;
 case 'leave-note':S.dirty=false;S.noteDraft=null;navigate(e.dataset.target,true);break;
 case 'save-profile':{const y=Number($('#p-year').value);if(!Number.isInteger(y)||y<2020||y>2100){toast('请填写有效的考试年份');break}S.profile={school:$('#p-school').value,major:$('#p-major').value,year:y,degree:$('#p-degree').value,background:$('#p-background').value};toast('档案已保存（本次演示）');break}
 case 'start-practice':{const count=Number($('#cfg-count').value);if(!Number.isInteger(count)||count<1||count>50){toast('题量必须为 1—50 的整数');break}S.cfg={source:$('#cfg-source').value,subject:$('#cfg-subject').value,difficulty:$('#cfg-difficulty').value,count};startSession();break}
 case 'start-diagnostic':startSession(true);break;
 case 'choose':if(!current().submitted&&S.session.state==='RUNNING'){current().user=e.dataset.value;renderSession()}break;
 case 'submit-item':submitItem();break;
 case 'move-item':case 'review-item':S.session.index=Number(e.dataset.index);if(act==='review-item')navigate('practice-session');else renderSession();break;
 case 'next-item':S.session.index=Math.min(S.session.index+1,S.session.items.length-1);renderSession();break;
 case 'hint':current().hint=Math.min(2,current().hint+1);renderSession();break;
 case 'ask-finish':modal('结束批次','<p>结束后不能继续作答。未提交选择不计作答，未答不计错题。</p>',btn('继续作答','close')+btn('结束并查看结果','finish','primary'));break;
 case 'finish':close();finishSession();break;
 case 'open-session':S.session=S.sessions[Number(e.dataset.index)];navigate('result');break;
 case 'toggle-favorite':{const id=Number(e.dataset.id);if(S.favorite.has(id))S.favorite.delete(id);else S.favorite.add(id);render();toast(S.favorite.has(id)?'已收藏':'已取消收藏');break}
 case 'ask-remove-wrong':modal('移出错题','<p>仅移除本次演示中的错题标记，历史判分仍保留。</p>',btn('取消','close')+btn('确认移出','remove-wrong','danger',`data-id="${e.dataset.id}"`));break;
 case 'remove-wrong':S.wrong.delete(Number(e.dataset.id));close();renderMarks();toast('已移出错题标记');break;
 case 'practice-marks':startSession(false,true,Array.from(S.route==='wrong'?S.wrong:S.favorite));break;
 case 'tutor':S.generation++;S.generating=false;S.contextNote=null;S.context='已判分错题 #'+e.dataset.id+' · '+Q.find(q=>q.id===Number(e.dataset.id)).point;S.chat=[];S.action=null;navigate('assistant');break;
 case 'analyze-study':S.contextNote=null;S.context='学习统计 · 薄弱知识点与独立样本';navigate('assistant');sendChat('请分析我的学情，并安排补强练习');break;
 case 'example-profile':S.profileReady=true;renderStats();break;
 case 'refresh-profile':S.profileReady=S.profileReady||S.sessions.length>0;renderStats();toast('已刷新模拟画像');break;
 case 'export-report':{const text='考研 Agent 模拟学情报告\n全部为原型演示数据，非学习效果评估。\n'+JSON.stringify(S.sessions.map(s=>metrics(s)),null,2);const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));a.download='模拟学情报告.txt';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);toast('已导出模拟报告');break}
 case 'new-chat':S.generation++;S.generating=false;S.chat=[];S.context='';S.contextNote=null;S.action=null;renderAssistant();break;
 case 'privacy':privacy();break;
 case 'save-privacy':S.model=$('#privacy-model').checked;S.scopes=$$('input[name=privacy-scope]:checked').map(e=>e.value);S.generation++;S.generating=false;close();renderAssistant();toast('隐私设置已模拟保存');break;
 case 'prompt-study':sendChat('分析学情并安排复习');break;
 case 'prompt-practice':sendChat('安排折半查找补强练习');break;
 case 'prompt-note':sendChat('整理一份折半查找复习笔记');break;
 case 'send-chat':sendChat();break;
 case 'stop-generation':S.generation++;S.generating=false;S.chat.push({role:'assistant',text:'已停止生成，未创建练习或修改笔记。',mode:'已停止'});renderAssistant();break;
 case 'simulate-failure':sendChat('演示一次生成失败',true);break;
 case 'retry-chat':sendChat(S.lastFailed||'请说明折半查找');break;
 case 'cancel-action':S.action.status='CANCELLED';renderAssistant();break;
 case 'confirm-action':{
  const a=S.action;if(!a||a.status!=='PENDING')break;
  if(a.type==='NOTE'){
   S.proposal=a.text;const n=a.noteId?S.notes.find(n=>n.id===a.noteId):null;
   modal('预览笔记建议',`<p>${n?'针对「'+esc(n.title)+'」v'+a.baseVersion+' 的建议，确认后保存新版本。':'确认后创建一份新笔记。'}</p>${n?'<details><summary>查看原文</summary><pre>'+esc(n.body)+'</pre></details>':''}<div class="proto-preview">${markdown(a.text)}</div>`,btn('返回继续核对','close')+btn('确认保存建议','save-proposal','primary'));
  }else if(startSession(false,false,a.ids)){a.status='SUCCESS';a.session=S.session;renderAssistant()}
  break;
 }
 case 'enter-action':S.session=S.action.session;navigate('practice-session');break;
 case 'save-proposal':{
  const a=S.action;if(!a||a.status!=='PENDING')break;
  let n=a.noteId?S.notes.find(n=>n.id===a.noteId):null;
  if(a.noteId&&(!n||n.version!==a.baseVersion)){modal('笔记版本已变化',notice('未覆盖原笔记。请重新选择最新版本，再让助手提出建议。','warn'));break}
  if(n){n.versions.push({version:n.version,title:n.title,body:n.body});n.version++;n.body=a.text}
  else{n={id:Date.now(),title:a.title,body:a.text,version:1,versions:[]};S.notes.push(n)}
  S.noteId=n.id;S.noteDraft=null;S.dirty=false;a.status='SUCCESS';close();renderAssistant();toast('笔记建议已保存为 v'+n.version);break;
 }

 case 'new-note':if(S.dirty){modal('存在未保存修改','<p>请先保存当前笔记，或通过导航离开并确认放弃修改。</p>');break}S.noteId=null;S.noteDraft={title:'',body:''};S.dirty=false;renderNotes();break;
 case 'open-note':if(S.dirty){modal('存在未保存修改','<p>请先保存或通过导航离开并确认放弃修改。</p>');break}S.noteId=Number(e.dataset.id);S.noteDraft=null;renderNotes();break;
 case 'save-note':{const title=$('#note-title').value.trim(),body=$('#note-body').value;if(!title){toast('请填写笔记标题');break}let n=currentNote();if(n){n.versions.push({version:n.version,title:n.title,body:n.body});n.version++;n.title=title;n.body=body}else{n={id:Date.now(),title,body,version:1,versions:[]};S.notes.push(n);S.noteId=n.id}S.noteDraft=null;S.dirty=false;renderNotes();toast('笔记已保存为 v'+n.version);break}
 case 'note-history':{const n=currentNote();modal('笔记历史版本（只读）',[...n.versions,{version:n.version,title:n.title,body:n.body}].map(v=>`<details><summary>v${v.version} · ${esc(v.title)}</summary><pre>${esc(v.body)}</pre></details>`).join(''));break}
 case 'ask-note':if(S.dirty){toast('请先保存修改，助手只读取已保存版本');break}S.contextNote={...currentNote()};S.context='个人笔记 · '+currentNote().title+' · v'+currentNote().version;navigate('assistant');sendChat('请帮助整理当前笔记');break;
 case 'note-conflict':modal('笔记版本冲突',notice('笔记已有新版本。你的编辑内容已保留，请重新读取并核对后保存。','warn'),btn('保留当前编辑','close')+btn('读取已保存版本','reload-note','primary'));break;
 case 'reload-note':S.noteDraft=null;S.dirty=false;close();renderNotes();break;
 case 'search-school':S.schoolFilter=$('#school-query').value.trim();renderSchools();break;
 case 'school-detail':S.schoolId=Number(e.dataset.id);navigate('school-detail');break;
 case 'recommend-schools':modal('条件推荐',`<p>当前档案：${S.profile.year} 年 · ${esc(S.profile.major)} · ${S.profile.degree==='academic'?'学硕':'专硕'}</p>${notice('本原型不生成真实院校推荐。演示候选仅用于检查“条件 → 候选 → 详情”的操作路径。','warn')}`,btn('取消','close')+btn('查看演示候选','show-recommendations','primary'));break;
 case 'show-recommendations':close();toast('已展示示例候选，请点击院校卡片查看详情');break;
 case 'filter-documents':S.documentFilter=$('#document-subject').value;renderDocuments();break;
 case 'read-document':modal(e.dataset.subject+' · 示例资料',`<p>平台已发布资料 · 来源链接未登记</p><h4>复习要点</h4><p>${e.dataset.subject==='数据结构'?esc(Q[0].analysis):esc(Q[1].analysis)}</p>${notice('以上为自编演示摘要，引用与原文位置需在正式资料中登记。')}`);break;
 case 'question-entry':questionEntry(e.dataset.id);break;
 case 'save-question':{const get=id=>$('#'+id).value.trim();const opts=[0,1,2,3].map(i=>get('q-option'+i));const real=get('q-source-type')==='REAL_EXAM';if(real&&(!Number.isInteger(Number(get('q-year')))||Number(get('q-year'))<1900||Number(get('q-year'))>2100)){toast('真题年份应为 1900—2100 的整数');break}if(!get('q-content')||opts.some(x=>!x)||!get('q-analysis')||!get('q-source')||!get('q-locator')||!get('q-permission')||!get('q-point')||(real&&(!get('q-year')||!get('q-number')))){toast('请补齐题目、来源和使用权限；真题需填写年份与原题号');break}let q=S.questions.find(q=>q.id===S.editQuestionId);const data={subject:get('q-subject'),point:get('q-point'),content:get('q-content'),options:opts,answer:get('q-answer'),analysis:get('q-analysis'),source:get('q-source'),locator:get('q-locator'),permission:get('q-permission'),year:get('q-year'),number:get('q-number'),sourceType:get('q-source-type'),difficulty:get('q-difficulty'),status:'PENDING_REVIEW',comment:''};if(q)Object.assign(q,data,{version:q.version+1});else S.questions.push({...data,id:101+S.questions.length,version:1});close();renderQuestions();toast('已保存并送审，尚未发布');break}
 case 'question-batch':batchEntry();break;
 case 'fill-batch':$('#batch-json').value=JSON.stringify({questions:Q.slice(0,2).map(q=>({subject:q.subject,knowledgePoint:q.point,content:q.q,optionA:q.options[0],optionB:q.options[1],optionC:q.options[2],optionD:q.options[3],answer:q.answer,analysis:q.analysis,difficulty:'MEDIUM',sourceType:'ORIGINAL',sourceName:'408 小组自编演示题',sourceLocator:'原型自编题第 '+q.id+' 题',permissionNote:'小组自编，仅用于课程原型演示'}))},null,2);S.batch=null;$('#submit-batch').disabled=true;break;
 case 'preview-batch':{try{const raw=$('#batch-json').value;if(new Blob([raw]).size>2*1024*1024)throw Error('输入超过 2 MiB');const data=JSON.parse(raw).questions;if(!Array.isArray(data)||data.length<1||data.length>50)throw Error('每批应包含 1—50 道题');data.forEach((q,n)=>{for(const k of ['subject','knowledgePoint','content','optionA','optionB','optionC','optionD','answer','analysis','sourceName','sourceLocator','permissionNote'])if(typeof q[k]!=='string'||!q[k].trim())throw Error('第 '+(n+1)+' 题缺少 '+k);if(!/^[A-D]$/.test(q.answer))throw Error('答案必须为 A—D');if(q.sourceType==='REAL_EXAM'&&(!q.sourceYear||!q.sourceQuestionNo))throw Error('真题需登记年份与原题号')});S.batch={raw,data};$('#batch-preview').innerHTML=notice('已预览 '+data.length+' 道题，尚未写入题库。')+data.map(q=>`<details><summary>${esc(q.content)}</summary><p>标准答案 ${q.answer} · ${esc(q.analysis)}</p><p>来源 ${esc(q.sourceName)} · ${esc(q.permissionNote)}</p></details>`).join('');$('#submit-batch').disabled=false}catch(err){S.batch=null;$('#submit-batch').disabled=true;$('#batch-preview').innerHTML=notice(esc(err.message),'error')}break}
 case 'submit-batch':if(!S.batch||S.batch.raw!==$('#batch-json').value){toast('内容已变化，请重新校验预览');break}S.batch.data.forEach(q=>S.questions.push({id:101+S.questions.length,version:1,subject:q.subject,point:q.knowledgePoint,content:q.content,options:[q.optionA,q.optionB,q.optionC,q.optionD],answer:q.answer,analysis:q.analysis,source:q.sourceName,locator:q.sourceLocator,permission:q.permissionNote,sourceType:q.sourceType,year:q.sourceYear||'',number:q.sourceQuestionNo||'',difficulty:({EASY:'简单',MEDIUM:'中等',HARD:'困难'}[q.difficulty]||'中等'),status:'PENDING_REVIEW',comment:''}));close();renderQuestions();toast('整批送审成功，所有题目等待审核');break;
 case 'review-question':reviewQuestion(Number(e.dataset.id));break;
 case 'approve-question':case 'reject-question':{const comment=$('#review-comment').value.trim();if(act==='reject-question'&&!comment){toast('驳回需填写审核意见');break}const q=S.questions.find(q=>q.id===S.reviewId);q.status=act==='approve-question'?'APPROVED':'REJECTED';q.comment=comment;close();renderQuestions();toast(q.status==='APPROVED'?'审核通过（模拟）':'题目已驳回');break}
 case 'approve-document':case 'reject-document':{const d=S.documents.find(d=>d.id===Number(e.dataset.id));if(d.status!=='PENDING')break;S.documentReview={id:d.id,status:act==='approve-document'?'PUBLISHED':'REJECTED'};modal('确认资料审核',`<p>资料：${esc(d.title)}</p><p>确认${act==='approve-document'?'通过并发布':'拒绝发布'}这份资料？</p>`,btn('取消','close')+btn('确认审核','confirm-document','primary'));break}
 case 'confirm-document':{const d=S.documents.find(d=>d.id===S.documentReview.id);if(d.status==='PENDING')d.status=S.documentReview.status;close();renderAdminDocuments();toast('资料审核状态已更新（模拟）');break}
 }
}
document.addEventListener('click',ev=>{
 const action=ev.target.closest('[data-act]');if(action){ev.preventDefault();clickAction(action.dataset.act,action);return}
 const go=ev.target.closest('[data-go]');if(go){ev.preventDefault();navigate(go.dataset.go);return}
 const a=ev.target.closest('a');if(a){ev.preventDefault();const href=a.getAttribute('href')||'';let path=href.split('/').pop().replace('.html','');if(href.includes('/schools/')){S.schoolId=Number(path)||1;path='school-detail'}if(href.includes('tasks/history'))path='history';if(path==='tasks')path='assistant';if(LABELS[path])navigate(path);else toast('该来源未登记；本原型不打开未核实链接');return}
 const b=ev.target.closest('button');if(b){const t=b.textContent.replace(/\s/g,'');if(t==='登录'||t==='注册'){const inputs=$$('main input');const user=inputs[0]?.value.trim(),password=inputs[1]?.value;if(!user||!password){toast('请填写用户名和演示密码');return}if(t==='注册'&&(user.length<3||user.length>64||password.length<6||password.length>32||password!==inputs[2]?.value)){toast('用户名 3—64 位；密码 6—32 位且两次输入相同');return}S.role='STUDENT';navigate('home');toast(t==='注册'?'模拟注册成功，已进入学生首页':'模拟登录成功');return}if(t==='开始单选诊断'){startSession(true);return}if(t==='暂时跳过'){b.closest('.diagnosis')?.remove();return}if(t==='个人笔记'){navigate('notes');return}}
});
document.addEventListener('input',ev=>{if(['note-title','note-body'].includes(ev.target.id)){S.dirty=true;S.noteDraft={title:$('#note-title').value,body:$('#note-body').value};$('#note-save-state').textContent='有尚未保存的修改';notePreview()}if(ev.target.id==='batch-json'){S.batch=null;const b=$('#submit-batch');if(b)b.disabled=true}});
document.addEventListener('keydown',ev=>{if(ev.key==='Enter'&&!ev.shiftKey&&ev.target.id==='chat-input'){ev.preventDefault();sendChat()}if(ev.key==='Escape')close()});
document.addEventListener('submit',ev=>ev.preventDefault());
S.route=INITIAL_ROUTE;
if(INITIAL_ROUTE.startsWith('admin-'))S.role='ADMIN';
render();
