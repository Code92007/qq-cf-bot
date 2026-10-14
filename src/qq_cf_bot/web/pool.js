"use strict";

const pool = { data: null, csrf: "", status: "new", page: 1, busy: false, selected: null, request: 0, timer: null };
const $ = (id) => document.getElementById(id);
const statusNames = { new: "新瓶子", picked: "已捞待做", skipped: "已放弃", ac: "已 AC" };
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

document.addEventListener("DOMContentLoaded", () => {
  $("draw").addEventListener("click", drawBottle);
  $("drawAgain").addEventListener("click", drawBottle);
  ["openToss", "emptyToss"].forEach((id) => $(id).addEventListener("click", openToss));
  document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => $(button.dataset.close).close()));
  $("tossForm").addEventListener("submit", tossBottle);
  $("statusTabs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-status]");
    if (!button || pool.busy) return;
    pool.status = button.dataset.status;
    pool.page = 1;
    loadPool();
  });
  $("filters").addEventListener("submit", (event) => { event.preventDefault(); filterChanged(); });
  $("filters").addEventListener("input", () => {
    clearTimeout(pool.timer);
    pool.timer = setTimeout(filterChanged, 300);
  });
  $("filters").addEventListener("change", () => { clearTimeout(pool.timer); filterChanged(); });
  $("clearFilters").addEventListener("click", () => { $("filters").reset(); filterChanged(); });
  $("refresh").addEventListener("click", () => loadPool());
  $("previous").addEventListener("click", () => changePage(-1));
  $("next").addEventListener("click", () => changePage(1));
  $("problemList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-open]");
    if (!button || pool.busy) return;
    const item = pool.data.items.find((p) => p.id === Number(button.dataset.open));
    if (item) openBottle(item, false);
  });
  $("bottleBody").addEventListener("click", (event) => {
    const button = event.target.closest("[data-record], [data-practice], [data-keep]");
    if (!button || pool.busy) return;
    if (button.hasAttribute("data-practice")) practiceBottle();
    else if (button.hasAttribute("data-keep")) $("bottleDialog").close();
    else updateRecord(button.dataset.record);
  });
  window.addEventListener("focus", () => { if (pool.data && !pool.busy && !$("bottleDialog").open && !$("tossDialog").open) loadPool(); });
  loadPool();
});

function filters() {
  const form = new FormData($("filters"));
  return Object.fromEntries([...form.entries()].filter(([, value]) => value !== "").map(([key, value]) => [key, key === "mine" ? "1" : value]));
}

function filterChanged() { pool.page = 1; loadPool(); }
function changePage(offset) { pool.page += offset; loadPool(); }

async function api(path, body) {
  const response = await fetch(path, body === undefined ? { credentials: "same-origin" } : {
    method: "POST", credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": pool.csrf }, body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) { const error = new Error(data.message || "请求失败，请稍后重试。"); error.status = response.status; throw error; }
  return data;
}

function notice(message = "", error = false) {
  $("notice").textContent = message;
  $("notice").classList.toggle("success", !error);
}

function signedOut() {
  pool.request += 1;
  pool.data = null;
  pool.csrf = "";
  $("poolView").hidden = true;
  $("loginRequired").hidden = false;
  $("userName").textContent = "";
  $("drawHint").textContent = "登录后随手投题，随缘捞题。";
  ["bottleDialog", "tossDialog"].forEach((id) => { if ($(id).open) $(id).close(); });
  setBusy(false);
}

async function loadPool() {
  const request = ++pool.request;
  try {
    const query = new URLSearchParams({ ...filters(), status: pool.status, page: String(pool.page) });
    const data = await api(`/api/pool?${query}`);
    if (request !== pool.request) return;
    pool.data = data;
    pool.csrf = data.csrfToken;
    pool.page = data.page;
    $("poolView").hidden = false;
    $("loginRequired").hidden = true;
    $("userName").textContent = data.user.displayName;
    renderPool();
    return true;
  } catch (error) {
    if (request !== pool.request) return;
    if (error.status === 401) signedOut();
    else notice(error.message, true);
    return false;
  }
}

function renderPool() {
  const data = pool.data;
  Object.entries(data.counts).forEach(([status, count]) => { $(`count-${status}`).textContent = count; });
  document.querySelectorAll("[data-status]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.status === pool.status)));
  const tag = $("tagFilter").value;
  $("tagFilter").innerHTML = '<option value="">所有标签</option>' + data.tags.map((t) => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join("");
  $("tagFilter").value = data.tags.includes(tag) ? tag : "";
  $("summary").textContent = `${statusNames[pool.status] || "全部题目"} · ${data.total} 道`;
  $("drawHint").textContent = `当前筛选可捞 ${data.available} 瓶 · 已捞、放弃和 AC 的题自动避开`;
  $("problemList").innerHTML = data.items.map(cardHtml).join("");
  $("empty").hidden = data.total > 0;
  $("emptyText").textContent = data.counts.all === 0 ? "池子还空着，把群友推荐的好题丢进来吧。" : pool.status === "new" ? "当前没有新瓶子。试试放宽筛选，或去「已捞待做」继续之前的题。" : "暂时没有符合条件的记录。换个筛选试试。";
  $("emptyToss").textContent = data.counts.all === 0 ? "投下第一瓶" : "＋ 再投一道题";
  $("pageLabel").textContent = `${data.page} / ${data.pages}`;
  $("pagination").hidden = data.pages <= 1;
  setBusy(pool.busy);
}

function tagsHtml(item) {
  return `<div class="pool-tags"><span class="pool-tag pool-rating">${item.rating === null ? "未评级" : `参考 ${escapeHtml(item.rating)}`}</span>${item.tags.map((t) => `<span class="pool-tag">${escapeHtml(t)}</span>`).join("")}</div>`;
}

function date(value, full = false) {
  if (!value) return "";
  const at = new Date(value);
  return Number.isNaN(at.getTime()) ? "" : full ? at.toLocaleString("zh-CN", { hour12: false }) : at.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

function cardHtml(item) {
  return `<article class="pool-card"><div class="pool-card-top"><span class="pool-oj">${escapeHtml(pool.data.platforms[item.platform])}</span><span class="pool-status status-${item.status}">${statusNames[item.status]}</span></div>
    <h3>${escapeHtml(item.title)}</h3><span class="problem-id">${escapeHtml(item.problemId)}</span>${tagsHtml(item)}
    <p class="pool-note">${escapeHtml(item.note || "一瓶没有附言的好题，等你打开。")}</p>
    <div class="pool-card-foot"><small>${escapeHtml(item.author)} · ${date(item.createdAt)}${item.status === "ac" ? `<br>${escapeHtml(item.acSource)}${item.acAt ? ` · ${date(item.acAt)}` : ""}` : ""}</small><button data-open="${item.id}" type="button" aria-label="查看 ${escapeHtml(item.title)}">${item.status === "new" ? "打开瓶子 ↗" : "查看记录 ↗"}</button></div></article>`;
}

function openToss() { $("tossError").textContent = ""; $("tossDialog").showModal(); $("tossForm").elements.problemId.focus(); }

function openBottle(item, drawn) {
  pool.selected = item;
  $("bottleEyebrow").textContent = drawn ? "捞到一瓶 · 已收进待做" : "打开一瓶";
  $("bottleError").textContent = "";
  renderBottle();
  if (!$("bottleDialog").open) $("bottleDialog").showModal();
}

function renderBottle() {
  const item = pool.selected;
  let actions = "";
  if (item.status === "new") actions += '<button class="primary" data-record="picked" type="button">收下待做</button>';
  if (item.status === "picked") actions += '<button class="quiet" data-keep type="button">留着下次做</button>';
  if (["new", "picked"].includes(item.status)) {
    actions += '<button class="quiet" data-record="ac" type="button">标记 AC</button><button class="danger-quiet" data-record="skipped" type="button">扔掉不做</button>';
    if (item.platform === "codeforces") actions += '<button class="quiet" data-practice type="button">在站内口胡</button>';
  }
  if (["picked", "skipped"].includes(item.status)) actions += '<button class="quiet" data-record="new" type="button">放回池中</button>';
  if (item.status === "ac" && !item.importedAc) actions += `<button class="quiet" data-record="${item.drawnAt ? "picked" : "new"}" type="button">撤销 AC</button>`;
  $("bottleBody").innerHTML = `<span class="pool-oj">${escapeHtml(pool.data.platforms[item.platform])}</span> <span class="pool-status status-${item.status}">${statusNames[item.status]}</span>
    <h2 id="bottleTitle">${escapeHtml(item.title)}</h2><p class="problem-id">${escapeHtml(item.problemId)}</p>${tagsHtml(item)}
    <p class="pool-note">${escapeHtml(item.note || "这道题没有附言。打开看看，或许正合口味。")}</p>
    <p class="bottle-byline">${escapeHtml(item.author)} 投于 ${date(item.createdAt, true)}${item.drawnAt ? `<br>最近捞到：${date(item.drawnAt, true)} · 捞过 ${item.drawCount} 次` : ""}${item.status === "ac" ? `<br>${escapeHtml(item.acSource)}${item.acAt ? ` · ${date(item.acAt, true)}` : ""}` : ""}</p>
    <div class="bottle-actions"><a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">去原 OJ 看题 ↗</a>${actions}</div>
    <p class="pool-small">${item.importedAc ? "已有站内通过或已同步的平台 AC，已自动排除随机。原记录更新后这里会随之更新。" : item.status === "skipped" ? "已为你排除这道题，其他人仍然可以捞到。想再试时，可以主动放回池中。" : item.status === "ac" ? "已记入你的口胡池 AC 记录，不会再随机出现。手动记录不计训练 Rating。" : "捞到的题会留在「已捞待做」。收下或扔掉，都不影响别人捞题。"}</p>`;
}

function setBusy(busy) {
  pool.busy = busy;
  document.querySelectorAll("button").forEach((button) => { button.disabled = busy; });
  $("draw").disabled = busy || !pool.data;
  $("openToss").disabled = busy || !pool.data;
  $("drawAgain").disabled = busy || !pool.data;
  $("previous").disabled = busy || !pool.data || pool.page <= 1;
  $("next").disabled = busy || !pool.data || pool.page >= pool.data.pages;
  $("draw").textContent = busy ? "稍等一下…" : "随机捞一瓶 ↗";
}

async function mutation(path, body, onSuccess, errorId) {
  if (pool.busy) return;
  pool.request += 1;
  setBusy(true);
  notice();
  if (errorId) $(errorId).textContent = "";
  try {
    const result = await api(path, body);
    await onSuccess(result);
    await loadPool();
  } catch (error) {
    if (error.status === 401) signedOut();
    else if (errorId) $(errorId).textContent = error.message;
    else notice(error.message, true);
  } finally { setBusy(false); }
}

function tossBottle(event) {
  event.preventDefault();
  const body = Object.fromEntries(new FormData($("tossForm")));
  return mutation("/api/pool/problems", body, async (result) => {
    $("tossDialog").close();
    $("tossForm").reset();
    notice(result.message);
    openBottle(result.item, false);
    $("bottleEyebrow").textContent = result.created ? "新瓶子已入池" : "这题已经在池里 · 找到原瓶子";
  }, "tossError");
}

function drawBottle() {
  if (!$("filters").reportValidity()) return;
  const errorId = $("bottleDialog").open ? "bottleError" : null;
  return mutation("/api/pool/draw", { filters: filters() }, async (result) => openBottle(result.item, true), errorId);
}

function updateRecord(status) {
  return mutation("/api/pool/record", { id: pool.selected.id, status }, async (result) => {
    pool.selected = result.item;
    $("bottleEyebrow").textContent = "记录已更新";
    renderBottle();
  }, "bottleError");
}

function practiceBottle() {
  let settings = {};
  try { settings = JSON.parse(localStorage.getItem("cf-bot-training-settings-v2") || "{}"); } catch (_) { /* Use server defaults. */ }
  return mutation("/api/pool/practice", { ...settings, id: pool.selected.id }, async () => { location.assign("/"); }, "bottleError");
}
