import { request } from "./js/api.js";
"use strict";

const $ = id => document.getElementById(id);
const statuses = { running: "处理中", completed: "已完成", needs_input: "需补充信息", unsupported: "资料未覆盖", failed: "执行失败" };
let token = sessionStorage.getItem("kaoyan_token") || "";
let currentUser = null;
let epoch = 0, selection = 0, historyVersion = 0, page = 0, pages = 0, busy = false;

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
  page = 0; pages = 0; setBusy(false); showUser(null); resetResult(); $("history-items").replaceChildren(); $("task-input").value = ""; $("task-subject").value = "";
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
  $(id).addEventListener("click", async () => { const current = epoch; page = Math.max(0, page + change); message(); try { await history(); } catch (error) { if (current === epoch) handleError(error); } });
}


const features = {
  profile: ["个人档案", "将保存报考年份、目标专业、地区偏好和学习基础。", ["按账号保存个人条件", "允许逐步补充资料"]],
  schools: ["院校推荐", "将结合个人条件和经核验的招生资料比较候选专业。", ["按年份与专业匹配", "展示条件和来源", "保留推荐记录"]],
  practice: ["刷题中心", "将以审核题库组织完整练习批次。", ["章节、随机、错题与收藏模式", "答题卡、草稿保存与继续练习", "分步提示、确定性判分与批次结果"]],
  wrong: ["错题本", "将关联真实作答、知识点和复习记录。", ["错题归集与重练", "掌握状态", "有依据的Agent辅导"]],
  admin: ["资料管理", "资料、招生记录与题目将通过管理员审核后发布。", ["来源与使用权限登记", "资料版本和发布", "管理员权限校验"]]
};
function renderRoute() {
  if (!currentUser) return;
  const route = location.hash.slice(1) || "home";
  const name = route in features || ["home", "knowledge", "records"].includes(route) ? route : "home";
  $("home-panel").hidden = name !== "home";
  $("knowledge-panel").hidden = name !== "knowledge";
  $("records-panel").hidden = name !== "records";
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
}
window.addEventListener("hashchange", renderRoute);

(async () => {
  if (!token) { showUser(null); return; }
  const current = epoch;
  try { const user = await api("/api/auth/me"); if (current !== epoch) return; showUser(user); await history(); }
  catch (error) { if (current === epoch) handleError(error); }
})();
