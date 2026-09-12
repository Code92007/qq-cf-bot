const state = {
  data: null,
  csrf: "",
  busy: false,
  toastTimer: null,
  giveupTimer: null,
  acRecords: null,
  acRecordsPromise: null,
  activeRecordsTab: "breakdown"
};

const el = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  populateRatings();
  bindEvents();
  loadState();
});

function bindEvents() {
  el("loginTab").addEventListener("click", () => switchAuth("login"));
  el("registerTab").addEventListener("click", () => switchAuth("register"));
  el("oralTab").addEventListener("click", () => switchSubmission("oral"));
  el("codeTab").addEventListener("click", () => switchSubmission("code"));
  el("loginForm").addEventListener("submit", submitLogin);
  el("registerForm").addEventListener("submit", submitRegister);
  el("logoutBtn").addEventListener("click", logout);
  el("newChallengeForm").addEventListener("submit", newChallenge);
  el("giveUpBtn").addEventListener("click", giveUp);
  el("oralForm").addEventListener("submit", submitOral);
  el("codeForm").addEventListener("submit", submitCode);
  el("sourceCode").addEventListener("keydown", handleEditorTab);
  el("ratingDetailBtn").addEventListener("click", () => openAcRecords("breakdown"));
  el("acHistoryBtn").addEventListener("click", () => openAcRecords("history"));
  el("ratingBreakdownTab").addEventListener("click", () => switchAcRecordsTab("breakdown"));
  el("acHistoryTab").addEventListener("click", () => switchAcRecordsTab("history"));
  el("historySearch").addEventListener("input", renderFilteredHistory);
}

async function loadState() {
  try {
    const data = await api("/api/state");
    showApp(data);
  } catch (error) {
    if (error.status === 401) showAuth();
    else showToast(error.message, true);
  }
}

function showAuth() {
  state.data = null;
  state.csrf = "";
  state.acRecords = null;
  if (el("acRecordsDialog").open) el("acRecordsDialog").close();
  el("appView").classList.add("hidden");
  el("authView").classList.remove("hidden");
}

function showApp(data) {
  state.data = data;
  state.csrf = data.csrfToken;
  state.acRecords = null;
  el("authView").classList.add("hidden");
  el("appView").classList.remove("hidden");
  render(data);
}

function switchAuth(mode) {
  const login = mode === "login";
  el("loginTab").classList.toggle("active", login);
  el("loginTab").setAttribute("aria-selected", String(login));
  el("registerTab").classList.toggle("active", !login);
  el("registerTab").setAttribute("aria-selected", String(!login));
  el("loginForm").classList.toggle("hidden", !login);
  el("registerForm").classList.toggle("hidden", login);
}

function switchSubmission(mode) {
  const oral = mode === "oral";
  el("oralTab").classList.toggle("active", oral);
  el("oralTab").setAttribute("aria-selected", String(oral));
  el("codeTab").classList.toggle("active", !oral);
  el("codeTab").setAttribute("aria-selected", String(!oral));
  el("oralForm").classList.toggle("hidden", !oral);
  el("codeForm").classList.toggle("hidden", oral);
}

async function submitLogin(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await authRequest("/api/auth/login", { username: form.get("username"), password: form.get("password") }, "正在登录");
}

async function submitRegister(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await authRequest("/api/auth/register", {
    username: form.get("username"), displayName: form.get("displayName"), password: form.get("password")
  }, "正在创建账号");
}

async function authRequest(path, body, busyText) {
  setBusy(true, busyText);
  try {
    const result = await api(path, { method: "POST", body });
    showApp(result.state);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(false);
  }
}

async function logout() {
  setBusy(true, "正在退出");
  try { await api("/api/auth/logout", { method: "POST", body: {} }); }
  catch (_) { /* A local logout still clears the UI. */ }
  finally { setBusy(false); showAuth(); }
}

async function newChallenge(event) {
  event.preventDefault();
  setBusy(true, "正在准备题面");
  try {
    const result = await api("/api/challenges", {
      method: "POST",
      body: { minRating: Number(el("minRating").value), maxRating: Number(el("maxRating").value) }
    });
    applyState(result.state);
    el("solutionText").value = "";
    el("sourceCode").value = "";
  } catch (error) { showToast(error.message, true); }
  finally { setBusy(false); }
}

async function giveUp() {
  if (el("giveUpBtn").disabled) return;
  setBusy(true, "正在结束本轮");
  try {
    const result = await api("/api/challenges/giveup", { method: "POST", body: {} });
    applyState(result.state);
    showResult({ accepted: false, message: "本轮已结束。", resolved: result.resolved, label: "CHALLENGE CLOSED" });
  } catch (error) { showToast(error.message, true); }
  finally { setBusy(false); }
}

async function submitOral(event) {
  event.preventDefault();
  setBusy(true, "正在审核做法");
  try {
    const result = await api("/api/challenges/oral", { method: "POST", body: { solution: el("solutionText").value } });
    applyState(result.state);
    showResult(result);
  } catch (error) { showToast(error.message, true); }
  finally { setBusy(false); }
}

async function submitCode(event) {
  event.preventDefault();
  setBusy(true, "正在进行代码判定");
  try {
    const result = await api("/api/challenges/code", {
      method: "POST", body: { language: el("codeLanguage").value, source: el("sourceCode").value }
    });
    applyState(result.state);
    showResult(result);
  } catch (error) {
    try { applyState(await api("/api/state")); }
    catch (_) { /* Keep the current view when state refresh also fails. */ }
    showResult({
      accepted: false,
      label: "SUBMISSION FAILED",
      title: "代码判定未完成",
      message: error.message
    });
  }
  finally { setBusy(false); }
}

function applyState(data) {
  state.data = data;
  state.csrf = data.csrfToken;
  state.acRecords = null;
  render(data);
}

function render(data) {
  el("displayName").textContent = data.user.displayName;
  el("userInitial").textContent = Array.from(data.user.displayName)[0]?.toUpperCase() || "U";
  el("myRating").textContent = Math.round(data.me.rating);
  el("mySolved").textContent = data.me.solvedCount;
  el("myHighest").textContent = data.me.highestSolved ?? "-";
  el("minRating").value = data.ratingRange.min;
  el("maxRating").value = data.ratingRange.max;
  el("emptyRange").textContent = `${data.ratingRange.min} - ${data.ratingRange.max}`;
  renderLeaderboard(data.leaderboard, data.user.id);
  renderCapabilities(data.capabilities);
  renderProblem(data.active);
}

function renderCapabilities(capabilities) {
  const oralReady = capabilities.oralJudge;
  const codeReady = capabilities.codeJudge;
  const codeStatus = capabilities.codeJudgeStatus;
  el("oralAvailability").textContent = oralReady ? "AI 判定服务在线" : "AI 判定服务未配置";
  el("oralAvailability").classList.toggle("unavailable", !oralReady);
  el("oralForm").querySelector("button[type=submit]").disabled = !oralReady;
  el("codeAvailability").textContent = codeStatus?.message || (codeReady ? "代码判定服务已配置" : "代码判定服务未配置");
  el("codeAvailability").classList.toggle("unavailable", !codeReady || codeStatus?.state === "degraded");
  el("codeForm").querySelector("button[type=submit]").disabled = !codeReady;
}

function renderProblem(active) {
  clearInterval(state.giveupTimer);
  el("emptyState").classList.toggle("hidden", Boolean(active));
  el("problemView").classList.toggle("hidden", !active);
  el("challengeTitle").textContent = active ? "当前挑战" : "训练台";
  el("newChallengeBtn").disabled = Boolean(active);
  el("minRating").disabled = Boolean(active);
  el("maxRating").disabled = Boolean(active);
  if (!active) return;

  renderHtmlSection("descriptionSection", "题目描述", active.statement.description);
  renderHtmlSection("inputSection", "输入", active.statement.input);
  renderHtmlSection("outputSection", "输出", active.statement.output);
  renderHtmlSection("hintSection", "提示", active.statement.hint);
  renderSamples(active.statement.samples);
  startGiveupTimer(active.giveupWaitSeconds);
}

function renderHtmlSection(id, title, content) {
  const target = el(id);
  target.replaceChildren();
  target.classList.toggle("hidden", !content);
  if (!content) return;
  const heading = document.createElement("h2");
  heading.textContent = title;
  const body = document.createElement("div");
  body.innerHTML = content;
  target.append(heading, body);
}

function renderSamples(samples) {
  const target = el("samplesSection");
  target.replaceChildren();
  target.classList.toggle("hidden", !samples.length);
  if (!samples.length) return;
  const heading = document.createElement("h2");
  heading.textContent = "样例";
  target.append(heading);
  samples.forEach((sample, index) => {
    const grid = document.createElement("div");
    grid.className = "sample-grid";
    grid.append(sampleBlock(`输入 #${index + 1}`, sample.input), sampleBlock(`输出 #${index + 1}`, sample.output));
    target.append(grid);
  });
}

function sampleBlock(label, value) {
  const wrap = document.createElement("div");
  const name = document.createElement("p");
  name.className = "sample-label";
  name.textContent = label;
  const pre = document.createElement("pre");
  pre.textContent = value;
  wrap.append(name, pre);
  return wrap;
}

function renderLeaderboard(rows, currentUserId) {
  const body = el("leaderboardBody");
  body.replaceChildren();
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    if (row.userId === currentUserId) tr.className = "me";
    [row.rank, row.displayName, Math.round(row.rating), row.solvedCount].forEach((value) => {
      const td = document.createElement("td");
      td.textContent = value;
      tr.append(td);
    });
    body.append(tr);
  });
  el("leaderboardCount").textContent = `${rows.length} 人`;
  el("leaderboardEmpty").classList.toggle("hidden", rows.length > 0);
}

async function openAcRecords(tab) {
  state.activeRecordsTab = tab;
  const dialog = el("acRecordsDialog");
  if (!dialog.open) dialog.showModal();
  switchAcRecordsTab(tab);
  if (state.acRecords) {
    renderAcRecords(state.acRecords);
    return;
  }

  setAcRecordsLoading(true);
  if (!state.acRecordsPromise) state.acRecordsPromise = api("/api/ac-records");
  try {
    state.acRecords = await state.acRecordsPromise;
    renderAcRecords(state.acRecords);
  } catch (error) {
    if (dialog.open) dialog.close();
    showToast(error.message, true);
  } finally {
    state.acRecordsPromise = null;
    setAcRecordsLoading(false);
  }
}

function switchAcRecordsTab(tab) {
  const breakdown = tab === "breakdown";
  state.activeRecordsTab = breakdown ? "breakdown" : "history";
  el("ratingBreakdownTab").classList.toggle("active", breakdown);
  el("ratingBreakdownTab").setAttribute("aria-selected", String(breakdown));
  el("acHistoryTab").classList.toggle("active", !breakdown);
  el("acHistoryTab").setAttribute("aria-selected", String(!breakdown));
  const loading = !el("acRecordsLoading").classList.contains("hidden");
  el("ratingBreakdownPanel").classList.toggle("hidden", loading || !breakdown);
  el("acHistoryPanel").classList.toggle("hidden", loading || breakdown);
  if (!breakdown && !loading) el("historySearch").focus();
}

function setAcRecordsLoading(loading) {
  el("acRecordsLoading").classList.toggle("hidden", !loading);
  switchAcRecordsTab(state.activeRecordsTab);
}

function renderAcRecords(data) {
  const breakdown = data.ratingBreakdown || [];
  el("recordTotal").textContent = data.total || 0;
  el("recordHighest").textContent = breakdown[0]?.rating || "-";
  el("recordLevels").textContent = breakdown.length;
  renderRatingBreakdown(breakdown, data.total || 0);
  el("historySearch").value = "";
  renderFilteredHistory();
}

function renderRatingBreakdown(rows, total) {
  const body = el("ratingBreakdownBody");
  body.replaceChildren();
  const maxCount = Math.max(1, ...rows.map((row) => row.count));
  rows.forEach((row, index) => {
    const tr = document.createElement("tr");
    tr.append(tableCell(index + 1), tableCell(row.rating || "未定级"), tableCell(row.count));

    const shareCell = document.createElement("td");
    const meter = document.createElement("meter");
    meter.min = 0;
    meter.max = maxCount;
    meter.value = row.count;
    meter.setAttribute("aria-label", `${row.rating || "未定级"} 难度通过 ${row.count} 题`);
    const percent = document.createElement("span");
    percent.textContent = total ? `${Math.round((row.count / total) * 100)}%` : "0%";
    shareCell.append(meter, percent);
    tr.append(shareCell);
    body.append(tr);
  });
  el("ratingBreakdownEmpty").classList.toggle("hidden", rows.length > 0);
}

function renderFilteredHistory() {
  if (!state.acRecords) return;
  const query = el("historySearch").value.trim().toLocaleLowerCase();
  const history = (state.acRecords.history || []).filter((item) => {
    if (!query) return true;
    return `${item.cfId} ${item.title} ${item.rating ?? ""}`.toLocaleLowerCase().includes(query);
  });
  renderAcHistory(history, Boolean(query));
}

function renderAcHistory(history, filtered) {
  const body = el("acHistoryBody");
  body.replaceChildren();
  history.forEach((item) => {
    const tr = document.createElement("tr");

    const problemCell = document.createElement("td");
    const problemLink = externalLink(`${item.cfId} ${item.title}`, item.codeforcesUrl);
    problemLink.className = "history-problem";
    problemCell.append(problemLink);

    const methodCell = document.createElement("td");
    const method = document.createElement("span");
    method.className = "method-badge";
    method.textContent = acceptedMethod(item);
    methodCell.append(method);

    const actionsCell = document.createElement("td");
    actionsCell.className = "history-links";
    actionsCell.append(externalLink("CF", item.codeforcesUrl), externalLink("题解", item.solutionUrl));
    if (item.submissionUrl) actionsCell.append(externalLink("提交", item.submissionUrl));

    tr.append(
      problemCell,
      tableCell(item.rating ?? "-"),
      methodCell,
      tableCell(formatAcceptedAt(item.acceptedAt)),
      actionsCell
    );
    body.append(tr);
  });
  el("historyResultCount").textContent = `${history.length} 道题`;
  el("acHistoryEmpty").textContent = filtered ? "没有匹配的 AC 记录" : "暂无计分 AC 记录";
  el("acHistoryEmpty").classList.toggle("hidden", history.length > 0);
}

function tableCell(value) {
  const td = document.createElement("td");
  td.textContent = value;
  return td;
}

function externalLink(label, href) {
  const link = document.createElement("a");
  link.href = href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = label;
  return link;
}

function acceptedMethod(item) {
  if (item.verdict === "LLM_ACCEPTED") return "静态审核";
  return item.method === "code" ? "代码 AC" : "做法审核";
}

function formatAcceptedAt(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(date);
}

function startGiveupTimer(initialSeconds) {
  let remaining = Math.max(0, initialSeconds);
  const update = () => {
    const button = el("giveUpBtn");
    button.disabled = remaining > 0;
    button.textContent = remaining > 0 ? `${remaining}s 后可放弃` : "放弃题目";
    remaining = Math.max(0, remaining - 1);
  };
  update();
  state.giveupTimer = setInterval(update, 1000);
}

function showResult(result) {
  const accepted = Boolean(result.accepted);
  const resolved = result.resolved;
  el("resultAccent").classList.toggle("rejected", !accepted);
  el("resultLabel").textContent = result.label || (accepted ? "ACCEPTED" : "REVIEW RESULT");
  el("resultTitle").textContent = result.title || (accepted ? "通过" : (resolved ? "本轮结束" : "还需要修改"));
  el("resultMessage").textContent = result.message || "";
  const reveal = el("problemReveal");
  reveal.replaceChildren();
  const links = el("resultLinks");
  links.replaceChildren();
  if (resolved) {
    addDefinition(reveal, "题目", `${resolved.cfId} ${resolved.title}`);
    addDefinition(reveal, "难度", resolved.rating ?? "未知");
    addDefinition(reveal, "标签", resolved.tags.length ? resolved.tags.join(", ") : "无");
    addLink(links, "Codeforces", resolved.codeforcesUrl);
    addLink(links, "洛谷题面", resolved.luoguUrl);
    addLink(links, "查看题解", resolved.solutionUrl);
  }
  if (result.verdict) {
    addDefinition(reveal, "Verdict", result.verdict.message);
    if (result.verdict.timeMs != null) addDefinition(reveal, "耗时", `${result.verdict.timeMs} ms`);
    if (result.verdict.memoryKb != null) addDefinition(reveal, "内存", `${result.verdict.memoryKb} KB`);
  }
  el("resultDialog").showModal();
}

function addDefinition(list, term, description) {
  const dt = document.createElement("dt");
  const dd = document.createElement("dd");
  dt.textContent = term;
  dd.textContent = description;
  list.append(dt, dd);
}

function addLink(container, label, href) {
  const link = document.createElement("a");
  link.href = href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = label;
  container.append(link);
}

function populateRatings() {
  for (let rating = 800; rating <= 4000; rating += 100) {
    [el("minRating"), el("maxRating")].forEach((select) => {
      const option = document.createElement("option");
      option.value = rating;
      option.textContent = rating;
      select.append(option);
    });
  }
  el("minRating").value = "1900";
  el("maxRating").value = "2600";
}

function handleEditorTab(event) {
  if (event.key !== "Tab") return;
  event.preventDefault();
  const input = event.currentTarget;
  const start = input.selectionStart;
  input.value = `${input.value.slice(0, start)}    ${input.value.slice(input.selectionEnd)}`;
  input.selectionStart = input.selectionEnd = start + 4;
}

async function api(path, options = {}) {
  const headers = { Accept: "application/json" };
  if (options.method === "POST") {
    headers["Content-Type"] = "application/json";
    if (state.csrf) headers["X-CSRF-Token"] = state.csrf;
  }
  const response = await fetch(path, {
    method: options.method || "GET",
    headers,
    credentials: "same-origin",
    body: options.body === undefined ? undefined : JSON.stringify(options.body)
  });
  let data;
  try { data = await response.json(); }
  catch (_) { data = { message: "服务返回了无法识别的响应。" }; }
  if (!response.ok) {
    const error = new Error(data.message || "请求失败。")
    error.status = response.status;
    throw error;
  }
  return data;
}

function setBusy(busy, text = "处理中") {
  state.busy = busy;
  el("busyText").textContent = text;
  el("busyLayer").classList.toggle("hidden", !busy);
}

function showToast(message, isError = false) {
  const toast = el("toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.remove("show"), 3600);
}
