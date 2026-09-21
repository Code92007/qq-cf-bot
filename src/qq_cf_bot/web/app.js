const state = {
  data: null,
  csrf: "",
  busy: false,
  toastTimer: null,
  giveupTimer: null,
  acRecords: null,
  acRecordsPromise: null,
  activeRecordsTab: "breakdown",
  viewMode: "single",
  contestTimer: null,
  drafts: new Map(),
  currentDraftCf: "",
  singleDraft: { oral: "", code: "" }
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
  el("singleModeTab").addEventListener("click", () => switchTrainingMode("single"));
  el("contestModeTab").addEventListener("click", () => switchTrainingMode("contest"));
  el("oralTab").addEventListener("click", () => switchSubmission("oral"));
  el("codeTab").addEventListener("click", () => switchSubmission("code"));
  el("loginForm").addEventListener("submit", submitLogin);
  el("registerForm").addEventListener("submit", submitRegister);
  el("logoutBtn").addEventListener("click", logout);
  el("newChallengeForm").addEventListener("submit", newChallenge);
  el("specificProblemBtn").addEventListener("click", openSpecificProblem);
  el("specificProblemForm").addEventListener("submit", shareChallenge);
  el("contestSessionForm").addEventListener("submit", startContestSession);
  el("endContestBtn").addEventListener("click", endContestSession);
  el("contestProblems").addEventListener("click", selectContestProblem);
  el("cancelSpecificProblemBtn").addEventListener("click", () => el("specificProblemDialog").close());
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
  clearInterval(state.contestTimer);
  if (el("acRecordsDialog").open) el("acRecordsDialog").close();
  if (el("specificProblemDialog").open) el("specificProblemDialog").close();
  el("appView").classList.add("hidden");
  el("authView").classList.remove("hidden");
}

function showApp(data) {
  state.data = data;
  state.csrf = data.csrfToken;
  state.acRecords = null;
  if (data.contestSession || (data.lastContestSession && !data.active)) state.viewMode = "contest";
  el("authView").classList.add("hidden");
  el("appView").classList.remove("hidden");
  render(data);
}

function switchTrainingMode(mode) {
  if (mode !== "single" && mode !== "contest") return;
  saveCurrentDraft();
  state.viewMode = mode;
  if (state.data) render(state.data);
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
    state.singleDraft = { oral: "", code: "" };
    el("solutionText").value = "";
    el("sourceCode").value = "";
  } catch (error) { showToast(error.message, true); }
  finally { setBusy(false); }
}

function openSpecificProblem() {
  if (el("specificProblemBtn").disabled) return;
  const dialog = el("specificProblemDialog");
  if (!dialog.open) dialog.showModal();
  el("specificProblemId").focus();
}

async function shareChallenge(event) {
  event.preventDefault();
  const problemId = el("specificProblemId").value.trim();
  el("specificProblemDialog").close();
  setBusy(true, "正在准备指定题面");
  try {
    const result = await api("/api/challenges/share", {
      method: "POST",
      body: { problemId }
    });
    applyState(result.state);
    state.singleDraft = { oral: "", code: "" };
    el("specificProblemId").value = "";
    el("solutionText").value = "";
    el("sourceCode").value = "";
    switchSubmission("oral");
  } catch (error) { showToast(error.message, true); }
  finally { setBusy(false); }
}

async function startContestSession(event) {
  event.preventDefault();
  setBusy(true, "正在拉取整场题目");
  try {
    const result = await api("/api/contest-sessions", {
      method: "POST",
      body: {
        category: el("contestCategory").value,
        contestId: el("contestId").value.trim()
      }
    });
    state.drafts.clear();
    state.currentDraftCf = "";
    state.viewMode = "contest";
    applyState(result.state);
    el("contestId").value = "";
  } catch (error) { showToast(error.message, true); }
  finally { setBusy(false); }
}

async function selectContestProblem(event) {
  const button = event.target.closest("button[data-cf-id]");
  if (!button || button.classList.contains("current") || !state.data?.contestSession) return;
  saveCurrentDraft();
  setBusy(true, `正在载入 ${button.dataset.cfId}`);
  try {
    const result = await api("/api/contest-sessions/select", {
      method: "POST",
      body: { cfId: button.dataset.cfId }
    });
    applyState(result.state);
  } catch (error) { showToast(error.message, true); }
  finally { setBusy(false); }
}

async function endContestSession() {
  if (!state.data?.contestSession) return;
  saveCurrentDraft();
  setBusy(true, "正在结算套题");
  try {
    const result = await api("/api/contest-sessions/end", { method: "POST", body: {} });
    applyState(result.state);
    showContestSummary(result.ended);
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
    const path = state.viewMode === "contest" ? "/api/contest-sessions/oral" : "/api/challenges/oral";
    const result = await api(path, { method: "POST", body: { solution: el("solutionText").value } });
    applyState(result.state);
    showResult(result);
  } catch (error) { showToast(error.message, true); }
  finally { setBusy(false); }
}

async function submitCode(event) {
  event.preventDefault();
  setBusy(true, "正在进行代码判定");
  try {
    const path = state.viewMode === "contest" ? "/api/contest-sessions/code" : "/api/challenges/code";
    const result = await api(path, {
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
  const contestMode = state.viewMode === "contest";
  const contestSession = data.contestSession;
  const displayedContest = contestSession || data.lastContestSession;
  const active = contestMode ? contestSession?.active : data.active;
  el("displayName").textContent = data.user.displayName;
  el("userInitial").textContent = Array.from(data.user.displayName)[0]?.toUpperCase() || "U";
  el("myRating").textContent = Math.round(data.me.rating);
  el("mySolved").textContent = data.me.solvedCount;
  el("myHighest").textContent = data.me.highestSolved ?? "-";
  el("minRating").value = data.ratingRange.min;
  el("maxRating").value = data.ratingRange.max;
  el("singleModeTab").classList.toggle("active", !contestMode);
  el("singleModeTab").setAttribute("aria-selected", String(!contestMode));
  el("contestModeTab").classList.toggle("active", contestMode);
  el("contestModeTab").setAttribute("aria-selected", String(contestMode));
  el("newChallengeForm").classList.toggle("hidden", contestMode);
  el("contestSessionForm").classList.toggle("hidden", !contestMode);
  el("emptyTitle").textContent = contestMode ? "等待开场" : "等待抽题";
  el("emptyRange").textContent = contestMode
    ? "选择 Div. 2、Div. 1 或 Gym"
    : `${data.ratingRange.min} - ${data.ratingRange.max}`;
  [el("contestCategory"), el("contestId"), el("startContestBtn")].forEach((control) => {
    control.disabled = Boolean(contestSession);
  });
  renderLeaderboard(data.leaderboard, data.user.id);
  renderCapabilities(data.capabilities);
  renderContestBoard(contestMode ? displayedContest : null);
  renderProblem(active, contestMode, contestSession);
  restoreEditor(active, contestMode);
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

function renderProblem(active, contestMode, contestSession) {
  clearInterval(state.giveupTimer);
  el("emptyState").classList.toggle("hidden", Boolean(active));
  el("problemView").classList.toggle("hidden", !active);
  el("challengeTitle").textContent = contestMode ? "套题训练" : (active ? "当前挑战" : "训练台");
  el("newChallengeBtn").disabled = Boolean(state.data?.active);
  el("specificProblemBtn").disabled = Boolean(state.data?.active);
  el("minRating").disabled = Boolean(state.data?.active);
  el("maxRating").disabled = Boolean(state.data?.active);
  el("challengeMode").textContent = contestMode ? "套题 VP · 不计榜单" : "专项练习 · 不计榜单";
  el("challengeMode").classList.toggle("hidden", !active || (!contestMode && active.ranked !== false));
  el("giveUpBtn").classList.toggle("hidden", contestMode);
  const identity = el("contestProblemIdentity");
  identity.classList.toggle("hidden", !contestMode || !active?.problem);
  identity.textContent = active?.problem ? `${active.problem.cfId} · ${active.problem.title}` : "";
  if (contestMode && contestSession && !active) {
    el("emptyTitle").textContent = "选择一道题";
    el("emptyRange").textContent = "套题计时仍在继续";
  } else if (contestMode && state.data?.lastContestSession && !active) {
    el("emptyTitle").textContent = "上一场已结束";
    el("emptyRange").textContent = "时间拆分保留在上方，可开始下一场";
  }
  if (!active) return;

  renderHtmlSection("descriptionSection", "题目描述", active.statement.description);
  renderHtmlSection("inputSection", "输入", active.statement.input);
  renderHtmlSection("outputSection", "输出", active.statement.output);
  renderHtmlSection("hintSection", "提示", active.statement.hint);
  renderSamples(active.statement.samples);
  if (!contestMode) startGiveupTimer(active.giveupWaitSeconds);
}

function renderContestBoard(contestSession) {
  clearInterval(state.contestTimer);
  el("contestBoard").classList.toggle("hidden", !contestSession);
  if (!contestSession) return;
  const ended = contestSession.status === "ended";
  const category = { div2: "DIV. 2", div1: "DIV. 1", gym: "GYM" }[contestSession.category] || "CF";
  el("contestMeta").textContent = `${category} · #${contestSession.contestId} · ${ended ? "REVIEW" : "VP"}`;
  el("contestName").textContent = contestSession.contestName;
  el("vpDuration").textContent = `/ ${formatClock(contestSession.durationSeconds)}`;
  el("contestCategory").value = contestSession.category;

  el("endContestBtn").classList.toggle("hidden", ended);
  const renderedAt = Date.now();
  const updateClock = () => {
    const started = Date.parse(contestSession.startedAt);
    const elapsed = ended || Number.isNaN(started)
      ? contestSession.elapsedSeconds
      : Math.max(0, Math.floor((Date.now() - started) / 1000));
    el("vpClock").textContent = formatClock(elapsed);
    el("vpClock").classList.toggle("overtime", contestSession.durationSeconds > 0 && elapsed > contestSession.durationSeconds);
    const current = contestSession.problems.find((problem) => problem.current);
    const currentSplit = current
      ? el("contestProblems").querySelector(`[data-split-cf-id="${current.cfId}"]`)
      : null;
    if (!ended && currentSplit) {
      currentSplit.textContent = formatProblemSplit(current, false, Math.max(0, Math.floor((Date.now() - renderedAt) / 1000)));
    }
  };
  updateClock();
  if (!ended) state.contestTimer = setInterval(updateClock, 1000);

  const container = el("contestProblems");
  container.replaceChildren();
  contestSession.problems.forEach((problem) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.cfId = problem.cfId;
    button.className = "contest-problem-row";
    button.classList.toggle("current", problem.current);
    button.classList.toggle("oral-ac", problem.oralAcSeconds != null);
    button.classList.toggle("code-ac", problem.codeAcSeconds != null);
    button.classList.toggle("readonly", ended);
    if (ended) button.setAttribute("aria-disabled", "true");

    const problemCell = document.createElement("span");
    problemCell.className = "contest-problem-name";
    const index = document.createElement("strong");
    index.textContent = problem.index;
    const name = document.createElement("span");
    name.textContent = problem.title;
    const rating = document.createElement("small");
    rating.textContent = problem.rating ? `${problem.rating}` : "未定级";
    problemCell.append(index, name, rating);

    const oral = timingCell(problem.oralAcSeconds, problem.oralAttempts, "口胡中");
    const code = timingCell(problem.codeAcSeconds, problem.codeAttempts, "未 AC");
    const split = document.createElement("span");
    split.className = "time-split";
    split.dataset.splitCfId = problem.cfId;
    split.textContent = formatProblemSplit(problem, ended);
    button.append(problemCell, oral, code, split);
    container.append(button);
  });
}

function formatProblemSplit(problem, ended, activeExtraSeconds = 0) {
  const thinking = (problem.thinkingSeconds || 0) + (
    problem.current && problem.oralAcSeconds == null && problem.codeAcSeconds == null ? activeExtraSeconds : 0
  );
  const coding = (problem.codingSeconds || 0) + (
    problem.current && problem.oralAcSeconds != null && problem.codeAcSeconds == null ? activeExtraSeconds : 0
  );
  if (problem.codeAcSeconds != null && problem.splitAvailable) {
    return `想 ${formatCompactDuration(thinking)} · 写 ${formatCompactDuration(coding)}`;
  }
  if (problem.codeAcSeconds != null) return "未口胡，无法拆分";
  if (problem.oralAcSeconds != null) {
    return ended
      ? `想 ${formatCompactDuration(thinking)} · 写 ${formatCompactDuration(coding)}（未 AC）`
      : `想 ${formatCompactDuration(thinking)} · 写 ${formatCompactDuration(coding)}`;
  }
  if (problem.openedAt) {
    return ended
      ? `思考 ${formatCompactDuration(thinking)}（未口胡）`
      : `思考 ${formatCompactDuration(thinking)}`;
  }
  return "尚未打开";
}

function timingCell(seconds, attempts, fallback) {
  const cell = document.createElement("span");
  cell.className = "contest-time-cell";
  const value = document.createElement("strong");
  value.textContent = seconds == null ? "--:--:--" : `+${formatClock(seconds)}`;
  const detail = document.createElement("small");
  detail.textContent = attempts ? `${attempts} 次判定` : fallback;
  cell.append(value, detail);
  return cell;
}

function saveCurrentDraft() {
  const draft = { oral: el("solutionText").value, code: el("sourceCode").value };
  if (state.viewMode === "contest" && state.currentDraftCf) state.drafts.set(state.currentDraftCf, draft);
  else state.singleDraft = draft;
}

function restoreEditor(active, contestMode) {
  if (!contestMode) {
    state.currentDraftCf = "";
    el("solutionText").value = state.singleDraft.oral;
    el("sourceCode").value = state.singleDraft.code;
    return;
  }
  const cfId = active?.problem?.cfId || "";
  if (cfId === state.currentDraftCf) return;
  state.currentDraftCf = cfId;
  const draft = state.drafts.get(cfId) || { oral: "", code: "" };
  el("solutionText").value = draft.oral;
  el("sourceCode").value = draft.code;
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

function formatClock(totalSeconds) {
  const value = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const hours = String(Math.floor(value / 3600)).padStart(2, "0");
  const minutes = String(Math.floor((value % 3600) / 60)).padStart(2, "0");
  const seconds = String(value % 60).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

function formatCompactDuration(totalSeconds) {
  if (totalSeconds == null) return "--";
  const value = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  if (value >= 3600) return `${Math.floor(value / 3600)}h ${Math.floor((value % 3600) / 60)}m`;
  return `${Math.floor(value / 60)}m ${value % 60}s`;
}

function showContestSummary(contestSession) {
  const oralCount = contestSession.problems.filter((problem) => problem.oralAcSeconds != null).length;
  const codeCount = contestSession.problems.filter((problem) => problem.codeAcSeconds != null).length;
  showResult({
    accepted: true,
    label: "VP FINISHED",
    title: "套题已结束",
    message: contestSession.contestName
  });
  const reveal = el("problemReveal");
  addDefinition(reveal, "用时", formatClock(contestSession.elapsedSeconds));
  addDefinition(reveal, "口胡 AC", `${oralCount} / ${contestSession.problems.length}`);
  addDefinition(reveal, "代码 AC", `${codeCount} / ${contestSession.problems.length}`);
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
