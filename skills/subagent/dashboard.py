#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard.py — /subagent 웹 대시보드 (localhost / 내부 IP).

subagent_tool.py 의 함수를 그대로 재사용해 브라우저에서 모델을 조회·지정한다.
- API 키·자격증명은 절대 노출/전송하지 않는다 (모델명만 다룸).
- 외부 의존성: flask 만. subagent_tool 은 같은 디렉터리에서 import.
- 한/영 전환은 프런트엔드 i18n 사전으로 처리(서버 무관).
"""
from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, jsonify, request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import subagent_tool as st  # noqa: E402

app = Flask(__name__)

HOST = "0.0.0.0"
PORT = 8097


# ------------------------------------------------------------------ API
@app.get("/api/state")
def api_state():
    """전체 상태 JSON. show() 에는 API 키가 포함되지 않는다."""
    return jsonify(st.show())


@app.post("/api/set")
def api_set():
    """모델 지정. kind = agent | main | fcc-tier."""
    d = request.get_json(force=True, silent=True) or {}
    kind = d.get("kind")
    model = (d.get("model") or "").strip()
    if not model:
        return jsonify({"ok": False, "error": "model 값이 비어 있습니다 / empty model"}), 400
    try:
        if kind == "agent":
            res = st.set_agent(
                d.get("agent", ""), model,
                d.get("scope", "user"),
                bool(d.get("follow_symlink", False)),
            )
        elif kind == "main":
            res = st.set_main(model, d.get("scope", "user"))
        elif kind == "fcc-tier":
            res = st.set_fcc_tier(d.get("tier", ""), model)
        else:
            return jsonify({"ok": False, "error": f"unknown kind: {kind}"}), 400
        return jsonify(res)
    except SystemExit as e:
        msg = str(e)
        # set_agent 의 심링크 가드 — UI 가 재선택하도록 플래그 전달
        guard = msg.startswith("[guard]")
        return jsonify({"ok": False, "guard": guard, "error": msg}), 200 if guard else 400
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@app.get("/")
def index():
    return HTML


# ------------------------------------------------------------------ HTML
HTML = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Subagent Model Manager</title>
<style>
  :root{
    --bg:#0d1117; --panel:#161b22; --panel2:#1c2230; --border:#2a3242;
    --fg:#e6edf3; --muted:#8b949e; --accent:#5b8cff; --accent2:#3b6bdb;
    --ok:#3fb950; --warn:#d29922; --err:#f85149; --link:#7ea6ff;
    --radius:10px;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif}
  a{color:var(--link)}
  header{display:flex;align-items:center;gap:14px;padding:18px 24px;
    border-bottom:1px solid var(--border);background:var(--panel);position:sticky;top:0;z-index:5}
  header h1{font-size:18px;margin:0;font-weight:650;letter-spacing:.2px}
  .dot{width:9px;height:9px;border-radius:50%;background:var(--accent);
    box-shadow:0 0 10px var(--accent)}
  .spacer{flex:1}
  .btn{background:var(--panel2);color:var(--fg);border:1px solid var(--border);
    border-radius:8px;padding:7px 12px;cursor:pointer;font-size:13px}
  .btn:hover{border-color:var(--accent)}
  .btn.lang{font-weight:650}
  main{max-width:1080px;margin:0 auto;padding:24px}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);
    padding:18px 20px;margin-bottom:20px}
  .card h2{font-size:15px;margin:0 0 14px;font-weight:600;
    display:flex;align-items:center;gap:8px}
  .badge{font-size:11px;padding:2px 8px;border-radius:20px;border:1px solid var(--border);
    color:var(--muted);background:var(--panel2)}
  .badge.accent{color:var(--accent);border-color:var(--accent)}
  .kv{color:var(--muted)}
  .kv b{color:var(--fg);font-weight:600}
  .warn-box{background:rgba(210,153,34,.1);border:1px solid var(--warn);color:#e3c27a;
    border-radius:8px;padding:10px 12px;font-size:13px;margin-bottom:14px}
  table{width:100%;border-collapse:collapse}
  th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--border);vertical-align:middle}
  th{color:var(--muted);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.4px}
  td.name{font-weight:550}
  .sym{font-size:11px;color:var(--warn);margin-left:6px}
  select,input[type=text]{background:var(--bg);color:var(--fg);border:1px solid var(--border);
    border-radius:7px;padding:6px 8px;font-size:13px;min-width:120px}
  select:focus,input:focus{outline:none;border-color:var(--accent)}
  .row-actions{display:flex;gap:8px;align-items:center}
  .apply{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
  .apply:hover{background:var(--accent2)}
  .cat{color:var(--accent);font-size:12px;letter-spacing:.5px;padding-top:14px}
  .modelcell{color:var(--muted);font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
  #toast{position:fixed;right:20px;bottom:20px;display:flex;flex-direction:column;gap:8px;z-index:50}
  .t{background:var(--panel2);border:1px solid var(--border);border-left:3px solid var(--accent);
    padding:10px 14px;border-radius:8px;max-width:420px;font-size:13px;box-shadow:0 6px 20px rgba(0,0,0,.4)}
  .t.ok{border-left-color:var(--ok)} .t.err{border-left-color:var(--err)} .t.warn{border-left-color:var(--warn)}
  .t .path{color:var(--muted);font-size:11.5px;font-family:ui-monospace,monospace;word-break:break-all}
  .foot{color:var(--muted);font-size:12px;text-align:center;padding:8px 0 30px}
  .scope-pick{display:flex;gap:6px;align-items:center;font-size:12px;color:var(--muted);margin-bottom:12px}
  .scope-pick select{min-width:auto}
</style>
</head>
<body>
<header>
  <span class="dot"></span>
  <h1 data-i18n="title">서브에이전트 모델 관리</h1>
  <span class="badge accent" id="launcher">—</span>
  <span class="spacer"></span>
  <button class="btn lang" id="langBtn" onclick="toggleLang()">EN</button>
  <button class="btn" onclick="load()" data-i18n="refresh">새로고침</button>
</header>
<main>
  <div id="content"><p class="kv" data-i18n="loading">불러오는 중…</p></div>
  <div class="foot">
    <span data-i18n="footnote">모델명만 다룹니다 — API 키·자격증명은 전송하지 않습니다.</span>
  </div>
</main>
<div id="toast"></div>

<script>
// ---------------- i18n ----------------
const I18N = {
  ko:{
    title:"서브에이전트 모델 관리", refresh:"새로고침", loading:"불러오는 중…",
    footnote:"모델명만 다룹니다 — API 키·자격증명은 전송하지 않습니다.",
    mainModel:"메인 모델", mainNote:"변경 시 현재 세션 미반영 → /model 전환 또는 재시작",
    effective:"유효", session:"세션", project:"프로젝트", user:"전역",
    agents:"파일 기반 서브에이전트", fccMap:"fcc 티어 → 백엔드 매핑",
    builtin:"내장 에이전트(파일 아님 · frontmatter 불가)",
    builtinNote:"호출 시 model 파라미터 또는 CLAUDE_CODE_SUBAGENT_MODEL 로만 지정",
    colName:"에이전트", colModel:"현재", colChange:"변경",
    apply:"적용", scope:"저장 범위", scopeUser:"전역(모든 프로젝트)", scopeProject:"프로젝트(이 폴더만)",
    collapsed:"현재 작업 폴더가 홈(~)이라 전역=프로젝트 스코프가 동일 디렉터리입니다.",
    tier:"티어", backend:"백엔드 모델", fccNote:"변경 시 fcc-server 재시작 후 반영",
    saved:"저장됨", failed:"실패", reflect:"반영",
    guardTitle:"공유 원본(심링크)입니다",
    guardBody:"이 에이전트는 여러 곳이 공유하는 원본을 가리킵니다. 어떻게 저장할까요?",
    guardShadow:"이 프로젝트 사본만 수정", guardShared:"공유 원본 수정(모두 영향)", cancel:"취소",
    custom:"직접 입력…", customPh:"전체 모델 ID 입력",
  },
  en:{
    title:"Subagent Model Manager", refresh:"Refresh", loading:"Loading…",
    footnote:"Model names only — API keys / credentials are never transmitted.",
    mainModel:"Main Model", mainNote:"Not applied to current session → use /model or restart",
    effective:"effective", session:"session", project:"project", user:"user",
    agents:"File-based Subagents", fccMap:"fcc Tier → Backend Mapping",
    builtin:"Built-in agents (not files · no frontmatter)",
    builtinNote:"Set only via model param on call or CLAUDE_CODE_SUBAGENT_MODEL",
    colName:"Agent", colModel:"Current", colChange:"Change",
    apply:"Apply", scope:"Save scope", scopeUser:"Global (all projects)", scopeProject:"Project (this folder only)",
    collapsed:"CWD is home (~) so global = project scope point to the same directory.",
    tier:"Tier", backend:"Backend model", fccNote:"Applied after fcc-server restart",
    saved:"Saved", failed:"Failed", reflect:"applies",
    guardTitle:"Shared original (symlink)",
    guardBody:"This agent points to a shared original used elsewhere. How do you want to save?",
    guardShadow:"Edit this project's copy only", guardShared:"Edit shared original (affects all)", cancel:"Cancel",
    custom:"Custom…", customPh:"Enter full model ID",
  }
};
let LANG = localStorage.getItem("subagent-lang") || "ko";
let STATE = null;
const MODELS = ["inherit","opus","sonnet","haiku","fable"];
function t(k){ return (I18N[LANG]&&I18N[LANG][k]) || k; }

function toggleLang(){
  LANG = (LANG==="ko") ? "en" : "ko";
  localStorage.setItem("subagent-lang", LANG);
  document.getElementById("langBtn").textContent = (LANG==="ko") ? "EN" : "한";
  document.documentElement.lang = LANG;
  applyStaticI18n();
  render();
}
function applyStaticI18n(){
  document.querySelectorAll("[data-i18n]").forEach(el=>{
    el.textContent = t(el.getAttribute("data-i18n"));
  });
}

// ---------------- data ----------------
async function load(){
  try{
    const r = await fetch("/api/state");
    STATE = await r.json();
    document.getElementById("launcher").textContent = STATE.launcher;
    render();
  }catch(e){ toast("err", t("failed"), String(e)); }
}

function modelSelect(current, onCustomId){
  // current 가 알려진 별칭이 아니면 커스텀으로 취급
  const known = MODELS.includes(current);
  let opts = MODELS.map(m=>`<option value="${m}"${m===current?" selected":""}>${m}</option>`).join("");
  opts += `<option value="__custom__"${!known?" selected":""}>${t("custom")}</option>`;
  const cur = known ? "" : current;
  return `<select onchange="onModelSel(this)">${opts}</select>`+
    `<input type="text" class="customid" placeholder="${t('customPh')}" value="${esc(cur)}" `+
    `style="display:${known?'none':'inline-block'};min-width:220px" oninput="void 0">`;
}
function onModelSel(sel){
  const inp = sel.parentElement.querySelector(".customid");
  if(!inp) return;
  inp.style.display = (sel.value==="__custom__") ? "inline-block" : "none";
}
function pickedModel(container){
  const sel = container.querySelector("select");
  const inp = container.querySelector(".customid");
  if(sel.value==="__custom__") return (inp.value||"").trim();
  return sel.value;
}

// ---------------- render ----------------
function render(){
  if(!STATE) return;
  const C = document.getElementById("content");
  const mm = STATE.main_model;
  const collapsed = STATE.agents.scope_collapsed;
  let h = "";

  // main model
  h += `<div class="card"><h2>${t("mainModel")} <span class="badge">${STATE.launcher}</span></h2>`;
  h += `<p class="kv">${t("effective")}: <b>${esc(mm.effective||"—")}</b> · `+
       `${t("session")}=${esc(mm.session_env||"∅")} · ${t("project")}=${esc(mm.project_settings||"∅")} · `+
       `${t("user")}=${esc(mm.user_settings||"∅")}</p>`;
  h += scopePicker("main-scope", collapsed);
  h += `<div class="row-actions" id="main-row">${modelSelect(mm.effective||"inherit")}`+
       `<button class="btn apply" onclick="applyMain()">${t("apply")}</button></div>`;
  h += `<p class="kv" style="margin:10px 0 0;font-size:12px">↳ ${t("mainNote")}</p></div>`;

  // agents
  h += `<div class="card"><h2>${t("agents")}</h2>`;
  if(collapsed) h += `<div class="warn-box">⚠ ${t("collapsed")}</div>`;
  h += scopePicker("agent-scope", collapsed);
  h += `<table><thead><tr><th>${t("colName")}</th><th>${t("colModel")}</th>`+
       `<th style="width:44%">${t("colChange")}</th></tr></thead><tbody>`;
  const byCat = {};
  (STATE.agents.user||[]).forEach(a=>{ (byCat[a.category]=byCat[a.category]||[]).push(a); });
  Object.keys(byCat).sort().forEach(cat=>{
    h += `<tr><td colspan="3" class="cat">· ${esc(cat)}</td></tr>`;
    byCat[cat].forEach(a=>{
      const sym = a.is_symlink ? `<span class="sym" title="${esc(a.symlink_target||'')}">🔗 shared</span>` : "";
      h += `<tr data-agent="${esc(a.name)}"><td class="name">${esc(a.name)}${sym}</td>`+
           `<td class="modelcell">${esc(a.model)}</td>`+
           `<td><div class="row-actions">${modelSelect(a.model)}`+
           `<button class="btn apply" onclick="applyAgent('${esc(a.name)}', this)">${t("apply")}</button>`+
           `</div></td></tr>`;
    });
  });
  h += `</tbody></table></div>`;

  // fcc tier map (launcher==fcc 이고 매핑 존재)
  const fcc = STATE.fcc;
  if(STATE.launcher==="fcc" && fcc && fcc.mapping && Object.keys(fcc.mapping).length){
    h += `<div class="card"><h2>${t("fccMap")}</h2>`;
    h += `<table><thead><tr><th>${t("tier")}</th><th style="width:60%">${t("backend")}</th><th></th></tr></thead><tbody>`;
    Object.entries(fcc.mapping).forEach(([tier,val])=>{
      h += `<tr data-tier="${esc(tier)}"><td class="name">${esc(tier)}</td>`+
           `<td><div class="row-actions"><input type="text" class="fccval" value="${esc(val||'')}" style="min-width:320px"></div></td>`+
           `<td><button class="btn apply" onclick="applyFcc('${esc(tier)}', this)">${t("apply")}</button></td></tr>`;
    });
    h += `</tbody></table>`;
    h += `<p class="kv" style="margin:10px 0 0;font-size:12px">↳ ${t("fccNote")}</p></div>`;
  }

  // builtin
  h += `<div class="card"><h2>${t("builtin")}</h2>`+
       `<p class="kv">${(STATE.builtin_agents||[]).map(esc).join(", ")}</p>`+
       `<p class="kv" style="font-size:12px;margin:8px 0 0">↳ ${t("builtinNote")}</p></div>`;

  C.innerHTML = h;
}

function scopePicker(id, collapsed){
  const dis = collapsed ? "disabled" : "";
  return `<div class="scope-pick"><span>${t("scope")}:</span>`+
    `<select id="${id}" ${dis}>`+
    `<option value="user">${t("scopeUser")}</option>`+
    `<option value="project">${t("scopeProject")}</option>`+
    `</select></div>`;
}

// ---------------- actions ----------------
async function post(body){
  const r = await fetch("/api/set", {method:"POST",headers:{"Content-Type":"application/json"},
    body: JSON.stringify(body)});
  return r.json();
}
function scopeOf(id){ const el=document.getElementById(id); return el?el.value:"user"; }

async function applyMain(){
  const model = pickedModel(document.getElementById("main-row"));
  if(!model) return;
  const res = await post({kind:"main", model, scope:scopeOf("main-scope")});
  reportAndReload(res, model);
}
async function applyAgent(name, btn){
  const row = btn.closest("tr");
  const model = pickedModel(row.querySelector(".row-actions"));
  if(!model) return;
  const scope = scopeOf("agent-scope");
  let res = await post({kind:"agent", agent:name, model, scope});
  if(res.guard){
    showGuard(name, model, res.error);
    return;
  }
  reportAndReload(res, model);
}
async function applyFcc(tier, btn){
  const row = btn.closest("tr");
  const model = row.querySelector(".fccval").value.trim();
  if(!model) return;
  const res = await post({kind:"fcc-tier", tier, model});
  reportAndReload(res, model);
}

// symlink guard modal (simplified as toast with 2 buttons)
function showGuard(name, model, msg){
  const id = "g"+Date.now();
  const box = document.createElement("div");
  box.className = "t warn"; box.id = id;
  box.innerHTML = `<div><b>${t("guardTitle")}</b></div><div style="margin:4px 0 8px">${t("guardBody")}</div>`+
    `<div class="row-actions">`+
    `<button class="btn" onclick="guardChoose('${esc(name)}','${esc(model)}','project','${id}')">${t("guardShadow")}</button>`+
    `<button class="btn" onclick="guardChoose('${esc(name)}','${esc(model)}','shared','${id}')">${t("guardShared")}</button>`+
    `<button class="btn" onclick="document.getElementById('${id}').remove()">${t("cancel")}</button>`+
    `</div>`;
  document.getElementById("toast").appendChild(box);
}
async function guardChoose(name, model, how, id){
  document.getElementById(id).remove();
  const body = (how==="project")
    ? {kind:"agent", agent:name, model, scope:"project"}
    : {kind:"agent", agent:name, model, scope:"user", follow_symlink:true};
  const res = await post(body);
  reportAndReload(res, model);
}

function reportAndReload(res, model){
  if(res && res.ok){
    const path = res.path ? `<div class="path">${esc(res.path)}</div>` : "";
    const note = res.note ? `<div class="kv" style="font-size:11.5px;margin-top:3px">↳ ${esc(res.note)}</div>` : "";
    toast("ok", `${t("saved")}: ${esc(model)}`, path+note, false);
    setTimeout(load, 400);
  }else{
    toast("err", t("failed"), esc((res&&res.error)||"?"), false);
  }
}

// ---------------- toast ----------------
function toast(kind, title, htmlBody, autohide=true){
  const box = document.createElement("div");
  box.className = "t "+kind;
  box.innerHTML = `<div><b>${title}</b></div>${htmlBody||""}`;
  document.getElementById("toast").appendChild(box);
  if(autohide!==false) setTimeout(()=>box.remove(), 4200);
  else setTimeout(()=>box.remove(), 8000);
}
function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g,c=>(
  {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }

// ---------------- init ----------------
document.getElementById("langBtn").textContent = (LANG==="ko") ? "EN" : "한";
document.documentElement.lang = LANG;
applyStaticI18n();
load();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print(f"[subagent-dashboard] serving on http://{HOST}:{PORT}  "
          f"— bind to a trusted LAN/localhost only (no auth on write endpoint)")
    app.run(host=HOST, port=PORT, debug=False)
