"use strict";
const $ = id => document.getElementById(id);
const model = {data:null, csrf:"", user:0, detail:null, view:"union", savePromise:null, saveTimer:null, dirty:false, busy:false, preview:null, scroll:0, scrollX:0, initialized:false, pending:{}};
const esc = s => String(s ?? "").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function difficultyClass(r){return !r?"difficulty-unknown":r<1200?"difficulty-brown":r<1600?"difficulty-green":r<1900?"difficulty-cyan":r<2100?"difficulty-blue":r<2400?"difficulty-purple":r<2700?"difficulty-orange":"difficulty-red";}
const EMPTY = {oral:false,code:false,attempted:false,oralAttempted:false,draft:false};
function message(text="") { $("notice").textContent=text; }
async function request(path, body) {
  const options = {credentials:"same-origin",cache:"no-store"};
  if (body !== undefined) Object.assign(options,{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":model.csrf},body:JSON.stringify(body)});
  const r=await fetch(path,options), data=await r.json();
  if(!r.ok){const e=new Error(data.message || "请求失败");e.status=r.status;e.code=data.error;throw e;}
  return data;
}
const post = (action,body={}) => request("/api/regionals/"+action,body);
function localGet(key){try{return localStorage.getItem(key);}catch(_){return null;}}
function localSet(key,value){try{localStorage.setItem(key,value);}catch(_){}}
function draftKey(pid){return `regional-draft:${model.user}:${pid}`;}
function completed(p){return model.view==="oral"?p.oral:model.view==="code"?p.code:p.oral||p.code;}
function attempted(p){return model.view==="oral"?p.oralAttempted:model.view==="code"?p.attempted:p.attempted||p.oralAttempted;}
function visible(p){return $("filter").value==="all" || ($("filter").value==="unfinished"&&!completed(p)) || ($("filter").value==="draft"&&p.draft) || ($("filter").value==="oralOnly"&&p.oral&&!p.code);}
function persistFilters(){localSet(`regional-filters:${model.user}`,JSON.stringify({year:$("year").value,series:$("series").value,search:$("search").value,filter:$("filter").value,view:model.view}));}
function renderWall(){
  if(!model.data)return;
  const rows=model.data.contests.filter(c=>(!$("year").value||c.year===Number($("year").value))&&($("series").value==="all"||c.series===$("series").value)&&(!$("search").value||c.name.toLowerCase().includes($("search").value.toLowerCase())));
  const max=Math.max(1,...rows.map(c=>c.problems.length));
  $("wall").querySelector("thead").innerHTML=`<tr><th scope="col">比赛 / 赛站</th><th scope="col">我的进度</th>${Array.from({length:max},(_,i)=>`<th scope="col">${String.fromCharCode(65+i)}</th>`).join("")}</tr>`;
  let done=0,total=0;
  $("wall").querySelector("tbody").innerHTML=rows.map(c=>{
    let solved=0,tries=0;
    const cells=c.problems.map(p=>{
      const status=model.data.progress[p.id]||EMPTY,ok=completed(status),tried=attempted(status),show=visible(status);
      solved+=Number(ok);tries+=Number(tried||(model.view!=="code"&&status.draft));
      const marks=model.view==="oral"?(status.oral?"口":status.draft?"草稿":status.oralAttempted?"需修改":"") :model.view==="code"?(status.code?"AC":status.attempted?(status.verdict||"已提交"):"") :[status.oral?"口":"",status.code?"码":""].filter(Boolean).join("")||(status.draft?"草稿":tried?"尝试":"");
      const diff=model.data.difficulty?.[p.id] || (p.difficulty?{rating:p.difficulty,source:p.difficulty_source}:null);
      const title=`${diff?`难度 ${diff.rating} · ${diff.source}\n`:"难度未评级\n"}${c.name} ${p.index} · ${p.name}\n口胡：${status.oral?"通过":status.oralAttempted?"已尝试":"未通过"}；代码：${status.code?"AC":status.attempted?(status.verdict||"提交过"):"未提交"}${status.draft?"；有草稿":""}${p.unmapped?"；平台题号待核验":""}`;
      return `<td><button class="tile ${difficultyClass(diff?.rating)} ${ok?"done":status.draft&&model.view!=="code"?"draft":tried?"tried":""} ${show?"":"filtered"} ${p.unmapped?"unmapped":""}" data-problem="${esc(p.id)}" title="${esc(title)}" aria-label="${esc(title)}">${esc(p.index)}<span class="tile-mark" aria-hidden="true">${esc(marks)}</span></button></td>`;
    }).join("");
    done+=solved;total+=c.problems.length;
    return `<tr><th scope="row"><a class="site-name" href="${esc(c.source_url)}" target="_blank" rel="noopener noreferrer"><span class="series-badge">${esc(c.series)}</span>${esc(c.year)} · ${esc(c.site)}站</a></th><td>${model.view==="code"?`AC ${solved} / ${c.problems.length}<br>提交过 ${tries}`:`完成 ${solved} / ${c.problems.length}<br>尝试过 ${tries}`}</td>${cells}${"<td></td>".repeat(max-c.problems.length)}</tr>`;
  }).join("")||`<tr><td colspan="${max+2}">没有匹配的比赛，试试其他年份或赛站。</td></tr>`;
  $("summary").textContent=`${rows.length} 场比赛 · ${model.user?`${done} / ${total} 题完成`:`${total} 题已收录`}`;
  $("coverage").textContent=`目录核验于 ${model.data.verifiedAt||"—"}。来源：Codeforces、QOJ 等公开目录；虚线题格表示平台映射待核验。账号历史未回填完时，未着色不代表从未做过。`;
  document.querySelectorAll("[data-view]").forEach(b=>{b.classList.toggle("selected",b.dataset.view===model.view);b.setAttribute("aria-pressed",String(b.dataset.view===model.view));});
  persistFilters();
}
function renderRecords(){
  $("qojAccounts").innerHTML=(model.data.qojAccounts||[]).map(a=>`<div class="binding"><strong>QOJ · ${esc(a.uid)}</strong><small>${a.last_sync?"最近收到记录 · "+esc(new Date(a.last_sync).toLocaleString()):"已连接，请在 QOJ 插件中点击同步"}</small><button data-qoj-revoke="${esc(a.uid)}">断开授权</button></div>`).join("")||'<p class="muted small">尚未连接 QOJ 个人或团队账号。</p>';
  const names={codeforces:"Codeforces",vjudge:"VJudge",nowcoder:"牛客"},statuses={queued:"排队中",running:"同步中",idle:"已同步",failed:"同步失败"};
  $("bindings").innerHTML=(model.data.bindings||[]).map(b=>`<div class="binding"><strong>${esc(names[b.platform]||b.platform)} · ${esc(b.handle)}</strong><small>${esc(statuses[b.status]||b.status)} · ${esc(b.message)}${b.last_sync?` · ${esc(new Date(b.last_sync*1000).toLocaleString())}`:""}${b.complete?"":" · 历史未完成"}</small><button data-sync="${b.id}" ${["queued","running"].includes(b.status)?"disabled":""}>同步 / 继续回填</button><button data-unbind="${b.id}">解绑</button></div>`).join("")||'<p class="muted small">尚未绑定账号。绑定后会同步公开提交记录。</p>';
  $("batches").innerHTML=(model.data.imports||[]).map(b=>{const s=JSON.parse(b.summary);return `<div class="batch"><span>导入 ${s.valid} 条 · ${esc(new Date(b.created_at).toLocaleString())}</span><button data-revoke="${esc(b.id)}">撤销此批导入</button></div>`;}).join("");
}
async function refresh(){
  const data=await request("/api/regionals");
  model.data=data;model.csrf=data.csrfToken;model.user=data.user.id;
  $("userName").textContent=data.user.displayName;
  $("privateRecords").hidden=false;
  $("resume").hidden=!data.lastProblem;
  if(model.initialized)renderWall();renderRecords();renderQojAuthorization();
}
async function boot(){
  try{await refresh();}catch(e){
    if(e.status!==401){message(e.message);return;}
    model.data=await request("/api/regional-catalog");model.data.progress={};model.user=0;
    $("loginRequired").hidden=false;$("recordsPanel").hidden=true;
  }
  $("year").innerHTML=model.data.years.map(y=>`<option>${y}</option>`).join("");
  let saved={};try{saved=JSON.parse(localGet(`regional-filters:${model.user}`)||"{}");}catch(_){}
  for(const id of ["year","series","filter","search"]){if(saved[id]!==undefined&&(!(id==="year")||model.data.years.includes(Number(saved[id]))))$(id).value=saved[id];}
  if(["oral","code","union"].includes(saved.view))model.view=saved.view;
  model.initialized=true;renderWall();renderQojAuthorization();
  const hash=decodeURIComponent(location.hash.slice(1));
  if(hash&&model.user&&model.data.contests.some(c=>c.problems.some(p=>p.id===hash)))await openProblem(hash);
}
async function run(task){
  if(model.busy)return;
  model.busy=true;message();
  const buttons=[...document.querySelectorAll('button:not(:disabled)')];buttons.forEach(b=>b.disabled=true);
  try{await task();}catch(e){message(e.message);}finally{model.busy=false;buttons.filter(b=>b.isConnected).forEach(b=>b.disabled=false);renderRecords();updateAvailability();}
}
function updateAvailability(){if(!model.detail)return;$("estimateDifficulty").disabled=model.busy||!model.detail.statement||!model.data.oralJudge;$("submitOral").disabled=model.busy||!model.detail.statement||!model.data.oralJudge;$("submitCode").disabled=model.busy||!model.detail.statement||!model.data.codeJudge||!model.detail.problem.cf_contest_id;}
async function openProblem(pid){
  if(!model.user){message("请先登录本站，再开始口胡。比赛目录仍可浏览。");$("loginRequired").scrollIntoView({behavior:"smooth"});return;}
  await saveDraft();
  if(!$("wallView").hidden){model.scroll=document.querySelector('.table-wrap').scrollTop;model.scrollX=document.querySelector('.table-wrap').scrollLeft;}
  message("正在准备中文题面，首次打开可能需要一点时间…");
  const d=await post("open",{problemId:pid});
  model.detail=d;model.dirty=false;
  $("oralText").value=d.draft.body;$("codeText").value="";$("oralResult").textContent="";
  let recovery=null;try{recovery=JSON.parse(localGet(draftKey(pid))||"null");}catch(_){}
  if(recovery&&recovery.body!==d.draft.body&&recovery.dirty){$("oralText").value=recovery.body;model.dirty=true;message("已恢复本机尚未同步的草稿。服务器版本仍保留；如有冲突请复制后合并。");}else message();
  const contest=model.data.contests.find(c=>c.id===d.problem.contest);
  $("practiceContest").textContent=contest.name;
  const diff=model.data.difficulty?.[pid];$("difficultyStatus").textContent=diff?`难度 ${diff.rating} · ${diff.source}`:"难度未评级";
  $("estimateDifficulty").disabled=!model.data.oralJudge;
  $("problemTitle").textContent=`${d.problem.index} · ${d.title&&d.title!=="区域赛题目"?d.title:d.problem.name}`;
  $("problemNav").innerHTML=contest.problems.map(p=>`<button data-problem="${esc(p.id)}" class="${p.id===pid?"selected":""}">${esc(p.index)}</button>`).join("");
  const s=d.statement;
  $("statementBody").innerHTML=s?`${s.description}${s.input?`<h3>输入格式</h3>${s.input}`:""}${s.output?`<h3>输出格式</h3>${s.output}`:""}${s.samples.map((sample,i)=>`<h3>样例 ${i+1}</h3><pre>${esc(sample.input)}</pre><pre>${esc(sample.output)}</pre>`).join("")}${s.hint?`<h3>样例说明</h3>${s.hint}`:""}`:`<p>${esc(d.statementError)}</p>`;
  $("sourceLinks").innerHTML=(d.problem.aliases||[]).map(key=>{const [oj,id]=key.split(':');let url=oj==="codeforces"?`https://codeforces.com/gym/${d.problem.cf_contest_id}/problem/${d.problem.index}`:oj==="qoj"?`https://qoj.ac/problem/${id}`:null;return url?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(oj)} 原题 ↗</a>`:"";}).join("");
  $("attempts").innerHTML=d.attempts.map(a=>`<div class="attempt"><strong>${esc(a.verdict)}</strong> <small class="muted">${esc(new Date(a.created_at).toLocaleString())}</small><p>${esc(a.reason)}</p><details><summary>查看当时的${a.kind==="oral"?"做法":"代码"}</summary><pre>${esc(a.body)}</pre></details></div>`).join("")+d.evidence.map(e=>`<div class="attempt"><strong>${esc(e.verdict)}</strong> · ${esc(e.platform)} · ${esc(e.handle)}<br><small class="muted">${e.submitted_at?esc(new Date(e.submitted_at*1000).toLocaleString()):"时间未知"} · ${e.origin.startsWith("import:")?"导入记录":"账号同步"}</small></div>`).join("");
  if(!d.attempts.length&&!d.evidence.length)$("attempts").textContent="还没有练习记录。";
  $("saveStatus").textContent=model.dirty?"本机恢复，尚未同步":d.draft.updated_at?"草稿已保存":"自动保存";
  $("wallView").hidden=true;$("practiceView").hidden=false;$("resume").hidden=true;
  history.replaceState(null,"",'#'+encodeURIComponent(pid));updateAvailability();window.scrollTo(0,0);
}
async function saveDraft(){
  clearTimeout(model.saveTimer);
  if(model.savePromise){await model.savePromise;if(model.dirty)return saveDraft();return;}
  if(!model.detail||!model.dirty)return;
  const pid=model.detail.problem.id,body=$("oralText").value,version=model.detail.draft.version;
  $("saveStatus").textContent="正在保存…";
  model.savePromise=(async()=>{
    try{const r=await post("draft",{problemId:pid,body,version});model.detail.draft.version=r.version;model.detail.draft.body=body;model.dirty=$("oralText").value!==body;localSet(draftKey(pid),JSON.stringify({body:$("oralText").value,dirty:model.dirty}));$("saveStatus").textContent=model.dirty?"仍有修改待保存":"已保存 · "+new Date(r.updatedAt).toLocaleTimeString();}
    catch(e){$("saveStatus").textContent="未同步 · 本机已保留";throw e;}
    finally{model.savePromise=null;}
  })();return model.savePromise;
}
async function back(){await saveDraft();model.detail=null;$("practiceView").hidden=true;$("wallView").hidden=false;history.replaceState(null,"",location.pathname);await refresh();document.querySelector('.table-wrap').scrollTop=model.scroll;document.querySelector('.table-wrap').scrollLeft=model.scrollX;}
async function submit(kind){
  await saveDraft();const pid=model.detail.problem.id;
  const payload={problemId:pid,requestId:crypto.randomUUID?crypto.randomUUID():Date.now()+"_"+Math.random().toString(36).slice(2)};
  if(kind==="oral")payload.solution=$("oralText").value;else Object.assign(payload,{source:$("codeText").value,language:$("language").value});
  message(kind==="oral"?"正在审核做法…":"正在提交代码判定…");
  const key=JSON.stringify([pid,kind,payload.solution,payload.source,payload.language]);
  if(model.pending[key])payload.requestId=model.pending[key];else model.pending[key]=payload.requestId;
  const result=await post(kind,payload);delete model.pending[key];
  const outcome=`${result.verdict} · ${result.reason}`;
  await refresh();await openProblem(pid);$("oralResult").textContent=outcome;
}
document.addEventListener("DOMContentLoaded",()=>{
  boot().catch(e=>message(e.message));
  ["year","series","filter"].forEach(id=>$(id).addEventListener("change",renderWall));$("search").addEventListener("input",renderWall);
  document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener("click",()=>{model.view=b.dataset.view;renderWall();}));
  document.addEventListener("click",e=>{const b=e.target.closest('button[data-problem]');if(b)run(()=>openProblem(b.dataset.problem));});
  $("resume").addEventListener("click",()=>run(()=>openProblem(model.data.lastProblem)));
  $("estimateDifficulty").addEventListener("click",()=>run(async()=>{const r=await post("difficulty",{problemId:model.detail.problem.id});await refresh();$("difficultyStatus").textContent=`难度 ${r.rating} · ${r.source}`;}));
  $("back").addEventListener("click",()=>run(back));$("retry").addEventListener("click",()=>run(()=>openProblem(model.detail.problem.id)));
  $("saveDraft").addEventListener("click",()=>run(saveDraft));$("submitOral").addEventListener("click",()=>run(()=>submit('oral')));$("submitCode").addEventListener("click",()=>run(()=>submit('code')));
  $("oralText").addEventListener("input",()=>{if(!model.detail)return;model.dirty=true;$("saveStatus").textContent="尚未同步 · 本机已保留";localSet(draftKey(model.detail.problem.id),JSON.stringify({body:$("oralText").value,dirty:true}));clearTimeout(model.saveTimer);model.saveTimer=setTimeout(()=>saveDraft().catch(e=>message(e.message)),900);});
  window.addEventListener("beforeunload",e=>{if(model.dirty){e.preventDefault();e.returnValue="";}});
  $("bindForm").addEventListener("submit",e=>{e.preventDefault();const f=new FormData(e.currentTarget);run(async()=>{await post('bind',{platform:f.get('platform'),handle:f.get('handle')});await refresh();});});
  $("bindings").addEventListener("click",e=>{const b=e.target.closest('button');if(!b)return;run(async()=>{if(b.dataset.sync)await post('sync',{bindingId:Number(b.dataset.sync)});if(b.dataset.unbind)await post('unbind',{bindingId:Number(b.dataset.unbind)});await refresh();});});
  $("qojAuthorize").addEventListener("click",()=>run(authorizeQoj));
  $("qojAccounts").addEventListener("click",e=>{const b=e.target.closest("[data-qoj-revoke]");if(b)run(async()=>{await post("qoj-revoke",{uid:b.dataset.qojRevoke});await refresh();message("授权已断开，已有记录和口胡草稿保留。");});});
  $("batches").addEventListener("click",e=>{const b=e.target.closest('[data-revoke]');if(b)run(async()=>{await post('import-revoke',{token:b.dataset.revoke});await refresh();});});
  setInterval(()=>{if(!model.user||model.busy||document.hidden)return;const syncing=(model.data.bindings||[]).some(b=>['queued','running'].includes(b.status));const due=(model.data.bindings||[]).some(b=>b.status==='idle'&&Date.now()/1000-b.last_sync>(b.complete?900:120));const qojDue=(model.data.qojAccounts||[]).length&&!model.detail&&Date.now()-(model.qojPollAt||0)>15000;if(qojDue)model.qojPollAt=Date.now();if(syncing||due||qojDue)refresh().catch(e=>message(e.message));},5000);
});

function qojAuthParams(){
  const p=new URLSearchParams(location.search),uid=p.get('uid')||'',nonce=p.get('nonce')||'';
  return p.has('qojAuthorize')&&/^[A-Za-z0-9_-]{1,64}$/.test(uid)&&/^[A-Za-z0-9_-]{16,100}$/.test(nonce)?{uid,nonce}:null;
}
function renderQojAuthorization(){
  const auth=qojAuthParams();if(!auth)return;
  if(!model.user){document.querySelector('#loginRequired a').href='/?next=regionals&qojReturn='+encodeURIComponent(location.pathname+location.search);return;}
  $('recordsPanel').open=true;$('qojAuthorization').hidden=false;
  $('qojAuthorizeText').textContent=`将 QOJ 账号「${auth.uid}」的提交记录同步到本站用户「${model.data.user.displayName}」。如果是团队账号，其 AC 将计入你的代码进度。仅在确认此账号属于你或你的团队时连接。`;
}
async function authorizeQoj(){
  const auth=qojAuthParams();if(!auth||!window.opener)throw new Error('请从 QOJ 插件重新发起连接。');
  const result=await post('qoj-authorize',{uid:auth.uid});
  window.opener.postMessage({type:'regional-qoj-authorized',uid:auth.uid,nonce:auth.nonce,token:result.token},'https://qoj.ac');
  history.replaceState(null,'',location.pathname);$('qojAuthorization').hidden=true;
  await refresh();message('已连接，请回到 QOJ 页面点击插件的「同步」。');
}
