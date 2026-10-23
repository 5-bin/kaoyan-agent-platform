// Only synthetic accounts on the loopback smoke server; never log tokens or request bodies.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const base = process.argv[2];
assert.equal(new URL(base).hostname, '127.0.0.1');
(async () => {
  const browser = await chromium.launch({ headless: true,
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || process.env.CHROME_PATH });
  const checks = [];
  try {
    for (const width of [1280, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      try {
        const page = await context.newPage();
        async function api(path, token, method = 'GET', data, expected = 200) {
          const response = await context.request.fetch(base + '/api' + path,
            { method, data, headers: token ? { Authorization: `Bearer ${token}` } : {} });
          assert.equal(response.status(), expected, method + ' ' + path);
          return (await response.json()).data;
        }
        async function login(name) {
          return (await api('/auth/login', '', 'POST', { username: name, password: 'test-only-question-password' })).accessToken;
        }
        await page.goto(base + '/admin/questions');
        await page.getByPlaceholder('用户名', { exact: true }).fill('question_admin');
        await page.getByPlaceholder('密码', { exact: true }).fill('test-only-question-password');
        await page.getByRole('button', { name: /登\s*录/ }).click();
        await page.getByRole('button', { name: '录入题目', exact: true }).waitFor();
        const admin = await page.evaluate(() => localStorage.getItem('token'));
        const reviewer = await login('question_reviewer');
        const student = await login('question_student');
        const entry = { subject: '数据结构', difficulty: 'EASY', knowledgePoint: 'smoke-admin-' + width,
          content: '自编联调题：栈的出栈顺序是什么？', optionA: '先进先出', optionB: '后进先出', optionC: '随机', optionD: '按大小',
          answer: 'B', analysis: '栈在栈顶操作，后入先出。', sourceType: 'ORIGINAL',
          sourceName: '隔离浏览器自编验证', sourceLocator: 'browser-question-admin.cjs',
          sourceQuestionNo: '', permissionNote: '工程自编夹具，仅用于联调。' };
        await page.getByRole('button', { name: '录入题目', exact: true }).click();
        await page.getByLabel('难度', { exact: true }).selectOption(entry.difficulty);
        await page.getByLabel('标准答案', { exact: true }).selectOption(entry.answer);
        for (const [label, field] of Object.entries({ '知识点': 'knowledgePoint', '题干': 'content', '选项A': 'optionA',
          '选项B': 'optionB', '选项C': 'optionC', '选项D': 'optionD', '解析': 'analysis',
          '来源名称／试卷名称': 'sourceName', '来源定位': 'sourceLocator', '使用权限说明': 'permissionNote' }))
          await page.getByLabel(label, { exact: true }).fill(entry[field]);
        await page.getByRole('button', { name: '保存并送审' }).click();
        const heading = page.getByRole('region', { name: '题目详情' }).getByRole('heading', { level: 3 });
        await heading.waitFor();
        const id = Number((await heading.innerText()).match(/#(\d+)/)[1]);
        assert.equal((await api('/questions/practice?knowledgePoint=' + entry.knowledgePoint, student)).length, 0);
        checks.push(`${width}: 页面录题持久化，待审核不入学生题池`);
        await page.getByRole('button', { name: '补充／修改' }).click();
        await page.getByLabel('解析', { exact: true }).fill('旧页面输入的解析');
        await api('/questions/admin/' + id, reviewer, 'PUT', { ...entry, analysis: '另一管理员保存的解析', version: 1 });
        await page.getByRole('button', { name: '保存并送审' }).click();
        await page.getByRole('alert').filter({ hasText: '请先复制需要保留的输入' }).waitFor();
        assert.equal(await page.getByLabel('解析', { exact: true }).inputValue(), '旧页面输入的解析');
        assert.equal(await page.getByRole('button', { name: '保存并送审' }).isDisabled(), true);
        assert.equal((await api('/questions/admin/' + id, admin)).analysis, '另一管理员保存的解析');
        await page.getByRole('button', { name: '取消录入' }).click();
        await page.getByRole('button', { name: '刷新详情' }).click();
        await page.getByRole('heading', { name: `题目 #${id} · 版本 2` }).waitFor();
        await page.getByRole('button', { name: '补充／修改' }).click();
        await page.getByLabel('解析', { exact: true }).fill('核对后保存的最终解析');
        await page.getByRole('button', { name: '保存并送审' }).click();
        await page.getByRole('heading', { name: `题目 #${id} · 版本 3` }).waitFor();
        checks.push(`${width}: 真实409保留旧输入，显式刷新后使用新版本保存`);
        await page.getByLabel('审核意见（驳回必填）').fill('核对自编记录后通过');
        await page.getByRole('button', { name: '审核通过', exact: true }).click();
        await page.getByRole('heading', { name: `题目 #${id} · 版本 4` }).waitFor();
        const approved = await api('/questions/admin/' + id, admin);
        const first = (await api('/practice/sessions', student, 'POST', { subject: '数据结构', count: 1, questionIds: [id] })).sessionId;
        await api(`/practice/sessions/${first}/answer`, student, 'POST', { questionId: id, answer: 'A' });
        const historical = (await api(`/practice/sessions/${first}/review`, student)).list.find(q => q.questionId === id);
        const second = (await api('/practice/sessions', student, 'POST', { subject: '数据结构', count: 1, questionIds: [id] })).sessionId;
        await api('/questions/admin/' + id + '/active', student, 'PUT', { active: 0, version: 4 }, 403);
        checks.push(`${width}: 页面审核后可判分，学生不能调用启停接口`);
        async function toggle(name, version) {
          await page.getByRole('button', { name, exact: true }).click();
          await page.getByRole('button', { name: '确定', exact: true }).click();
          await page.getByRole('heading', { name: `题目 #${id} · 版本 ${version}` }).waitFor();
        }
        await toggle('停用题目', 5);
        assert.equal((await api('/questions/practice?knowledgePoint=' + entry.knowledgePoint, student)).length, 0);
        await api(`/practice/sessions/${second}/answer`, student, 'POST', { questionId: id, answer: 'B' }, 409);
        assert.deepEqual((await api(`/practice/sessions/${first}/review`, student)).list.find(q => q.questionId === id), historical);
        checks.push(`${width}: 页面停用阻止抽题与未答提交，已答历史保持一致`);
        await toggle('重新启用', 6);
        assert.equal((await api('/questions/practice?knowledgePoint=' + entry.knowledgePoint, student)).length, 1);
        await api(`/practice/sessions/${second}/answer`, student, 'POST', { questionId: id, answer: 'B' });
        const restored = await api('/questions/admin/' + id, admin);
        for (const field of ['content', 'answer', 'analysis', 'sourceType', 'sourceName', 'sourceLocator', 'permissionNote',
          'reviewStatus', 'reviewerUserId', 'reviewedAt', 'reviewComment']) assert.deepEqual(restored[field], approved[field]);
        assert.deepEqual((await api(`/practice/sessions/${first}/review`, student)).list.find(q => q.questionId === id), historical);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        checks.push(`${width}: 页面恢复后可继续判分，来源、审核及旧快照保留，无横向溢出`);
      } finally { await context.close(); }
    }
    process.stdout.write(JSON.stringify({ checks, passed: true, backend: 'isolated H2 and Redis double',
      viewports: [1280, 390], realDevice: false, paidModelCalls: false }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error.name + ': ' + error.message); process.exit(1); });
