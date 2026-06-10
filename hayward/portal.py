"""Portal rendering.

A single self-contained HTML page (no build step, no external assets) so the
gateway ships as one process. The visual register is a control panel for an
ASF infrastructure service: a calm slate field, one restrained green accent
that stands for "within bounds" (the Hayward / hedge-warden idea), IBM Plex
Mono for anything that is data or identity, and a quiet sans for prose. The
signature element is the boundary rule — a hairline that frames the console
the way a hedge frames a field.
"""
from __future__ import annotations

import html
import json
from typing import Dict, List, Optional

from .config import Settings
from .seam import Identity


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def render_dev_login() -> str:
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hayward · sign in (dev)</title>
{_STYLE}
</head><body>
<main class="shell">
  <div class="console">
    <div class="eyebrow">hayward · dev auth</div>
    <h1>Stand in as an ASF identity</h1>
    <p class="lede">No external calls in dev mode. Enter a uid and the projects it belongs to;
    PMC memberships grant admin (the activity view) on those projects.</p>
    <form method="post" action="/auth/dev/login" class="stack">
      <label>uid
        <input name="uid" placeholder="jdoe" autocomplete="off" required>
      </label>
      <label>committer projects <span class="hint">comma-separated</span>
        <input name="projects" placeholder="airflow, lineage" autocomplete="off">
      </label>
      <label>PMC memberships <span class="hint">comma-separated · grants admin</span>
        <input name="committees" placeholder="airflow" autocomplete="off">
      </label>
      <button type="submit">Sign in</button>
    </form>
  </div>
</main>
</body></html>"""


def render_portal(settings: Settings, ident: Optional[Identity], models: List[Dict]) -> str:
    if ident is None:
        signin = (
            '<a class="btn" href="/auth/dev/login">Sign in (dev)</a>'
            if settings.is_dev_auth
            else '<a class="btn" href="/auth?login=/">Sign in with ASF</a>'
        )
        return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hayward · llm.apache.org</title>
{_STYLE}
</head><body>
<main class="shell">
  <div class="console">
    <div class="eyebrow">llm.apache.org</div>
    <h1>Hayward</h1>
    <p class="lede">The ASF's governed gateway to language models. Sign in with your
    Apache identity to browse approved models and make metered calls billed to your project.</p>
    {signin}
    <div class="modeline">auth: {_esc(settings.auth_mode)} · backend: {_esc(settings.litellm_mode)}</div>
  </div>
</main>
</body></html>"""

    projects = list(dict.fromkeys([*ident.committees, *ident.projects]))
    admin_projects = set(ident.committees) | ({p for p in projects} if ident.is_site_admin else set())

    ctx = {
        "uid": ident.uid,
        "projects": projects,
        "adminProjects": sorted(admin_projects),
        "models": models,
        "siteAdmin": ident.is_site_admin,
    }
    project_options = "".join(f'<option value="{_esc(p)}">{_esc(p)}</option>' for p in projects)
    if not projects:
        project_options = '<option value="">(no projects)</option>'

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hayward · llm.apache.org</title>
{_STYLE}
</head><body>
<main class="shell wide">
  <header class="topbar">
    <div class="brand"><span class="mark"></span> hayward<span class="dim"> · llm.apache.org</span></div>
    <div class="who">
      <span class="uid">{_esc(ident.uid)}</span>
      <a class="ghost" href="/auth/logout">Sign out</a>
    </div>
  </header>

  <section class="grid">
    <div class="panel">
      <div class="panel-h">Make a call</div>
      <div class="panel-b stack">
        <div class="row2">
          <label>Project
            <select id="project">{project_options}</select>
          </label>
          <label>Model
            <select id="model"></select>
          </label>
        </div>
        <div id="modelmeta" class="meta"></div>
        <label>Prompt
          <textarea id="prompt" rows="6" placeholder="Ask something, or attach a file below."></textarea>
        </label>
        <div class="row2">
          <label class="file">Attach a file <span class="hint">text · md · code · ≤2&nbsp;MB</span>
            <input type="file" id="file" accept=".txt,.md,.json,.py,.java,.go,.yaml,.yml,.csv,.log">
          </label>
          <button id="send">Send</button>
        </div>
        <div id="out" class="out" hidden></div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-h">Budget &amp; activity</div>
      <div class="panel-b stack">
        <div id="budget" class="budget">Select a project to see its budget.</div>
        <div id="activity" class="activity"></div>
        <div class="modeline">backend: {_esc(settings.litellm_mode)} · auth: {_esc(settings.auth_mode)}</div>
      </div>
    </div>
  </section>
</main>

<script>
const CTX = {json.dumps(ctx)};
{_SCRIPT}
</script>
</body></html>"""


_STYLE = """<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Inter:wght@400;500;600&display=swap');
:root{
  --bg:#10151b; --field:#161d26; --panel:#1a232e; --line:#2a3744;
  --ink:#e7edf3; --dim:#8aa0b4; --faint:#5b7184;
  --accent:#5fd08a; --accent-dim:#2f7a52; --warn:#e0a44a; --bad:#e06a6a;
  --mono:'IBM Plex Mono',ui-monospace,monospace; --sans:'Inter',system-ui,sans-serif;
}
*{box-sizing:border-box}
body{margin:0;background:
  radial-gradient(1200px 600px at 70% -10%, #18222e 0%, transparent 60%), var(--bg);
  color:var(--ink); font-family:var(--sans); line-height:1.5;
  -webkit-font-smoothing:antialiased;}
.shell{max-width:560px;margin:0 auto;padding:8vh 20px;}
.shell.wide{max-width:1080px;padding:28px 20px;}
.eyebrow{font-family:var(--mono);font-size:12px;letter-spacing:.18em;text-transform:uppercase;
  color:var(--accent);margin-bottom:14px;}
h1{font-family:var(--mono);font-weight:600;font-size:42px;letter-spacing:-.01em;margin:.1em 0 .3em;}
.lede{color:var(--dim);font-size:15px;max-width:48ch;}
.console{border:1px solid var(--line);border-radius:14px;background:linear-gradient(180deg,#1a232e,#151d26);
  padding:34px 32px;position:relative;}
.console::before{content:"";position:absolute;inset:7px;border:1px solid var(--line);border-radius:9px;
  pointer-events:none;opacity:.5;}
.modeline{font-family:var(--mono);font-size:11px;color:var(--faint);margin-top:22px;
  border-top:1px solid var(--line);padding-top:12px;}
.btn,button,.ghost{font-family:var(--mono);font-size:14px;cursor:pointer;}
.btn{display:inline-block;margin-top:8px;background:var(--accent);color:#08130c;font-weight:600;
  padding:11px 18px;border-radius:8px;text-decoration:none;border:none;}
.btn:hover{filter:brightness(1.08);}
button{background:var(--accent);color:#08130c;font-weight:600;border:none;padding:11px 16px;border-radius:8px;}
button:hover{filter:brightness(1.08);}
button:disabled{opacity:.5;cursor:wait;}
.stack{display:flex;flex-direction:column;gap:14px;}
label{display:flex;flex-direction:column;gap:6px;font-family:var(--mono);font-size:12px;
  letter-spacing:.04em;color:var(--dim);text-transform:uppercase;}
.hint{color:var(--faint);text-transform:none;letter-spacing:0;}
input,select,textarea{font-family:var(--mono);font-size:14px;background:var(--field);color:var(--ink);
  border:1px solid var(--line);border-radius:8px;padding:10px 12px;outline:none;}
input:focus,select:focus,textarea:focus{border-color:var(--accent-dim);box-shadow:0 0 0 2px rgba(95,208,138,.15);}
textarea{resize:vertical;line-height:1.5;}
/* portal */
.topbar{display:flex;justify-content:space-between;align-items:center;
  border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:22px;}
.brand{font-family:var(--mono);font-size:18px;font-weight:600;display:flex;align-items:center;gap:10px;}
.brand .dim,.dim{color:var(--faint);font-weight:400;}
.mark{width:14px;height:14px;border:2px solid var(--accent);border-radius:3px;display:inline-block;
  box-shadow:inset 0 0 0 2px var(--bg);}
.who{display:flex;align-items:center;gap:14px;font-family:var(--mono);font-size:13px;}
.uid{color:var(--accent);}
.ghost{color:var(--dim);text-decoration:none;border:1px solid var(--line);padding:7px 12px;border-radius:7px;}
.ghost:hover{border-color:var(--accent-dim);color:var(--ink);}
.grid{display:grid;grid-template-columns:1.4fr 1fr;gap:20px;}
@media(max-width:820px){.grid{grid-template-columns:1fr;}}
.panel{border:1px solid var(--line);border-radius:12px;background:var(--panel);overflow:hidden;}
.panel-h{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--dim);padding:14px 18px;border-bottom:1px solid var(--line);background:#151d26;}
.panel-b{padding:18px;}
.row2{display:grid;grid-template-columns:1fr auto;gap:14px;align-items:end;}
.row2 label.file{align-items:flex-start;}
.meta{font-family:var(--mono);font-size:11px;color:var(--faint);line-height:1.7;
  border-left:2px solid var(--line);padding-left:12px;min-height:1em;}
.meta b{color:var(--dim);font-weight:500;}
.meta .lic{color:var(--accent);}
.meta .prop{color:var(--warn);}
.out{font-family:var(--mono);font-size:13px;white-space:pre-wrap;background:var(--field);
  border:1px solid var(--line);border-radius:8px;padding:14px;color:var(--ink);}
.out .usage{color:var(--faint);font-size:11px;margin-top:10px;border-top:1px solid var(--line);padding-top:8px;}
.out.err{border-color:var(--bad);color:#f0b8b8;}
.budget{font-family:var(--mono);font-size:13px;color:var(--dim);}
.bar{height:8px;background:var(--field);border:1px solid var(--line);border-radius:5px;overflow:hidden;margin:10px 0;}
.bar>span{display:block;height:100%;background:var(--accent);}
.bar.warn>span{background:var(--warn);}
.bar.bad>span{background:var(--bad);}
.activity{font-family:var(--mono);font-size:12px;color:var(--dim);}
.activity table{width:100%;border-collapse:collapse;margin-top:8px;}
.activity th{text-align:left;color:var(--faint);font-weight:500;border-bottom:1px solid var(--line);
  padding:5px 6px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;}
.activity td{padding:5px 6px;border-bottom:1px solid #202b36;}
.activity .none{color:var(--faint);padding:8px 0;}
</style>"""


_SCRIPT = r"""
const $ = (id) => document.getElementById(id);
const modelSel = $('model'), projectSel = $('project');

function fillModels(){
  modelSel.innerHTML = CTX.models.map(m =>
    `<option value="${m.id}">${m.display_name}</option>`).join('');
  showMeta();
}
function showMeta(){
  const m = CTX.models.find(x => x.id === modelSel.value);
  if(!m){ $('modelmeta').textContent=''; return; }
  const openCls = m.openness === 'open-weight' || m.openness === 'open-source' ? 'lic' : 'prop';
  $('modelmeta').innerHTML =
    `<b>license</b> <span class="${openCls}">${m.license}</span> · <b>openness</b> ${m.openness}<br>`+
    `<b>weights</b> ${m.weights_distribution}<br>`+
    `<b>provenance record</b> ${m.provenance_record} · <b>ctx</b> ${m.context_window.toLocaleString()}`;
}

async function refreshBudget(){
  const p = projectSel.value;
  if(!p){ $('budget').textContent='No project selected.'; $('activity').innerHTML=''; return; }
  try{
    const r = await fetch(`/v1/projects/${encodeURIComponent(p)}/budget`);
    const b = await r.json();
    if(!b.provisioned){
      $('budget').innerHTML = `<b>${p}</b> — no spend yet. Budget provisions on first call.`;
    } else {
      const frac = b.max_budget_usd>0 ? Math.min(1, b.spend_usd/b.max_budget_usd) : 0;
      const cls = frac>0.9?'bad':frac>0.7?'warn':'';
      $('budget').innerHTML =
        `<b>${p}</b><div class="bar ${cls}"><span style="width:${(frac*100).toFixed(1)}%"></span></div>`+
        `$${b.spend_usd.toFixed(4)} of $${b.max_budget_usd.toFixed(2)} · $${b.remaining_usd.toFixed(4)} left`;
    }
  }catch(e){ $('budget').textContent='Budget unavailable.'; }
  refreshActivity(p);
}

async function refreshActivity(p){
  const isAdmin = CTX.adminProjects.includes(p);
  if(!isAdmin){ $('activity').innerHTML = `<div class="none">Activity is visible to PMC members of ${p}.</div>`; return; }
  try{
    const r = await fetch(`/v1/projects/${encodeURIComponent(p)}/usage`);
    if(!r.ok){ $('activity').innerHTML=''; return; }
    const a = await r.json();
    if(!a.count){ $('activity').innerHTML = `<div class="none">No activity in ${p} yet.</div>`; return; }
    const rows = a.entries.slice(-8).reverse().map(e=>{
      const t = new Date(e.ts*1000).toLocaleTimeString();
      const model = e.model.split('/').pop();
      return `<tr><td>${t}</td><td>${model}</td><td>${e.prompt_tokens+e.completion_tokens}</td><td>$${e.cost_usd.toFixed(4)}</td></tr>`;
    }).join('');
    $('activity').innerHTML =
      `<table><thead><tr><th>time</th><th>model</th><th>tok</th><th>cost</th></tr></thead><tbody>${rows}</tbody></table>`+
      `<div style="margin-top:8px;color:var(--faint)">total $${a.total_cost_usd.toFixed(4)} · ${a.count} calls</div>`;
  }catch(e){ $('activity').innerHTML=''; }
}

async function readFile(file){
  return new Promise((res,rej)=>{
    const fr = new FileReader();
    fr.onload=()=>res(fr.result); fr.onerror=()=>rej(fr.error);
    fr.readAsText(file);
  });
}

async function send(){
  const btn=$('send'), out=$('out');
  const project=projectSel.value, model=modelSel.value;
  let prompt=$('prompt').value.trim();
  const f=$('file').files[0];
  if(f){
    const text=await readFile(f);
    prompt = (prompt? prompt+"\n\n" : "") + `--- attached: ${f.name} ---\n` + text;
  }
  if(!prompt){ out.hidden=false; out.className='out err'; out.textContent='Enter a prompt or attach a file.'; return; }
  if(!project){ out.hidden=false; out.className='out err'; out.textContent='Select a project to bill the call to.'; return; }
  btn.disabled=true; out.hidden=false; out.className='out'; out.textContent='…calling '+model;
  try{
    const r=await fetch('/v1/chat/completions',{
      method:'POST', headers:{'Content-Type':'application/json','X-Hayward-Project':project},
      body:JSON.stringify({model, messages:[{role:'user',content:prompt}]}),
    });
    const j=await r.json();
    if(!r.ok){ out.className='out err'; out.textContent=(j.error&&j.error.message)||('error '+r.status); }
    else{
      const u=j.usage;
      out.className='out';
      out.innerHTML = escapeHtml(j.choices[0].message.content) +
        `<div class="usage">${u.total_tokens} tokens · $${(u.cost_usd||0).toFixed(4)} · billed to ${j.hayward_project}</div>`;
    }
  }catch(e){ out.className='out err'; out.textContent=String(e); }
  finally{ btn.disabled=false; refreshBudget(); }
}
function escapeHtml(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}

modelSel.addEventListener('change', showMeta);
projectSel.addEventListener('change', refreshBudget);
$('send').addEventListener('click', send);
fillModels(); refreshBudget();
"""
