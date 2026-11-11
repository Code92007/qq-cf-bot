"use strict";

const $ = (id) => document.getElementById(id);
const fieldNames = ["title", "problemRef", "idea", "code", "language", "nextStep"];
const state = { data: null, selected: null, base: "", csrf: "", user: null, clientId: "", status: "open", page: 1,
  saving: null, action: false, conflict: false, saveTimer: null, searchTimer: null, request: 0, localOk: true };
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fields = () => Object.fromEntries(fieldNames.map((name) => [name, $(name).value]));
const signature = (value) => JSON.stringify(fieldNames.map((name) => value[name]));
const dirty = () => state.user && signature(fields()) !== state.base;
const hasContent = () => fieldNames.some((name) => name !== "language" && $(name).value.trim());
const newClientId = () => globalThis.crypto?.randomUUID?.() || `draft-${Date.now()}-${Math.random().toString(36).slice(2)}`;
const localKey = (id = state.selected?.id || "new") => `cf-unfinished-${state.user}-${id}`;
const formatTime = (value) => new Date(value).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });

function notice(message = "", error = false) {
  $("notice").textContent = message;
  $("notice").classList.toggle("error", error);
}

function backup() {
  if (!state.user) return;
  try {
    localStorage.setItem(localKey(), JSON.stringify({ ...fields(), revision: state.selected?.revision || 0, clientId: state.clientId }));
    state.localOk = true;
  } catch (_) { state.localOk = false; }
}

function removeBackup(key) {
  try { localStorage.removeItem(key); } catch (_) { /* Saving to the server still works. */ }
}

async function api(path, body) {
  const response = await fetch(path, body === undefined ? { credentials: "same-origin" } : {
    method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrf }, body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.message || "保存失败，请稍后重试。");
    error.status = response.status;
    error.code = data.error;
    throw error;
  }
  return data;
}

function handleError(error) {
  if (error.code === "draft_conflict") {
    state.conflict = true;
    $("conflict").hidden = false;
    backup();
  }
  if (error.status === 401) {
    clearTimeout(state.saveTimer);
    $("draftFields").disabled = true;
    notice("登录已过期。未同步的草稿已尽量保留在本机，请重新登录后继续。", true);
    $("loginRequired").hidden = false;
  } else notice(error.message || "网络连接失败。草稿尚未同步，可以点击保存重试。", true);
  $("saveHint").textContent = state.localOk ? "尚未同步 · 本机保留了草稿" : "尚未同步 · 请保留此页面并重试保存";
}

async function loadList() {
  const request = ++state.request;
  const query = new URLSearchParams({ status: state.status, page: String(state.page), q: $("search").value.trim() });
  const data = await api(`/api/unfinished?${query}`);
  if (request !== state.request) return;
  if (state.user && data.user.id !== state.user) {
    $("draftFields").disabled = true;
    throw new Error("登录账号已改变，请刷新页面后继续。");
  }
  state.data = data;
  state.user = data.user.id;
  state.csrf = data.csrfToken;
  state.page = data.page;
  $("userName").textContent = data.user.displayName;
  renderList();
}

function renderList() {
  if (!state.data) return;
  const { items, counts, pages, page } = state.data;
  $("doneCount").textContent = counts.done;
  $("allCount").textContent = counts.all;
  $("openCount").textContent = counts.open;
  $("tabDoneCount").textContent = counts.done;
  $("completionProgress").max = counts.all || 1;
  $("completionProgress").value = counts.done;
  $("progressHint").textContent = counts.all === 0 ? "先存下一道，下次就有了起点。" : counts.open === 0 ? "都划掉了！让脑袋轻一会儿。" : `还有 ${counts.open} 道，等下一段空闲时间。`;
  document.querySelectorAll("[data-status]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.status === state.status)));
  $("entryList").innerHTML = items.map((item) => `<article class="entry-card ${item.status === "done" ? "done" : ""} ${state.selected?.id === item.id ? "selected" : ""}">
    <button class="entry-check" type="button" data-toggle="${item.id}" aria-label="${item.status === "done" ? "恢复待继续" : "划掉"}：${escapeHtml(item.title)}" aria-pressed="${item.status === "done"}">${item.status === "done" ? "✓" : ""}</button>
    <button class="entry-open" type="button" data-open="${item.id}" ${state.selected?.id === item.id ? 'aria-current="true"' : ""}><strong>${escapeHtml(item.title)}</strong>
    <span class="entry-preview">${escapeHtml(item.nextStep ? `↳ ${item.nextStep}` : item.preview || item.problemRef || "留个断点，下次继续")}</span>
    <span class="entry-tags">${item.hasIdea ? "<span>半份 idea</span>" : ""}${item.hasCode ? "<span>半份代码</span>" : ""}<time datetime="${escapeHtml(item.updatedAt)}">${escapeHtml(formatTime(item.updatedAt))}</time></span></button></article>`).join("");
  $("listEmpty").hidden = items.length > 0;
  $("listEmpty").textContent = $("search").value.trim() ? "没有搜到这道题，换个关键词试试。" : state.status === "done" ? "还没有划掉的题。每解决一道，这里就多一份成就感。" : state.status === "all" ? "还没有题目。先把脑子里没想完的那道存下来。" : "池子暂时空着。存一道半成品，下次有空再继续。";
  $("pagination").hidden = pages <= 1;
  $("pageHint").textContent = `${page} / ${pages}`;
  $("previous").disabled = page <= 1;
  $("next").disabled = page >= pages;
}

function renderEditorMeta() {
  const item = state.selected;
  const done = item?.status === "done";
  $("editorEyebrow").textContent = item ? (done ? "这一道，已划掉" : "接着上次的断点") : "存下这个断点";
  $("editorHeading").textContent = item ? (done ? "又完成了一道。" : "从这里，继续。") : "留给下次的自己";
  $("completeEntry").disabled = !item || state.action;
  $("completeEntry").textContent = done ? "↶ 恢复待继续" : "✓ 划掉这道题";
  $("entryTime").textContent = item ? `${done ? `完成于 ${formatTime(item.completedAt)} · ` : ""}更新于 ${formatTime(item.updatedAt)}` : "";
  $("sourceLink").hidden = !item?.url;
  if (item?.url) $("sourceLink").href = item.url;
  else $("sourceLink").removeAttribute("href");
}

function openEditor(item = null, recover = true) {
  clearTimeout(state.saveTimer);
  state.selected = item;
  state.clientId = newClientId();
  state.conflict = false;
  $("conflict").hidden = true;
  const initial = item || { title: "", problemRef: "", idea: "", code: "", language: "cpp", nextStep: "" };
  fieldNames.forEach((name) => { $(name).value = initial[name]; });
  state.base = signature(initial);
  $("saveHint").textContent = item ? "已保存到账户" : "写下一点内容，会自动保存";
  if (recover) {
    let local;
    try { local = JSON.parse(localStorage.getItem(localKey()) || "null"); } catch (_) { /* Invalid or unavailable local draft. */ }
    if (local && fieldNames.every((name) => typeof local[name] === "string") && signature(local) !== state.base) {
      fieldNames.forEach((name) => { $(name).value = local[name]; });
      if (/^[A-Za-z0-9_-]{8,80}$/.test(local.clientId)) state.clientId = local.clientId;
      $("saveHint").textContent = "已找回本机尚未同步的草稿";
      if (item && local.revision !== item.revision) {
        state.conflict = true;
        $("conflict").hidden = false;
      } else scheduleSave();
    }
  }
  renderEditorMeta();
  renderList();
}

function scheduleSave() {
  clearTimeout(state.saveTimer);
  if (!state.user || state.conflict || $("draftFields").disabled) return;
  state.saveTimer = setTimeout(() => saveDraft().catch(handleError), 900);
}

async function saveDraft() {
  clearTimeout(state.saveTimer);
  if (state.saving) {
    await state.saving;
    return saveDraft();
  }
  if (state.conflict) throw new Error("请先处理草稿版本冲突，当前内容会保留。");
  if (!dirty() || (!state.selected && !hasContent())) return;
  if ($("draftFields").disabled) throw new Error("请重新登录后继续保存。");
  if (!$("draftForm").reportValidity()) throw new Error("内容超过长度限制，请检查后保存。");
  const snapshot = fields();
  const oldKey = localKey();
  const body = { ...snapshot, clientId: state.clientId, ...(state.selected ? { id: state.selected.id, revision: state.selected.revision } : {}) };
  $("saveHint").textContent = "正在保存…";
  state.saving = (async () => {
    const { item } = await api("/api/unfinished/save", body);
    state.selected = item;
    // Only apply normalized fields if the user has not typed during this request.
    const normalized = { ...snapshot, title: snapshot.title.trim() || snapshot.problemRef.trim().slice(0, 120) || "未命名的题目", problemRef: snapshot.problemRef.trim() };
    if (signature(fields()) === signature(snapshot) && signature(item) === signature(normalized)) {
      fieldNames.forEach((name) => { $(name).value = item[name]; });
    }
    state.base = signature(item);
    removeBackup(oldKey);
    if (dirty()) backup();
    else removeBackup(localKey());
    $("saveHint").textContent = dirty() ? "还有新改动，正在接着保存…" : "✓ 已保存到账户";
    notice();
    renderEditorMeta();
    // The save is complete even if refreshing the sidebar temporarily fails.
    try { await loadList(); } catch (error) { notice(`草稿已保存，列表刷新失败：${error.message}`, true); }
  })();
  try { await state.saving; } finally { state.saving = null; }
  if (dirty()) return saveDraft();
}

async function action(work) {
  if (state.action) return;
  state.action = true;
  renderEditorMeta();
  try { await work(); } catch (error) { handleError(error); }
  finally { state.action = false; renderEditorMeta(); }
}

async function selectEntry(id) {
  if (state.selected?.id === id) return;
  await saveDraft();
  $("draftFields").disabled = true;
  try {
    const { item } = await api(`/api/unfinished/entry?id=${id}`);
    openEditor(item);
  } finally { $("draftFields").disabled = false; }
  if (window.matchMedia("(max-width: 720px)").matches) $("editorHeading").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function toggleEntry(id) {
  await saveDraft();
  const item = state.selected?.id === id ? state.selected : state.data.items.find((entry) => entry.id === id);
  if (!item) return;
  try {
    const result = await api("/api/unfinished/status", { id, revision: item.revision, status: item.status === "done" ? "open" : "done" });
    if (state.selected?.id === id) {
      state.selected = result.item;
      // Edits made during the status request still need to be saved.
      if (dirty()) backup();
      else removeBackup(localKey());
      renderEditorMeta();
      if (dirty()) scheduleSave();
    }
    await loadList();
    notice(result.item.status === "done" ? "✓ 又划掉一道！想一半的题，终于走到了终点。可随时恢复待继续。" : "已放回待继续。之前的思路和代码都在。");
  } catch (error) {
    // A stale sidebar row does not put an unrelated editor into conflict.
    if (error.code === "draft_conflict" && state.selected?.id !== id) {
      await loadList();
      throw new Error("这道题刚刚在另一处更新，列表已刷新，请再试一次。");
    }
    throw error;
  }
}

async function start() {
  try {
    await loadList();
    $("loading").hidden = true;
    $("retryLoad").hidden = true;
    $("workspace").hidden = false;
    $("loginRequired").hidden = true;
    // A new local draft takes precedence so an interrupted first save can be recovered.
    let localNew = false;
    try { localNew = !!localStorage.getItem(localKey("new")); } catch (_) { /* Server storage remains available. */ }
    if (localNew || !state.data.items.length) openEditor();
    else {
      const { item } = await api(`/api/unfinished/entry?id=${state.data.items[0].id}`);
      openEditor(item);
    }
  } catch (error) {
    $("loading").hidden = true;
    if (error.status === 401) $("loginRequired").hidden = false;
    else { notice(error.message || "暂时无法加载续题池，请重试。", true); $("retryLoad").hidden = false; }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("draftForm").addEventListener("input", () => {
    backup();
    $("saveHint").textContent = state.localOk ? "改动已暂存本机，正在等待同步…" : "有未保存改动，正在等待同步…";
    scheduleSave();
  });
  $("draftForm").addEventListener("submit", (event) => { event.preventDefault(); saveDraft().catch(handleError); });
  $("newEntry").addEventListener("click", () => action(async () => { await saveDraft(); openEditor(); $("title").focus(); }));
  $("entryList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-open], [data-toggle]");
    if (!button) return;
    action(() => button.hasAttribute("data-toggle") ? toggleEntry(Number(button.dataset.toggle)) : selectEntry(Number(button.dataset.open)));
  });
  $("completeEntry").addEventListener("click", () => action(() => toggleEntry(state.selected.id)));
  $("statusTabs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-status]");
    if (!button) return;
    action(async () => { state.status = button.dataset.status; state.page = 1; await loadList(); });
  });
  $("search").addEventListener("input", () => {
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(() => { state.page = 1; loadList().catch(handleError); }, 250);
  });
  ["previous", "next"].forEach((id) => $(id).addEventListener("click", () => action(async () => { state.page += id === "previous" ? -1 : 1; await loadList(); })));
  $("retryLoad").addEventListener("click", start);
  $("saveCopy").addEventListener("click", () => action(async () => {
    const oldKey = localKey();
    state.selected = null;
    state.clientId = newClientId();
    state.base = "";
    state.conflict = false;
    $("conflict").hidden = true;
    backup();
    await saveDraft();
    removeBackup(oldKey);
    notice("当前草稿已另存一份，另一处的记录也保留着。");
  }));
  $("reloadEntry").addEventListener("click", () => action(async () => {
    if (!window.confirm("加载服务器最新版本会替换编辑框里的内容。要保留当前内容，请先选择「另存一份」。确定加载？")) return;
    $("draftFields").disabled = true;
    try {
      const { item } = await api(`/api/unfinished/entry?id=${state.selected.id}`);
      removeBackup(localKey());
      openEditor(item, false);
    } finally { $("draftFields").disabled = false; }
    notice("已加载最新版本。");
  }));
  $("code").addEventListener("keydown", (event) => {
    if (event.key !== "Tab" || event.shiftKey) return;
    event.preventDefault();
    const input = event.target;
    input.setRangeText("    ", input.selectionStart, input.selectionEnd, "end");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  window.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s" && state.user) { event.preventDefault(); saveDraft().catch(handleError); }
  });
  window.addEventListener("beforeunload", (event) => {
    if (dirty()) { backup(); event.preventDefault(); event.returnValue = ""; }
  });
  window.addEventListener("online", () => { if (dirty()) saveDraft().catch(handleError); });
  window.addEventListener("focus", () => { if (state.user) loadList().catch(handleError); });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && dirty()) { backup(); saveDraft().catch(handleError); }
  });
  start();
});
