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

  function readFilters() {
    const params = new URLSearchParams(location.search);
    $("topicSearch").value = (params.get("q") || "").slice(0, 100);
    category = atlas.categories.some(c => c.id === params.get("category")) ? params.get("category") : "all";
    $("difficultyFilter").value = /^[1-5]$/.test(params.get("difficulty")) ? params.get("difficulty") : "all";
    view = params.get("view") === "list" ? "list" : "iceberg";
  }

  function writeURL() {
    const params = new URLSearchParams();
    const query = $("topicSearch").value.trim();
    if (query) params.set("q", query);
    if (category !== "all") params.set("category", category);
    if ($("difficultyFilter").value !== "all") params.set("difficulty", $("difficultyFilter").value);
    if (view !== "iceberg") params.set("view", view);
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
    return `<div class="topic${topic.source === "OI Wiki" ? "" : " supplementary"}" id="topic-${escape(topic.id)}" style="--category-color:${escape(color)}"><a href="${escape(topic.url)}" target="_blank" rel="noopener noreferrer" title="${escape(topic.title)} · ${escape(topic.source)}${topic.kind === "implementation" ? "（实现参考）" : ""}"><i class="topic-dot" aria-hidden="true"></i>${escape(topic.title)}</a><button class="topic-info" type="button" data-topic="${escape(topic.id)}" aria-label="了解${escape(topic.title)}"></button></div>`;
  }

  function render() {
    const query = normalize($("topicSearch").value.trim());
    const difficulty = $("difficultyFilter").value;
    visibleTopics = atlas.topics.filter(topic =>
      (category === "all" || topic.category === category) &&
      (difficulty === "all" || String(topic.difficulty) === difficulty) &&
      (!query || matchesQuery(topic, query))
    );
    $("icebergMap").classList.toggle("list-view", view === "list");
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
    $("resultSummary").innerHTML = `发现 <strong>${visibleTopics.length}</strong> / ${atlas.topics.length} 个知识点${query || category !== "all" || difficulty !== "all" ? " · 筛选后的水下世界" : " · 从熟悉的地方，走向未知"}`;
    $("resetFilters").hidden = !(query || category !== "all" || difficulty !== "all");
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
    $("topicDetails").innerHTML = `<p class="atlas-kicker">${String(topic.tier).padStart(2, "0")} / ${escape(tier.name)} · ${escape(field.name)}</p><h2 id="dialogTitle">${escape(topic.title)}</h2><p class="topic-description">${escape(topic.summary)}</p><div class="topic-metrics"><div><small>理解门槛 · 编辑估计</small><strong><span class="difficulty-bars" aria-hidden="true">${Array.from({length: 5}, (_, i) => `<i${i < topic.difficulty ? ' class="filled"' : ""}></i>`).join("")}</span>${topic.difficulty} / 5 · ${difficultyNames[topic.difficulty]}</strong></div><div><small>竞赛常见程度 · 编辑估计</small><strong>${popularityNames[topic.popularity]}</strong></div></div>${topic.aliases ? `<p class="dialog-alias">也可以搜：${escape(topic.aliases)}</p>` : ""}<a class="topic-reading primary" href="${escape(topic.url)}" target="_blank" rel="noopener noreferrer">${topic.kind === "implementation" ? "查看实现参考" : "阅读知识点"} · ${escape(topic.source)}<span aria-hidden="true">↗</span></a><p class="source-note">${topic.kind === "implementation" ? "这份链接以代码实现为主，适合已有相关背景时进一步参考。" : "在新标签页打开资料，冰山会留在这里。"}</p>${references ? `<div class="topic-references" aria-label="补充资料">${references}</div>` : ""}<div class="related-topics"><p>沿这个方向，再看看</p><div>${related.map(item => `<button type="button" data-related="${escape(item.id)}">${escape(item.title)}</button>`).join("")}</div></div>`;
    dialog.dataset.topic = id;
    if (!dialog.open) dialog.showModal();
    if (updateURL) writeURL();
  }

  function resetFilters() {
    clearTimeout(searchTimer);
    $("topicSearch").value = "";
    $("difficultyFilter").value = "all";
    category = "all";
    render();
    writeURL();
  }

  async function load() {
    $("loadError").hidden = true;
    try {
      const response = await fetch("/iceberg-data.json?v=4");
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
      render();
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
    readFilters(); render();
    if (id) openTopic(id, false);
    else if (dialog.open) dialog.close();
  });
  load();
})();
