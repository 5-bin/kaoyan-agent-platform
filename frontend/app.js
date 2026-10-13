import { request } from "./js/api.js";
"use strict";

const $ = id => document.getElementById(id);
const statuses = { running: "处理中", completed: "已完成", needs_input: "需补充信息", unsupported: "资料未覆盖", failed: "执行失败" };
let token = sessionStorage.getItem("kaoyan_token") || "";
let currentUser = null;
let epoch = 0, selection = 0, historyVersion = 0, page = 0, pages = 0, busy = false;
let practiceSession = null, practiceItem = null, practiceIndex = 0, savingDraft = false;

const subjectNames = { data_structure: "数据结构", computer_organization: "计算机组成原理", operating_system: "操作系统", computer_network: "计算机网络" };
const modeNames = { chapter: "章节练习", random: "随机练习", wrong: "错题重练", favorite: "收藏练习" };

function message(text = "") { $("message").textContent = text; }
function api(path, options = {}) { return request(path, { ...options, token }); }

function setBusy(value) { busy = value; $("submit-task").disabled = value; $("example").disabled = value; $("progress").hidden = !value; }
function resetResult() {
  $("result-status").textContent = "等待提交"; $("result-meta").textContent = "";
  $("result-answer").textContent = "提交任务后，处理结果将在这里显示。";
  for (const id of ["steps", "followup", "sources"]) { $(`${id}-section`).hidden = true; $(`result-${id}`).replaceChildren(); }
}
function showUser(user) {
  currentUser = user;
  $("auth-panel").hidden = Boolean(user); $("workspace").hidden = !user; $("user-bar").hidden = !user;
  $("username").textContent = user?.username || "";
  $("admin-link").hidden = user?.role !== "admin";
  renderRoute();
}
function clearSession() {
  epoch++; selection++; historyVersion++; token = ""; sessionStorage.removeItem("kaoyan_token");
  page = 0; pages = 0; practiceSession = null; practiceItem = null; setBusy(false); showUser(null); resetResult();
  $("history-items").replaceChildren(); $("session-list").replaceChildren(); $("wrong-items").replaceChildren();
  $("task-input").value = ""; $("task-subject").value = "";
}
function handleError(error) { if (error.status === 401) clearSession(); message(error.message); }
function listText(id, items) {
  const target = $(id); target.replaceChildren();
  for (const item of items || []) { const li = document.createElement("li"); li.textContent = item; target.append(li); }
}
function safeSourceUrl(value) {
  try {
    const url = new URL(value, location.origin);
    if (url.protocol === "https:" || (url.origin === location.origin && url.pathname.startsWith("/references/"))) return url.href;
  } catch { /* 仅展示无法验证的链接文字。 */ }
  return null;
}
function showResult(task) {
  $("result-status").textContent = statuses[task.status] || "未知状态";
  const result = task.result;
  $("result-meta").textContent = `任务 ${task.id} · ${result ? (result.mode === "model" ? "模型模式" : result.mode === "demo" ? "离线演示" : "模式未知") : "等待结果"}${result ? ` · ${result.latencyMs} ms` : ""}`;
  $("result-answer").textContent = result?.answer || "任务正在处理，请稍后刷新记录。";
  listText("result-steps", result?.steps); listText("result-followup", result?.followUp);
  $("steps-section").hidden = !result?.steps?.length; $("followup-section").hidden = !result?.followUp?.length;
  $("sources-section").hidden = !result?.sources?.length; $("result-sources").replaceChildren();
  for (const source of result?.sources || []) {
    const box = document.createElement("div"); box.className = "source";
    const url = safeSourceUrl(source.url); const title = document.createElement(url ? "a" : "strong"); title.textContent = source.title;
    if (url) { title.href = url; title.target = "_blank"; title.rel = "noopener noreferrer"; }
    const location = document.createElement("p"); location.textContent = `${source.locator} · ${source.version}`;
    const excerpt = document.createElement("p"); excerpt.textContent = source.excerpt;
    box.append(title, location, excerpt); $("result-sources").append(box);
  }
}
async function history() {
  const current = epoch, version = ++historyVersion;
  const data = await api(`/api/tasks?page=${page}`);
  if (current !== epoch || version !== historyVersion) return;
  pages = data.totalPages; $("history-items").replaceChildren(); $("history-empty").hidden = Boolean(data.items.length);
  for (const task of data.items) {
    const item = document.createElement("div"); item.className = "history-item";
    const content = document.createElement("div"); const text = document.createElement("p"); text.textContent = task.input.slice(0, 90);
    const meta = document.createElement("small"); meta.textContent = `${statuses[task.status] || task.status} · ${new Date(task.createdAt).toLocaleString()}`;
    content.append(text, meta); const button = document.createElement("button"); button.className = "secondary"; button.textContent = "查看结果";
    button.addEventListener("click", async () => {
      const selected = ++selection;
      try { const result = await api(`/api/tasks/${encodeURIComponent(task.id)}`); if (current === epoch && selected === selection) { showResult(result); location.hash = "knowledge"; } }
      catch (error) { if (current === epoch && selected === selection) handleError(error); }
    });
    item.append(content, button); $("history-items").append(item);
  }
  $("page-info").textContent = `第 ${pages ? page + 1 : 0} / ${pages} 页 · ${data.totalItems} 项`;
  $("prev").disabled = page === 0; $("next").disabled = page + 1 >= pages;
}

function percent(value) { return value == null ? "暂无数据" : `${(value * 100).toFixed(1)}%`; }
function metric(label, value) {
  const box = document.createElement("div"); box.className = "metric";
  const strong = document.createElement("strong"); strong.textContent = value;
  const span = document.createElement("span"); span.textContent = label;
  box.append(strong, span); return box;
}
async function loadStudySummary() {
  const current = epoch; const data = await api("/api/study/summary"); if (current !== epoch) return;
  const target = $("study-summary"); target.replaceChildren(
    metric("有效作答", data.validAttempts), metric("练习题数", data.uniqueQuestions),
    metric("正确率", percent(data.accuracy)), metric("独立正确率", percent(data.independentAccuracy)),
    metric("使用提示", data.hintsUsed)
  );
}

async function loadPracticeHome() {
  const current = epoch; const data = await api("/api/practice-sessions?status=active&page=0"); if (current !== epoch) return;
  $("session-list").replaceChildren(); $("session-empty").hidden = Boolean(data.items.length);
  for (const session of data.items) {
    const row = document.createElement("div"); row.className = "history-item";
    const text = document.createElement("div");
    const title = document.createElement("p"); title.textContent = `${modeNames[session.mode]} · ${session.actualCount}题`;
    const meta = document.createElement("small"); meta.textContent = `${session.subject ? subjectNames[session.subject] : "全部科目"} · 第${session.currentOrdinal}题`;
    const button = document.createElement("button"); button.className = "secondary"; button.textContent = "继续练习";
    button.addEventListener("click", () => openPracticeSession(session.id).catch(handleError));
    text.append(title, meta); row.append(text, button); $("session-list").append(row);
  }
}
async function createPractice(payload) {
  const session = await api("/api/practice-sessions", { method: "POST", body: JSON.stringify(payload) });
  await loadPracticeHome(); await openPracticeSession(session.id); return session;
}
async function openPracticeSession(id) {
  practiceSession = await api(`/api/practice-sessions/${encodeURIComponent(id)}`);
  practiceIndex = Math.max(0, Math.min(practiceSession.currentOrdinal - 1, practiceSession.items.length - 1));
  $("practice-workspace").hidden = false; $("practice-result").hidden = true;
  if (practiceSession.status === "completed") { await showPracticeResult(); return; }
  await openPracticeItem(practiceIndex);
}
async function openPracticeItem(index) {
  if (!practiceSession?.items?.length) return;
  practiceIndex = Math.max(0, Math.min(index, practiceSession.items.length - 1));
  const summary = practiceSession.items[practiceIndex];
  practiceItem = await api(`/api/practice-sessions/${practiceSession.id}/items/${summary.id}`);
  $("practice-title").textContent = modeNames[practiceSession.mode];
  $("practice-meta").textContent = `${practiceSession.subject ? subjectNames[practiceSession.subject] : "综合练习"} · ${practiceSession.actualCount}题`;
  $("question-point").textContent = `${subjectNames[practiceItem.subject]} · ${practiceItem.knowledgePointName}`;
  $("question-stem").textContent = practiceItem.stem; $("question-options").replaceChildren();
  for (const [key, value] of Object.entries(practiceItem.options)) {
    const label = document.createElement("label"); label.className = "option-row";
    const radio = document.createElement("input"); radio.type = "radio"; radio.name = "answer"; radio.value = key;
    radio.checked = (practiceItem.submitted ? practiceItem.selectedOption : practiceItem.selectedOptionDraft) === key;
    radio.disabled = practiceItem.submitted;
    radio.addEventListener("change", () => saveDraft().catch(handleError));
    const mark = document.createElement("strong"); mark.textContent = key;
    const text = document.createElement("span"); text.textContent = value;
    label.append(radio, mark, text); $("question-options").append(label);
  }
  $("favorite-question").textContent = practiceItem.favorite ? "取消收藏" : "收藏";
  $("question-position").textContent = `${practiceIndex + 1} / ${practiceSession.actualCount}`;
  $("previous-question").disabled = practiceIndex === 0; $("next-question").disabled = practiceIndex + 1 >= practiceSession.actualCount;
  $("submit-answer").disabled = practiceItem.submitted; $("hint-one").disabled = practiceItem.submitted;
  $("hint-two").disabled = practiceItem.submitted || practiceItem.hintLevelUsed < 1;
  $("draft-state").textContent = practiceItem.submitted ? "答案已提交，当前批次不能修改。" : (practiceItem.selectedOptionDraft ? "草稿已保存" : "选择选项后自动保存草稿");
  $("hint-content").hidden = true; $("answer-feedback").hidden = !practiceItem.submitted;
  if (practiceItem.submitted) showAnswerFeedback(); else $("answer-feedback").replaceChildren();
}
function selectedAnswer() { return document.querySelector('input[name="answer"]:checked')?.value || null; }
async function saveDraft() {
  if (!practiceSession || !practiceItem || practiceItem.submitted || savingDraft) return;
  savingDraft = true; $("draft-state").textContent = "正在保存...";
  try {
    practiceSession = await api(`/api/practice-sessions/${practiceSession.id}/progress`, { method: "PUT", body: JSON.stringify({
      expectedRevision: practiceSession.revision, currentOrdinal: practiceIndex + 1,
      drafts: [{ itemId: practiceItem.id, selectedOption: selectedAnswer() }]
    }) });
    practiceItem.selectedOptionDraft = selectedAnswer(); $("draft-state").textContent = "草稿已保存";
  } finally { savingDraft = false; }
}
function showAnswerFeedback() {
  const target = $("answer-feedback"); target.replaceChildren(); target.hidden = false;
  const title = document.createElement("strong"); title.textContent = practiceItem.correct ? "回答正确" : "回答错误";
  const explanation = document.createElement("p"); explanation.textContent = practiceItem.explanation;
  const source = document.createElement("p"); source.className = "hint"; source.textContent = `${practiceItem.sourceTitle} · ${practiceItem.sourceLocator}`;
  target.append(title, explanation, source);
}
async function requestHint(level) {
  const hint = await api(`/api/practice-sessions/${practiceSession.id}/items/${practiceItem.id}/hints`, { method: "POST", body: JSON.stringify({ level }) });
  practiceItem.hintLevelUsed = hint.hintLevelUsed; $("hint-two").disabled = hint.hintLevelUsed < 1;
  $("hint-content").hidden = false; $("hint-content").textContent = hint.available ? hint.content : "该题暂未提供此级提示。";
}
async function toggleFavorite() {
  const method = practiceItem.favorite ? "DELETE" : "PUT";
  const state = await api(`/api/favorites/${practiceItem.questionId}`, { method });
  practiceItem.favorite = state.favorite; $("favorite-question").textContent = state.favorite ? "取消收藏" : "收藏";
}
async function submitPracticeAnswer(event) {
  event.preventDefault(); const answer = selectedAnswer(); if (!answer) { message("请先选择一个答案"); return; }
  await saveDraft();
  await api("/api/attempts", { method: "POST", body: JSON.stringify({ questionId: practiceItem.questionId,
    questionVersionId: practiceItem.questionVersionId, selectedOption: answer, clientRequestId: crypto.randomUUID(),
    sessionId: practiceSession.id, sessionItemId: practiceItem.id }) });
  practiceSession = await api(`/api/practice-sessions/${practiceSession.id}`);
  await openPracticeItem(practiceIndex);
  if (practiceSession.status === "completed") await showPracticeResult();
  await loadPracticeHome();
}
async function finishPractice() {
  practiceSession = await api(`/api/practice-sessions/${practiceSession.id}/finish`, { method: "POST" });
  await showPracticeResult(); await loadPracticeHome();
}
async function showPracticeResult() {
  const data = await api(`/api/practice-sessions/${practiceSession.id}/result`);
  $("practice-workspace").hidden = true; $("practice-result").hidden = false;
  $("result-metrics").replaceChildren(metric("实际题数", data.actualCount), metric("已作答", data.answered),
    metric("未作答", data.unanswered), metric("答对", data.correct), metric("答错", data.wrong),
    metric("使用提示", data.hintsUsed), metric("正确率", percent(data.accuracy)), metric("独立正确率", percent(data.independentAccuracy)));
}
async function loadWrongQuestions() {
  const current = epoch; const data = await api("/api/wrong-questions?page=0"); if (current !== epoch) return;
  $("wrong-items").replaceChildren(); $("wrong-empty").hidden = Boolean(data.items.length);
  for (const wrong of data.items) {
    const row = document.createElement("div"); row.className = "wrong-row";
    const title = document.createElement("strong"); title.textContent = wrong.stem;
    const meta = document.createElement("p"); meta.className = "hint";
    meta.textContent = `${subjectNames[wrong.subject]} · ${wrong.knowledgePointName} · 错误${wrong.wrongCount}次 · ${wrong.status === "mastered" ? "已掌握" : `连续独立答对${wrong.consecutiveCorrect}/2`}`;
    row.append(title, meta); $("wrong-items").append(row);
  }
}
$("auth-form").addEventListener("submit", async event => {
  event.preventDefault(); const current = epoch; let activeEpoch = current; message();
  $("login").disabled = true; $("register").disabled = true;
  try {
    const action = event.submitter?.id === "register" ? "register" : "login";
    const data = await api(`/api/auth/${action}`, { method: "POST", body: JSON.stringify({ username: $("auth-name").value.trim(), password: $("auth-password").value }) });
    if (current !== epoch) return;
    token = data.token; sessionStorage.setItem("kaoyan_token", token); epoch++; activeEpoch = epoch; showUser(data.user); $("auth-password").value = ""; page = 0; await history();
  } catch (error) { if (activeEpoch === epoch) handleError(error); }
  finally { $("login").disabled = false; $("register").disabled = false; }
});
$("logout").addEventListener("click", async () => {
  const request = api("/api/auth/logout", { method: "POST" }); clearSession(); const current = epoch; message();
  try { await request; } catch { if (current === epoch) message("已在本页退出；服务端注销未确认，该会话将在到期后失效。"); }
});
$("task-form").addEventListener("submit", async event => {
  event.preventDefault(); if (busy) return;
  const input = $("task-input").value.trim(); if (!input) { message("请输入具体任务"); return; }
  const current = epoch, selected = ++selection; setBusy(true); message();
  try {
    const result = await api("/api/tasks", { method: "POST", body: JSON.stringify({ input, taskType: "knowledge_qa", ...($("task-subject").value ? { subject: $("task-subject").value } : {}) }) });
    if (current !== epoch) return;
    if (selected === selection) showResult(result); page = 0; await history();
  } catch (error) { if (current === epoch) handleError(error); }
  finally { if (current === epoch) setBusy(false); }
});
$("example").addEventListener("click", () => { $("task-input").value = "请解释进程与线程的基本概念。"; $("task-input").focus(); });
for (const [id, change] of [["refresh", 0], ["prev", -1], ["next", 1]]) {
  $(id).addEventListener("click", async () => { const current = epoch; page = Math.max(0, page + change); message(); try { await Promise.all([history(), loadStudySummary()]); } catch (error) { if (current === epoch) handleError(error); } });
}

$("practice-form").addEventListener("submit", async event => {
  event.preventDefault(); message();
  try { await createPractice({ mode: $("practice-mode").value, questionCount: Number($("practice-count").value),
    ...($("practice-subject").value ? { subject: $("practice-subject").value } : {}),
    ...($("practice-difficulty").value ? { difficulty: $("practice-difficulty").value } : {}) }); }
  catch (error) { handleError(error); }
});
$("reload-sessions").addEventListener("click", () => loadPracticeHome().catch(handleError));
$("answer-form").addEventListener("submit", event => submitPracticeAnswer(event).catch(handleError));
$("hint-one").addEventListener("click", () => requestHint(1).catch(handleError));
$("hint-two").addEventListener("click", () => requestHint(2).catch(handleError));
$("favorite-question").addEventListener("click", () => toggleFavorite().catch(handleError));
$("previous-question").addEventListener("click", () => openPracticeItem(practiceIndex - 1).catch(handleError));
$("next-question").addEventListener("click", () => openPracticeItem(practiceIndex + 1).catch(handleError));
$("finish-session").addEventListener("click", () => finishPractice().catch(handleError));
$("close-result").addEventListener("click", () => { $("practice-result").hidden = true; loadPracticeHome().catch(handleError); });
$("refresh-wrong").addEventListener("click", () => loadWrongQuestions().catch(handleError));
$("start-wrong-practice").addEventListener("click", async () => {
  try { location.hash = "practice"; await createPractice({ mode: "wrong", questionCount: 10 }); }
  catch (error) { handleError(error); }
});


const features = {
  profile: ["个人档案", "将保存报考年份、目标专业、地区偏好和学习基础。", ["按账号保存个人条件", "允许逐步补充资料"]],
  schools: ["院校推荐", "将结合个人条件和经核验的招生资料比较候选专业。", ["按年份与专业匹配", "展示条件和来源", "保留推荐记录"]],
  admin: ["资料管理", "资料、招生记录与题目将通过管理员审核后发布。", ["来源与使用权限登记", "资料版本和发布", "管理员权限校验"]]
};
function renderRoute() {
  if (!currentUser) return;
  const route = location.hash.slice(1) || "home";
  const name = route in features || ["home", "knowledge", "practice", "wrong", "records"].includes(route) ? route : "home";
  $("home-panel").hidden = name !== "home";
  $("knowledge-panel").hidden = name !== "knowledge";
  $("records-panel").hidden = name !== "records";
  $("practice-panel").hidden = name !== "practice";
  $("wrong-panel").hidden = name !== "wrong";
  $("feature-panel").hidden = !(name in features);
  for (const link of $("navigation").querySelectorAll("a")) {
    if (link.hash === `#${name}`) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  }
  if (name in features) {
    const [title, description, items] = features[name];
    $("feature-title").textContent = title;
    $("feature-description").textContent = name === "admin" && currentUser.role !== "admin" ? "该入口仅供管理员使用。" : description;
    listText("feature-items", name === "admin" && currentUser.role !== "admin" ? [] : items);
  }
  if (name === "practice") loadPracticeHome().catch(handleError);
  if (name === "wrong") loadWrongQuestions().catch(handleError);
  if (name === "records") loadStudySummary().catch(handleError);
}
window.addEventListener("hashchange", renderRoute);

(async () => {
  if (!token) { showUser(null); return; }
  const current = epoch;
  try { const user = await api("/api/auth/me"); if (current !== epoch) return; showUser(user); await history(); }
  catch (error) { if (current === epoch) handleError(error); }
})();
