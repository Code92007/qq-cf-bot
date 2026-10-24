const $ = (id) => document.getElementById(id);
const app = { csrf: "", lists: [], listId: 0, entries: [], entry: null, view: "union", draftVersion: 0, saving: false, savePromise: null, timer: null };
const statusNames = { new: "未开始", doing: "进行中", done: "手动完成", skipped: "暂跳过" };
function completed(item) { return app.view === "oral" ? item.oral : app.view === "code" ? item.code : item.oral || item.code; }
function resultName(item) { return [item.oral ? "口胡 AC" : "", item.code ? "代码 AC" : ""].filter(Boolean).join("、") || "尚未通过"; }
function updateSummary() {
  const done = app.entries.filter(completed).length;
  const oral = app.entries.filter((item) => item.oral).length;
  const code = app.entries.filter((item) => item.code).length;
  $("listCount").textContent = `${done} / ${app.entries.length} 当前视角通过 · 口胡 ${oral} · 代码 ${code}`;
}
function renderPracticeResult(entry) {
  $("practiceResult").innerHTML = `${entry.oral ? "<span>口胡 AC</span>" : ""}${entry.code ? "<span>代码 AC</span>" : ""}${!entry.oral && !entry.code ? '<span class="pending">尚未通过</span>' : ""}`;
}

function notice(message = "") { $("notice").textContent = message; }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]); }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? { credentials: "same-origin" } : {
    method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRF-Token": app.csrf }, body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw Object.assign(new Error(result.message || "请求失败，请重试。"), { status: response.status });
  return result;
}
async function loadLists(preferred) {
  const result = await api("/api/lists");
  app.lists = result.lists;
  app.listId = preferred && app.lists.some((item) => item.id === preferred) ? preferred :
    app.lists.some((item) => item.id === app.listId) ? app.listId : app.lists[0]?.id || 0;
  $("listSelect").innerHTML = app.lists.map((item) => `<option value="${item.id}">${escapeHtml(item.name)} · ${item.done}/${item.total}</option>`).join("");
  $("listSelect").value = String(app.listId);
  $("listView").hidden = false;
  for (const id of ["renameList", "deleteList", "addEntries", "randomEntry"]) $(id).disabled = !app.listId;
  if (app.listId) await loadEntries();
  else { app.entries = []; $("listTitle").textContent = "暂无题单"; $("listCount").textContent = ""; $("ojWallStatus").textContent = ""; renderEntries(); }
}
async function loadEntries() {
  const result = await api(`/api/lists/entries?id=${app.listId}`);
  app.entries = result.entries;
  $("listTitle").textContent = result.list.name;
  updateSummary();
  const wall = result.ojWall || {};
  const wallStatus = $("ojWallStatus");
  wallStatus.replaceChildren();
  if (wall.connected) {
    const stamp = wall.lastSync ? new Date(wall.lastSync * 1000).toLocaleString("zh-CN", { hour12: false }) : "未知";
    wallStatus.append(document.createTextNode(`OJ Wall · ${stamp}${wall.stale ? " · 记录可能未更新" : ""}${wall.error ? " · 同步失败" : ""}  `));
  } else wallStatus.append(document.createTextNode("OJ Wall 未关联  "));
  const wallLink = document.createElement("a"); wallLink.href = "/regionals";
  wallLink.textContent = wall.connected ? "管理同步" : "前往关联"; wallStatus.append(wallLink);
  const selected = $("groupFilter").value;
  const groups = [...new Set(app.entries.map((item) => item.group))];
  $("groupFilter").innerHTML = '<option value="">全部分组</option>' + groups.map((group) => `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`).join("");
  $("groupFilter").value = groups.includes(selected) ? selected : "";
  renderEntries();
}
function filtered() {
  const query = $("search").value.trim().toLowerCase();
  const group = $("groupFilter").value;
  const status = $("statusFilter").value;
  const result = $("resultFilter").value;
  return app.entries.filter((item) => (!group || item.group === group) && (status === "all" || item.status === status)
    && (result === "all" || result === "unfinished" && !completed(item)
      || result === "oralOnly" && item.oral && !item.code
      || result === "codeOnly" && item.code && !item.oral
      || result === "both" && item.oral && item.code)
    && (!query || `${item.problemId} ${item.title}`.toLowerCase().includes(query)));
}
function renderEntries() {
  const entries = filtered();
  $("listEmpty").hidden = !!entries.length;
  $("listEmpty").textContent = app.entries.length ? "没有符合筛选条件的题目。" : "当前题单还没有题目。";
  const groups = [...new Set(entries.map((item) => item.group))];
  $("entryGroups").innerHTML = groups.map((group) => {
    const items = entries.filter((item) => item.group === group);
    const done = items.filter(completed).length;
    return `<section class="lists-group"><h3>${escapeHtml(group)} <small>${done}/${items.length} 当前视角通过</small></h3><div class="entry-grid">${items.map((item) =>
      `<button class="entry" data-entry="${item.id}" data-status="${item.status}" data-passed="${completed(item)}" title="${escapeHtml(item.problemId)} · ${resultName(item)} · ${statusNames[item.status]}"><span><strong>${escapeHtml(item.problemId)}</strong>${item.title && item.title !== item.problemId ? `<small>${escapeHtml(item.title)}</small>` : ""}${item.hasDraft ? '<small>有草稿</small>' : ""}</span><span class="entry-marks" aria-hidden="true">${item.oral ? '<b>口</b>' : ""}${item.code ? '<b>码</b>' : ""}${!item.oral && !item.code ? '<i class="status-dot"></i>' : ""}</span></button>`).join("")}</div></section>`;
  }).join("");
}
function setStatement(statement, error) {
  $("statementBody").replaceChildren();
  $("statementError").textContent = error || "";
  if (!statement) return;
  $("practiceTitle").textContent = statement.title || app.entry.entry.problemId;
  for (const [name, key] of [["背景", "background"], ["题目描述", "description"], ["输入格式", "input"], ["输出格式", "output"], ["提示", "hint"]]) {
    const value = statement[key];
    if (!value) continue;
    const section = document.createElement("section"); section.className = "statement-part";
    const heading = document.createElement("h4"); heading.textContent = name;
    const content = document.createElement("div"); content.className = "statement-content";
    if (statement.html?.[key]) content.innerHTML = statement.html[key];
    else content.textContent = value;
    section.append(heading, content); $("statementBody").append(section);
  }
  for (const [index, pair] of (statement.samples || []).entries()) {
    const section = document.createElement("section"); section.className = "statement-part";
    const heading = document.createElement("h4"); heading.textContent = `样例 ${index + 1}`;
    const sample = document.createElement("pre"); sample.textContent = `输入\n${pair[0]}\n\n输出\n${pair[1]}`;
    section.append(heading, sample); $("statementBody").append(section);
  }
}
function renderAttempts(attempts) {
  $("attempts").innerHTML = attempts.length ? attempts.map((attempt) => `<article class="attempt"><strong>${attempt.accepted ? "口胡通过" : "需要修改"}</strong> · ${escapeHtml(new Date(attempt.created_at).toLocaleString("zh-CN", { hour12: false }))}<p>${escapeHtml(attempt.reason)}</p></article>`).join("") : '<p>还没有提交记录。</p>';
}
async function prepareStatement(id) {
  $("statementError").textContent = "正在加载题面…";
  try {
    const result = await api("/api/lists/open", { entryId: id, prepareStatement: true });
    if (app.entry?.entry.id !== id) return;
    app.entry.statement = result.statement;
    setStatement(result.statement, result.statementError);
  } catch (error) {
    if (app.entry?.entry.id === id) $("statementError").textContent = error.message;
  }
}
async function openEntry(id) {
  clearTimeout(app.timer);
  const result = await api("/api/lists/open", { entryId: id, prepareStatement: false });
  app.entry = result;
  app.draftVersion = result.draftVersion;
  $("listView").hidden = true; $("practiceView").hidden = false;
  $("practiceGroup").textContent = result.entry.group;
  $("practiceId").textContent = `${result.entry.platform.toUpperCase()} · ${result.entry.problemId}`;
  $("practiceTitle").textContent = result.entry.title || result.entry.problemId;
  renderPracticeResult(result.entry);
  $("practiceStatus").value = result.entry.status;
  $("sourceLink").href = result.entry.url;
  $("draftText").value = result.draft;
  $("saveHint").textContent = "草稿已保存";
  $("oralResult").textContent = ""; $("oralResult").className = "";
  setStatement(result.statement, result.statementError);
  renderAttempts(result.attempts);
  window.scrollTo(0, 0);
  if (!result.statement) prepareStatement(id);
}
async function saveDraft() {
  if (!app.entry) return true;
  if (app.saving) { try { await app.savePromise; } catch (_) {} return saveDraft(); }
  if ($("draftText").value === app.entry.draft) return true;
  app.saving = true;
  const id = app.entry.entry.id, text = $("draftText").value;
  $("saveHint").textContent = "保存中…";
  let saved = true;
  try {
    app.savePromise = api("/api/lists/draft", { entryId: id, text, version: app.draftVersion });
    const result = await app.savePromise;
    app.draftVersion = result.draftVersion;
    app.entry.draft = text;
    $("saveHint").textContent = $("draftText").value === text ? "草稿已保存" : "有未保存修改";
  } catch (error) { $("saveHint").textContent = error.message; saved = false; }
  finally { app.saving = false; app.savePromise = null; }
  return saved && ($("draftText").value === app.entry.draft || await saveDraft());
}
function scheduleSave() { clearTimeout(app.timer); app.timer = setTimeout(saveDraft, 800); }
async function mutate(action, payload, after) {
  notice();
  try { const result = await api(`/api/lists/${action}`, payload); if (after) await after(result); return result; }
  catch (error) { notice(error.message); return null; }
}
function openDialog(mode) {
  $("listForm").dataset.mode = mode;
  $("dialogTitle").textContent = mode === "create" ? "新建题单" : "添加题目";
  $("listNameWrap").hidden = mode !== "create";
  $("groupWrap").hidden = mode === "create";
  $("listName").required = mode === "create";
  $("entryText").required = mode === "add";
  $("listName").value = ""; $("entryText").value = "";
  $("listDialog").showModal();
  (mode === "create" ? $("listName") : $("entryText")).focus();
}
$("createList").addEventListener("click", () => openDialog("create"));
$("addEntries").addEventListener("click", () => openDialog("add"));
$("cancelDialog").addEventListener("click", () => $("listDialog").close());
$("listForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const mode = $("listForm").dataset.mode;
  const result = await mutate(mode, mode === "create" ? { name: $("listName").value, text: $("entryText").value } :
    { listId: app.listId, group: $("defaultGroup").value, text: $("entryText").value }, async (saved) => {
      $("listDialog").close(); await loadLists(mode === "create" ? saved.id : app.listId);
    });
  if (result && mode === "add") notice(`新增 ${result.added} 题，跳过 ${result.duplicates} 道重复题。`);
});
$("listSelect").addEventListener("change", async () => { app.listId = Number($("listSelect").value); await loadEntries(); });
$("renameList").addEventListener("click", async () => {
  const name = prompt("题单名称", app.lists.find((item) => item.id === app.listId)?.name || "");
  if (name !== null) await mutate("rename", { listId: app.listId, name }, () => loadLists(app.listId));
});
$("deleteList").addEventListener("click", async () => {
  if (confirm("删除这个题单及全部草稿、口胡记录？此操作无法撤销。")) await mutate("delete", { listId: app.listId }, () => loadLists());
});
for (const id of ["search", "groupFilter", "statusFilter", "resultFilter"]) $(id).addEventListener(id === "search" ? "input" : "change", renderEntries);
$("progressView").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-view]");
  if (!button) return;
  app.view = button.dataset.view;
  for (const item of $("progressView").querySelectorAll("button")) {
    item.classList.toggle("selected", item === button);
    item.setAttribute("aria-pressed", String(item === button));
  }
  updateSummary(); renderEntries();
});
$("entryGroups").addEventListener("click", (event) => {
  const button = event.target.closest("[data-entry]"); if (button) openEntry(Number(button.dataset.entry)).catch((error) => notice(error.message));
});
$("randomEntry").addEventListener("click", () => {
  const choices = filtered().filter((item) => !item.oral && item.status !== "skipped");
  if (!choices.length) return notice("当前筛选下没有未口胡的题目。");
  const bytes = new Uint32Array(1); crypto.getRandomValues(bytes);
  openEntry(choices[bytes[0] % choices.length].id).catch((error) => notice(error.message));
});
$("backToList").addEventListener("click", async () => { clearTimeout(app.timer); if (!await saveDraft()) return; app.entry = null; $("practiceView").hidden = true; $("listView").hidden = false; await loadLists(app.listId); });
$("removeEntry").addEventListener("click", async () => {
  if (!app.entry || !confirm("从题单移除此题及其草稿、口胡记录？")) return;
  const entryId = app.entry.entry.id;
  await mutate("remove", { entryId }, async () => { app.entry = null; $("practiceView").hidden = true; $("listView").hidden = false; await loadLists(app.listId); });
});
$("fetchStatement").addEventListener("click", () => { if (app.entry) prepareStatement(app.entry.entry.id); });
$("saveStatement").addEventListener("click", async () => {
  if (!app.entry) return;
  await mutate("statement", { entryId: app.entry.entry.id, text: $("statementText").value }, (result) => {
    app.entry.statement = result.statement; setStatement(result.statement, ""); $("manualStatement").open = false;
  });
});
$("draftText").addEventListener("input", () => { $("saveHint").textContent = "有未保存修改"; scheduleSave(); });
$("saveDraft").addEventListener("click", () => { clearTimeout(app.timer); saveDraft(); });
$("practiceStatus").addEventListener("change", async () => {
  if (!app.entry) return;
  const id = app.entry.entry.id;
  await mutate("status", { entryId: id, status: $("practiceStatus").value }, (result) => { app.entry.entry.status = result.status; });
});
$("submitOral").addEventListener("click", async () => {
  if (!app.entry) return;
  const entryId = app.entry.entry.id, body = $("draftText").value;
  clearTimeout(app.timer); if (!await saveDraft()) return;
  $("submitOral").disabled = true; $("oralResult").textContent = "正在审核…";
  try {
    const result = await api("/api/lists/oral", { entryId, body, requestId: crypto.randomUUID() });
    $("oralResult").textContent = `${result.accepted ? "口胡通过" : "需要修改"}：${result.reason}`;
    $("oralResult").className = result.accepted ? "" : "review";
    const refreshed = await api("/api/lists/open", { entryId, prepareStatement: false });
    if (app.entry?.entry.id === entryId) {
      app.entry = refreshed; app.draftVersion = refreshed.draftVersion;
      $("practiceStatus").value = refreshed.entry.status;
      renderPracticeResult(refreshed.entry); renderAttempts(refreshed.attempts);
    }
  } catch (error) { $("oralResult").textContent = error.message; $("oralResult").className = "review"; }
  finally { $("submitOral").disabled = false; }
});
async function init() {
  try {
    const state = await api("/api/state");
    app.csrf = state.csrfToken; $("userName").textContent = state.user.displayName;
    await loadLists();
  } catch (error) {
    if (error.status === 401) { $("loginRequired").hidden = false; $("createList").hidden = true; }
    else notice(error.message);
  }
}
init();
