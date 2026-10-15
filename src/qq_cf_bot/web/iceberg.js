(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const escape = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
  const difficultyNames = ["", "入门", "基础", "进阶", "困难", "挑战"];
  const popularityNames = ["", "非常冷门", "比较少见", "专题常见", "比赛常用", "广泛使用"];
  let atlas = null, visibleTopics = [], category = "all", view = "iceberg", observer = null;
  let searchTimer;
  const dialog = $("topicDialog");
  const normalize = value => value.toLocaleLowerCase().normalize("NFKC").replace(/[_\-–—·/]/g, "").trim();
  function matchesQuery(topic, query) {
    const text = normalize(`${topic.title} ${topic.aliases} ${topic.summary}`);
    // Short abbreviations must start a word; NTT should not match "Segment Tree".
    if (/^[a-z0-9]{2,5}$/.test(query)) return text.split(/[^\p{L}\p{N}]+/u).some(word => word.startsWith(query));
    return text.replace(/\s/g, "").includes(query.replace(/\s/g, ""));
  }

  let mode = "pure", journey = null, journeyError = "", journeyRequest = 0, reviewRequest = 0;
  const dateLabel = stamp => stamp ? new Date(stamp * 1000).toLocaleDateString("zh-CN", {timeZone:"Asia/Shanghai", year:"numeric", month:"2-digit", day:"2-digit"}).replaceAll("/", ".") : "时间未知";
  const topicName = id => atlas.topics.find(t => t.id === id)?.title || id;
  const achievement = topic => journey?.topics[topic.id];
  function isStale(p) { return Boolean(p?.lastAt && journey.now - p.lastAt >= Number($("staleDays").value) * 86400); }
  function matchesProgress(topic) {
    if (mode === "pure" || !journey) return true;
    const p = achievement(topic), filter = $("progressFilter").value;
    return filter === "all" || (filter === "lit" && p.count > 0) || (filter === "unlit" && !p.count) || (filter === "stale" && isStale(p)) || (filter === "unknown" && p.count > 0 && !p.lastAt);
  }
  function topicFootprint(topic) {
    if (mode === "pure" || !journey) return "";
    const p = achievement(topic);
    return `<button type="button" class="topic-footprint" data-topic="${escape(topic.id)}" aria-label="查看${escape(topic.title)}的做题足迹">${p.count ? `<span>✦ ${p.count} 题${isStale(p) ? " · 待复习" : ""}</span><span>点亮 ${dateLabel(p.firstAt)}${p.undated && p.firstAt ? " 起（部分无时间）" : ""}</span><span>最近 AC ${dateLabel(p.lastAt)}</span>` : "<span>○ 尚无关联 AC</span>"}</button>`;
  }
  function renderJourney() {
    $("journeyPanel").hidden = mode === "pure";
    $("journeyContent").hidden = !journey;
    $("achievementFilters").hidden = mode === "pure" || !journey;
    document.querySelectorAll("[data-mode]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
    if (mode === "pure") { $("reviewResults").hidden = true; return; }
    if (!journey) {
      $("journeyStatus").innerHTML = journeyError || "正在寻找你的足迹…";
      return;
    }
    const {summary:s, wall:w} = journey;
    const sync = w.connected ? `OJ Wall 上次同步 ${dateLabel(w.lastSync)}${w.stale ? " · 缓存已过期，请到区域赛页重新同步" : ""}${w.error ? " · " + escape(w.error) : ""}${!w.knowledgeReady ? " · AC 时间尚待同步" : ""}` : "连接 OJ Wall 后，这里会合并你的历史 AC";
    $("journeyStatus").innerHTML = `${escape(journey.user.displayName)}的成就墙 · ${sync}`;
    $("journeyStats").innerHTML = [[s.lit,"个知识点被点亮"],[s.solved,"道去重 AC 题目"],[s.mapped,"道题已有知识点关联"],[s.solved - s.mapped,"道题待补标签"]].map(([count,label]) => `<div><strong>${count}</strong><span>${label}</span></div>`).join("");
    const prior = $("memoryYear").value;
    $("memoryYear").innerHTML = '<option value="all">整个竞赛生涯</option>' + Object.keys(journey.memories).filter(y => y !== "all").sort().reverse().map(y => `<option value="${y}">${y} 年</option>`).join("");
    if (journey.memories[prior]) $("memoryYear").value = prior;
    renderMemory();
  }
  function memorySentences(m) {
    const year = $("memoryYear").value;
    const title = year === "all" ? "整个竞赛生涯" : year + " 年";
    return [
      [title, `${m.solved} 道题留下 AC 足迹，${m.activeDays} 天写下新的答案。`],
      ["初次相遇", `点亮 ${m.newTopics} 个新知识点。${m.deepest ? `最深的一次，来到「${topicName(m.deepest)}」。` : "下一次探索，正在等你。"}`],
      ["总会回来的地方", m.favorite ? `「${topicName(m.favorite.topic)}」出现在 ${m.favorite.count} 道 AC 题里。` : "关联知识点后，你最常走的方向会在这里浮现。"],
      ["最亮的那一天", m.peak ? `${m.peak.date}，你 AC 了 ${m.peak.count} 道不同的题。` : "有原始 AC 时间后，这一天会被记住。"],
      ["久别重逢", m.comeback ? `相隔 ${m.comeback.days} 天，${m.comeback.date} 再次遇见「${topicName(m.comeback.topic)}」。` : "每一次重逢，都在延长你的航线。"],
      ["最早保存的一份 AC", m.first ? `${m.first.date} · ${m.first.title}` : "旧记录缺少时间，保留足迹，等待补全。"]
    ];
  }
  function renderMemory() {
    if (!journey) return;
    const m = journey.memories[$("memoryYear").value] || journey.memories.all;
    $("memoryCards").innerHTML = memorySentences(m).map(([title,body],i) => `<article><span class="memory-index">0${i+1}</span><h3>${escape(title)}</h3><p>${escape(body)}</p></article>`).join("");
    $("memoryTimeline").innerHTML = m.timeline.map(t => `<li><time>${dateLabel(t.at)}</time><button type="button" data-memory-topic="${escape(t.topic)}">${escape(topicName(t.topic))}</button></li>`).join("") || '<li>暂无有时间的点亮记录。</li>';
  }
  async function loadJourney() {
    const request = ++journeyRequest;
    const teams = $("includeTeams").checked;
    journeyError = "";
    try {
      const response = await fetch("/api/iceberg/progress" + (teams ? "?teams=1" : ""), {cache:"no-store"});
      if (request !== journeyRequest) return;
      if (response.status === 401) { journey = null; journeyError = '<a href="/?next=iceberg">登录 CF Bot</a>，查看属于你的点亮时间和竞赛回忆。纯享版随时可以浏览。'; }
      else {
        if (!response.ok) throw new Error("无法读取做题记录");
        const data = await response.json();
        if (request !== journeyRequest) return;
        journey = data;
      }
    } catch (error) { if (request === journeyRequest) { journey = null; journeyError = '做题记录暂未加载成功，点击“刷新记录”重试。'; } }
    if (request !== journeyRequest) return;
    renderJourney(); render();
    if (dialog.open && dialog.dataset.topic) openTopic(dialog.dataset.topic, false);
  }
  function footprintDetails(topic) {
    if (mode === "pure" || !journey) return "";
    const p = achievement(topic), records = new Map(journey.problems.map(r => [r.key,r]));
    const examples = p.problemKeys.map(k => records.get(k));
    return `<section class="footprint-details"><h3>${p.count ? "✦ 这片海，你来过" : "还没有关联的 AC 足迹"}</h3><div class="footprint-dates"><p>首次点亮<strong>${dateLabel(p.firstAt)}</strong></p><p>最近一次 AC<strong>${dateLabel(p.lastAt)}</strong></p><p>去重题目<strong>${p.count} 道</strong></p></div>${p.undated ? `<p class="journey-note">${p.undated} 道题缺少原始时间；已知日期仅代表目前保存的最早 / 最近记录。</p>` : ""}<details ${p.count ? "open" : ""}><summary>关联题目与时间依据</summary><ul class="footprint-problems">${examples.map(r => `<li><div>${r.url ? `<a href="${escape(r.url)}" target="_blank" rel="noopener noreferrer">${escape(r.key)} · ${escape(r.title)} ↗</a>` : `<span>${escape(r.key)} · ${escape(r.title)}</span>`}<small>${escape(r.sources.join(" / "))}${r.manualTopicIds.includes(topic.id) ? " · 补充关联" : " · 标签匹配"}</small></div><p>首次 ${dateLabel(r.firstAt)}<br>最近 ${dateLabel(r.lastAt)}</p>${r.manualTopicIds.includes(topic.id) ? `<button type="button" data-unlink="${escape(r.key)}" class="quiet">移除补充关联</button>` : ""}</li>`).join("") || '<li>平台标签不够细时，可以在下方补充关联。</li>'}</ul></details><details class="manual-link"><summary>补充关联：这道已 AC 的题用到了它</summary><p class="journey-note">选择历史 AC 题目，使用原始 AC 时间点亮。可以把同一道题关联到多个知识点。</p><label>搜索已 AC 题目<input type="search" id="linkProblemSearch" placeholder="题号或题名" maxlength="100"></label><select id="linkProblem" aria-label="选择已 AC 题目">${linkOptions("")}</select><button id="saveTopicLink" type="button" class="quiet">关联到这个知识点</button><p id="linkStatus" role="status"></p></details><button type="button" id="recommendThisTopic" class="quiet">找几道这个知识点的题 ↗</button></section>`;
  }
  function linkOptions(query) {
    return '<option value="">选择一道题目</option>' + journey.problems.filter(r => `${r.key} ${r.title}`.toLowerCase().includes(query.toLowerCase())).slice(0,100).map(r => `<option value="${escape(r.key)}">${escape(r.key)} · ${escape(r.title)}</option>`).join("");
  }
  async function saveLink(key, remove=false) {
    const topic = dialog.dataset.topic;
    try {
      const response = await fetch("/api/iceberg/link", {method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":journey.csrfToken},body:JSON.stringify({problemKey:key,topicId:topic,teams:$("includeTeams").checked,remove})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "关联失败");
      await loadJourney();
    } catch (error) { if ($("linkStatus")) $("linkStatus").textContent = error.message; }
  }
  async function recommend(topic) {
    const request = ++reviewRequest;
    $("reviewResults").hidden = false;
    $("reviewResults").textContent = `正在为「${topic.title}」挑选题目…`;
    try {
      const query = new URLSearchParams({topic:topic.id,minRating:$("reviewMin").value,maxRating:$("reviewMax").value,teams:$("includeTeams").checked ? "1" : "0"});
      const response = await fetch("/api/iceberg/recommendations?" + query);
      const data = await response.json();
      if (request !== reviewRequest || mode === "pure") return;
      if (!response.ok) throw new Error(data.message || "推荐暂不可用");
      $("reviewResults").innerHTML = `<h3>下一次相遇 · ${escape(topic.title)}</h3><p>按标签与难度筛选，排除当前记录中的已 AC 题目。${data.total} 道候选题。</p><div>${data.problems.map(r => `<a href="${escape(r.url)}" target="_blank" rel="noopener noreferrer"><strong>${escape(r.key.replace("codeforces:", "CF"))} · ${escape(r.title)}</strong><span>${r.rating} · ${escape(r.tags.join(" / "))} ↗</span></a>`).join("") || '<p>当前缓存中暂无匹配题目。可以放宽难度，或通过知识点资料寻找专题题单。</p>'}</div>`;
      $("reviewResults").scrollIntoView({block:"center",behavior:"smooth"});
    } catch (error) { if (request === reviewRequest) $("reviewResults").textContent = error.message; }
  }

  function readFilters() {
    const params = new URLSearchParams(location.search);
    $("topicSearch").value = (params.get("q") || "").slice(0, 100);
    category = atlas.categories.some(c => c.id === params.get("category")) ? params.get("category") : "all";
    $("difficultyFilter").value = /^[1-5]$/.test(params.get("difficulty")) ? params.get("difficulty") : "all";
    view = params.get("view") === "list" ? "list" : "iceberg";
    mode = params.get("mode") === "achievements" ? "achievements" : "pure";
    $("progressFilter").value = ["lit","unlit","stale","unknown"].includes(params.get("progress")) ? params.get("progress") : "all";
    $("staleDays").value = ["30","90","180","365"].includes(params.get("days")) ? params.get("days") : "180";
    $("includeTeams").checked = params.get("teams") === "1";
  }

  function writeURL() {
    const params = new URLSearchParams();
    const query = $("topicSearch").value.trim();
    if (query) params.set("q", query);
    if (category !== "all") params.set("category", category);
    if ($("difficultyFilter").value !== "all") params.set("difficulty", $("difficultyFilter").value);
    if (view !== "iceberg") params.set("view", view);
    if (mode !== "pure") {
      params.set("mode", mode);
      if ($("progressFilter").value !== "all") params.set("progress", $("progressFilter").value);
      if ($("staleDays").value !== "180") params.set("days", $("staleDays").value);
      if ($("includeTeams").checked) params.set("teams", "1");
    }
    if (dialog.open && dialog.dataset.topic) params.set("topic", dialog.dataset.topic);
    const queryString = params.toString();
    history.replaceState(null, "", location.pathname + (queryString ? "?" + queryString : "") + location.hash);
  }

  function setActiveDepth(id) {
    document.querySelectorAll(".depth-link").forEach(link => {
      if (link.dataset.tier === String(id)) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  }

  function topicMarkup(topic) {
    const color = atlas.categories.find(c => c.id === topic.category).color;
    return `<div class="topic${topic.source === "OI Wiki" ? "" : " supplementary"}${mode === "achievements" && journey ? " has-footprint" + (achievement(topic).count ? " lit" : " unlit") + (isStale(achievement(topic)) ? " stale" : "") : ""}" id="topic-${escape(topic.id)}" style="--category-color:${escape(color)}"><a href="${escape(topic.url)}" target="_blank" rel="noopener noreferrer" title="${escape(topic.title)} · ${escape(topic.source)}${topic.kind === "implementation" ? "（实现参考）" : ""}"><i class="topic-dot" aria-hidden="true"></i>${escape(topic.title)}</a><button class="topic-info" type="button" data-topic="${escape(topic.id)}" aria-label="了解${escape(topic.title)}"></button>${topicFootprint(topic)}</div>`;
  }

  function render() {
    const query = normalize($("topicSearch").value.trim());
    const difficulty = $("difficultyFilter").value;
    visibleTopics = atlas.topics.filter(topic =>
      (category === "all" || topic.category === category) &&
      (difficulty === "all" || String(topic.difficulty) === difficulty) &&
      (!query || matchesQuery(topic, query)) && matchesProgress(topic)
    );
    if (mode === "achievements" && journey && $("progressFilter").value === "stale") visibleTopics.sort((a,b) => achievement(a).lastAt - achievement(b).lastAt);
    $("icebergMap").classList.toggle("list-view", view === "list");
    $("icebergMap").classList.toggle("achievement-view", mode === "achievements" && Boolean(journey));
    document.querySelectorAll("[data-view]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.view === view)));
    document.querySelectorAll("[data-category]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.category === category)));
    $("icebergMap").innerHTML = atlas.tiers.map(tier => {
      const topics = visibleTopics.filter(topic => topic.tier === tier.id);
      return `<section class="depth-section depth-${tier.id}" id="depth-${tier.id}" aria-labelledby="depth-title-${tier.id}"${topics.length ? "" : " hidden"}><header class="depth-header"><p class="depth-number"><strong>${String(tier.id).padStart(2, "0")}</strong> / ${topics.length} 个知识点</p><h3 id="depth-title-${tier.id}">${escape(tier.name)}</h3><span class="depth-english">${escape(tier.english)}</span><p title="${escape(tier.description)}">${escape(tier.tagline)}</p></header><div class="topic-cluster">${topics.map(topicMarkup).join("")}</div></section>`;
    }).join("");
    $("depthNav").innerHTML = atlas.tiers.map(tier => {
      const count = visibleTopics.filter(topic => topic.tier === tier.id).length;
      return `<a class="depth-link${count ? "" : " disabled"}" href="#depth-${tier.id}" data-tier="${tier.id}"${count ? "" : ' aria-disabled="true"'}><span>${String(tier.id).padStart(2, "0")}</span>${escape(tier.name)}</a>`;
    }).join("");
    $("resultSummary").innerHTML = `发现 <strong>${visibleTopics.length}</strong> / ${atlas.topics.length} 个知识点${query || category !== "all" || difficulty !== "all" || (mode === "achievements" && $("progressFilter").value !== "all") ? " · 筛选后的水下世界" : " · 从熟悉的地方，走向未知"}`;
    $("resetFilters").hidden = !(query || category !== "all" || difficulty !== "all" || (mode === "achievements" && $("progressFilter").value !== "all"));
    $("noResults").hidden = visibleTopics.length !== 0;
    $("icebergMap").hidden = visibleTopics.length === 0;
    $("randomTopic").disabled = visibleTopics.length === 0;
    if (observer) observer.disconnect();
    if ("IntersectionObserver" in window) {
      observer = new IntersectionObserver(entries => {
        const entered = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (entered.length) setActiveDepth(entered[0].target.id.replace("depth-", ""));
      }, { rootMargin: "-10% 0px -55% 0px", threshold: 0 });
      document.querySelectorAll(".depth-section:not([hidden])").forEach(section => observer.observe(section));
    }
    setActiveDepth(visibleTopics[0]?.tier || 0);
  }

  function openTopic(id, updateURL = true) {
    const topic = atlas.topics.find(item => item.id === id);
    if (!topic) return;
    const field = atlas.categories.find(c => c.id === topic.category);
    const tier = atlas.tiers.find(t => t.id === topic.tier);
    const related = atlas.topics.filter(item => item.category === topic.category && item.id !== id)
      .sort((a, b) => Math.abs(a.tier - topic.tier) - Math.abs(b.tier - topic.tier) || a.tier - b.tier).slice(0, 4);
    const references = (topic.references || []).map(ref => `<a class="topic-reference" href="${escape(ref.url)}" target="_blank" rel="noopener noreferrer"><span><small>${ref.kind === "implementation" ? "实现参考" : "延伸阅读"}</small>${escape(ref.title)}</span><span aria-hidden="true">↗</span></a>`).join("");
    $("topicDetails").innerHTML = `<p class="atlas-kicker">${String(topic.tier).padStart(2, "0")} / ${escape(tier.name)} · ${escape(field.name)}</p><h2 id="dialogTitle">${escape(topic.title)}</h2><p class="topic-description">${escape(topic.summary)}</p><div class="topic-metrics"><div><small>理解门槛 · 编辑估计</small><strong><span class="difficulty-bars" aria-hidden="true">${Array.from({length: 5}, (_, i) => `<i${i < topic.difficulty ? ' class="filled"' : ""}></i>`).join("")}</span>${topic.difficulty} / 5 · ${difficultyNames[topic.difficulty]}</strong></div><div><small>竞赛常见程度 · 编辑估计</small><strong>${popularityNames[topic.popularity]}</strong></div></div>${topic.aliases ? `<p class="dialog-alias">也可以搜：${escape(topic.aliases)}</p>` : ""}<a class="topic-reading primary" href="${escape(topic.url)}" target="_blank" rel="noopener noreferrer">${topic.kind === "implementation" ? "查看实现参考" : "阅读知识点"} · ${escape(topic.source)}<span aria-hidden="true">↗</span></a><p class="source-note">${topic.kind === "implementation" ? "这份链接以代码实现为主，适合已有相关背景时进一步参考。" : "在新标签页打开资料，冰山会留在这里。"}</p>${references ? `<div class="topic-references" aria-label="补充资料">${references}</div>` : ""}${footprintDetails(topic)}<div class="related-topics"><p>沿这个方向，再看看</p><div>${related.map(item => `<button type="button" data-related="${escape(item.id)}">${escape(item.title)}</button>`).join("")}</div></div>`;
    dialog.dataset.topic = id;
    if (!dialog.open) dialog.showModal();
    if (updateURL) writeURL();
  }

  function resetFilters() {
    clearTimeout(searchTimer);
    $("topicSearch").value = "";
    $("difficultyFilter").value = "all";
    category = "all";
    $("progressFilter").value = "all";
    render();
    writeURL();
  }

  async function load() {
    $("loadError").hidden = true;
    try {
      const response = await fetch("/iceberg-data.json?v=5");
      if (!response.ok) throw new Error("Atlas unavailable");
      const data = await response.json();
      if (!Array.isArray(data.topics) || !data.topics.length || !Array.isArray(data.tiers) || !Array.isArray(data.categories)) throw new Error("Invalid atlas");
      for (const topic of data.topics) {
        const url = new URL(topic.url);
        if (url.protocol !== "https:" || !/^[a-z0-9-]+$/.test(topic.id) || !data.categories.some(c => c.id === topic.category) || !data.tiers.some(t => t.id === topic.tier)) throw new Error("Invalid topic");
        if (topic.references !== undefined && (!Array.isArray(topic.references) || topic.references.some(ref => !ref.title || new URL(ref.url).protocol !== "https:" || !["article", "implementation"].includes(ref.kind)))) throw new Error("Invalid reference");
      }
      atlas = data;
      $("topicCount").textContent = atlas.topics.length;
      $("categoryFilters").innerHTML = `<button type="button" data-category="all" aria-pressed="true">全部领域</button>` + atlas.categories.map(field => `<button type="button" data-category="${escape(field.id)}" aria-pressed="false" style="--category-color:${escape(field.color)}"><i aria-hidden="true"></i>${escape(field.name)}</button>`).join("");
      readFilters();
      renderJourney();
      render();
      if (mode === "achievements") loadJourney();
      const linkedTopic = new URLSearchParams(location.search).get("topic");
      if (linkedTopic) openTopic(linkedTopic, false);
      if (/^#depth-[1-8]$/.test(location.hash)) {
        const section = document.querySelector(location.hash);
        if (section && !section.hidden) section.scrollIntoView();
      }
    } catch (error) {
      $("icebergMap").hidden = true;
      $("loadError").hidden = false;
      $("randomTopic").disabled = true;
      $("resultSummary").textContent = "地图未能加载，请重试。";
    }
  }

  $("atlasFilters").addEventListener("submit", event => { event.preventDefault(); });
  $("topicSearch").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { if (atlas) { render(); writeURL(); } }, 120);
  });
  $("difficultyFilter").addEventListener("change", () => { if (atlas) { render(); writeURL(); } });
  $("categoryFilters").addEventListener("click", event => {
    const button = event.target.closest("[data-category]");
    if (button && atlas) { category = button.dataset.category; render(); writeURL(); }
  });
  document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => {
    if (atlas) { view = button.dataset.view; render(); writeURL(); }
  }));
  $("icebergMap").addEventListener("click", event => {
    const button = event.target.closest("[data-topic]");
    if (button) openTopic(button.dataset.topic);
  });
  $("depthNav").addEventListener("click", event => {
    const link = event.target.closest("[data-tier]");
    if (!link) return;
    if (link.getAttribute("aria-disabled") === "true") { event.preventDefault(); return; }
    setActiveDepth(link.dataset.tier);
  });
  $("topicDetails").addEventListener("click", event => {
    const button = event.target.closest("[data-related]");
    if (button) openTopic(button.dataset.related);
  });
  $("randomTopic").addEventListener("click", () => {
    if (!visibleTopics.length) return;
    const topic = visibleTopics[Math.floor(Math.random() * visibleTopics.length)];
    document.querySelectorAll(".spotlight").forEach(element => element.classList.remove("spotlight"));
    const element = $("topic-" + topic.id);
    element.classList.add("spotlight");
    element.closest(".depth-section").classList.add("spotlight");
    element.scrollIntoView({block: "center", behavior: "instant"});
    setActiveDepth(topic.tier);
    openTopic(topic.id);
  });
  $("resetFilters").addEventListener("click", resetFilters);
  $("emptyReset").addEventListener("click", resetFilters);
  $("retryLoad").addEventListener("click", load);
  $("closeTopic").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", event => {
    const bounds = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) dialog.close();
  });
  dialog.addEventListener("close", () => { delete dialog.dataset.topic; writeURL(); });
  window.addEventListener("popstate", () => {
    if (!atlas) return;
    const id = new URLSearchParams(location.search).get("topic");
    readFilters(); renderJourney(); render();
    if (mode === "achievements") loadJourney();
    if (id) openTopic(id, false);
    else if (dialog.open) dialog.close();
  });
  document.querySelectorAll("[data-mode]").forEach(button => button.addEventListener("click", () => {
    if (!atlas) return;
    mode = button.dataset.mode;
    reviewRequest++;
    $("reviewResults").hidden = true;
    renderJourney(); render(); writeURL();
    if (dialog.open && dialog.dataset.topic) openTopic(dialog.dataset.topic, false);
    if (mode === "achievements") loadJourney();
  }));
  $("refreshJourney").addEventListener("click", loadJourney);
  $("includeTeams").addEventListener("change", () => { journey = null; renderJourney(); render(); writeURL(); loadJourney(); });
  for (const id of ["progressFilter", "staleDays"]) $(id).addEventListener("change", () => { if (atlas) { render(); writeURL(); } });
  $("memoryYear").addEventListener("change", renderMemory);
  $("memoryTimeline").addEventListener("click", event => { const b = event.target.closest("[data-memory-topic]"); if (b) openTopic(b.dataset.memoryTopic); });
  $("topicDetails").addEventListener("input", event => { if (event.target.id === "linkProblemSearch") $("linkProblem").innerHTML = linkOptions(event.target.value); });
  $("topicDetails").addEventListener("click", event => {
    const b = event.target.closest("button");
    if (!b || !journey) return;
    if (b.id === "saveTopicLink") saveLink($("linkProblem").value);
    if (b.dataset.unlink) saveLink(b.dataset.unlink, true);
    if (b.id === "recommendThisTopic") { const t = atlas.topics.find(t => t.id === dialog.dataset.topic); dialog.close(); recommend(t); }
  });
  $("reviewTopic").addEventListener("click", () => {
    const candidates = visibleTopics.filter(t => isStale(achievement(t)));
    if (!candidates.length) { $("reviewResults").hidden = false; $("reviewResults").textContent = "当前筛选下没有久未 AC 的知识点。可以缩短时间间隔，或在知识点说明里主动找题。"; return; }
    candidates.sort((a,b) => achievement(a).lastAt - achievement(b).lastAt);
    recommend(candidates[0]);
  });
  $("downloadMemory").addEventListener("click", () => {
    if (!journey) return;
    const m = journey.memories[$("memoryYear").value] || journey.memories.all;
    const content = `${journey.user.displayName}的算法竞赛回忆\n\n` + memorySentences(m).map(([t,p]) => `${t}\n${p}`).join("\n\n") + "\n\n点亮航线\n" + m.timeline.map(t => `${dateLabel(t.at)} · ${topicName(t.topic)}`).join("\n") + "\n\n依据当前保存的代码 AC 记录；标签关联代表做题足迹，历史记录可能不完整。";
    const url = URL.createObjectURL(new Blob([content], {type:"text/plain;charset=utf-8"}));
    const a = document.createElement("a"); a.href = url; a.download = `算法竞赛回忆-${$("memoryYear").value}.txt`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  load();
})();
