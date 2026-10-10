/* =====================================================
   THE ANALYST DISPATCH — Yusuf's daily briefing.
   Live keyless feeds: Remotive + The Muse.
   Board listings come from this app (/api/jobs/daily).
   Applied / saved / skipped stay on this device and in
   data/applications.json.
===================================================== */

const $  = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pad = n => String(n).padStart(2,'0');
const stripHtml = h => { const d = document.createElement('div'); d.innerHTML = h || ''; return (d.textContent || '').replace(/\u00a0/g,' '); };
const host = u => { try { return new URL(u).hostname.replace(/^www\./,''); } catch(e){ return u; } };
const dateKey = d => d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate());
const fmtTime = t => new Date(t).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',hour12:true}).toUpperCase();
const timeAgo = d => { if(!d) return '—'; const h=(Date.now()-new Date(d).getTime())/36e5;
  if(h<1) return 'just now'; if(h<24) return Math.floor(h)+'h ago'; return Math.floor(h/24)+'d ago'; };
const refreshIcons = () => { if (window.lucide) lucide.createIcons(); };
const debounce = (fn,ms)=>{ let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a),ms); }; };
function jid(j){ const k=(j.url||'')+'|'+(j.title||'')+'|'+(j.company||''); let h=5381;
  for(let i=0;i<k.length;i++) h=((h<<5)+h+k.charCodeAt(i))>>>0; return h.toString(36); }
async function fetchJSON(url, timeout=12000){
  const c=new AbortController(); const t=setTimeout(()=>c.abort(), timeout);
  try { const r=await fetch(url,{signal:c.signal}); if(!r.ok) throw new Error('HTTP '+r.status); return await r.json(); }
  finally { clearTimeout(t); }
}

const store = {
  get(k,f){ try{ const v=localStorage.getItem('dispatch:'+k); return v?JSON.parse(v):f; }catch(e){ return f; } },
  set(k,v){ try{ localStorage.setItem('dispatch:'+k, JSON.stringify(v)); }catch(e){} }
};

const PROFILE = {
  name:'Yusuf Hameed', headline:'Senior Business Analyst', location:'Columbia, MD',
  phone:'443-823-5622', email:'yush_21@yahoo.com', linkedin:'linkedin.com/in/yusuf-hameed-09561644'
};
const SPECIAL = {'uat':'UAT','brd':'BRD','frd':'FRD','sql':'SQL','kpi':'KPI','bi':'BI','ehr':'EHR','emr':'EMR','sdlc':'SDLC','qa':'QA','crm':'CRM','erp':'ERP','power bi':'Power BI','excel':'Excel','jira':'Jira','hipaa':'HIPAA'};
const prettyTerm = t => SPECIAL[t] || t.replace(/\b\w/g, c => c.toUpperCase());
const TERMS = [
  ['business analyst',6],['requirements gathering',5],['stakeholder',4],['user acceptance',4],['uat',4],
  ['brd',3],['frd',2],['functional specification',3],['acceptance criteria',3],['traceability',3],
  ['use case',2],['gap analysis',3],['process mapping',3],['workflow',2],['business process',3],
  ['process improvement',3],['jira',3],['sql',3],['power bi',3],['tableau',2],['excel',2],['agile',2],
  ['scrum',2],['user stories',2],['test scenario',3],['regression',3],['end-to-end',2],['root cause',3],
  ['data validation',3],['data analysis',2],['reporting',2],['kpi',2],['dashboard',2],['healthcare',3],
  ['hipaa',2],['insurance',2],['claims',2],['benefits',2],['ehr',2],['emr',2],['epic',2],['migration',2],
  ['implementation',2],['vendor',2],['change management',2],['sdlc',2],['quality assurance',2],
  ['training',1],['copilot',1],['requirements',3]
];
const termRes = TERMS.map(([t,w])=>{
  const e = t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  const b = /^[a-z0-9]/i.test(t) ? '\\b' : '', f = /[a-z0-9]$/i.test(t) ? '\\b' : '';
  return { t, w, re:new RegExp(b+e+f,'i') };
});
function scoreJob(j){
  const text = ((j.title||'')+' '+(j.company||'')+' '+(j.description||'')).toLowerCase();
  const matched = termRes.filter(x=>x.re.test(text)).map(x=>({t:x.t,w:x.w})).sort((a,b)=>b.w-a.w);
  const raw = matched.reduce((s,m)=>s+m.w,0);
  let fit = Math.round(100*raw/(raw+16));
  if(/analyst/i.test(j.title||'')) fit += 4;
  if(/senior|lead|sr\.|principal/i.test(j.title||'')) fit += 2;
  return { fit: Math.max(8, Math.min(99, fit)), matched };
}

function roleOf(t){ const s=t.toLowerCase();
  if(/quality assurance|\bqa\b|sdet|software test|test analyst|\btester\b|automation analyst/.test(s)) return 'qa';
  if(/data analy|analytics|business intelligence|\bbi\b|power ?bi|reporting analyst/.test(s)) return 'data';
  if(/systems? analyst|it analyst|application analyst|technical analyst|\berp\b|\bcrm\b/.test(s)) return 'systems';
  if(/business analy|business systems|process analyst|operations analyst/.test(s)) return 'ba';
  return 'other';
}
const LOCAL_RE = /\b(columbia|ellicott|catonsville|elkridge|hanover|odenton|severn|jessup|meade|baltimore|towson|glen burnie|linthicum|annapolis|rockville|silver spring|bethesda|gaithersburg|chevy chase|college park|beltsville|greenbelt|hyattsville|bowie|washington|howard county|anne arundel|montgomery county|maryland|, md|md)\b/i;
function locClass(j){
  if(j.sample) return /remote/i.test(j.location||'') ? 'remote' : 'local';
  if(j.sourceKey==='remotive') return 'remote';
  const l=(j.location||'').toLowerCase();
  if(/remote|anywhere|worldwide|global/.test(l)) return 'remote';
  if(/,\s*sc\b|south carolina/.test(l)) return 'elsewhere';
  if(LOCAL_RE.test(l)) return 'local';
  return 'elsewhere';
}

const OR_Q = '"business analyst" OR "systems analyst" OR "data analyst" OR "QA analyst" OR "quality assurance analyst"';
function boardLink(board, mode, q){
  const Q = encodeURIComponent(q || OR_Q);
  if(board==='indeed') return mode==='local'
    ? `https://www.indeed.com/jobs?q=${Q}&l=Columbia%2C+MD&radius=30&fromage=7&sc=0kf%3Aattr%28DSQF7%29`
    : `https://www.indeed.com/jobs?q=${Q}&l=Remote&fromage=7&sc=0kf%3Aattr%28DSQF7%29`;
  if(board==='dice') return mode==='local'
    ? `https://www.dice.com/jobs?q=${Q}&location=Columbia%2C+MD%2C+USA&radius=30&filters.postedDate=SEVEN_DAYS`
    : `https://www.dice.com/jobs?q=${Q}&location=Remote&filters.postedDate=SEVEN_DAYS`;
  if(board==='monster') return mode==='local'
    ? `https://www.monster.com/jobs/search?q=${Q}&where=Columbia%2C+MD&rad=30&days=7`
    : `https://www.monster.com/jobs/search?q=${Q}&where=Remote&days=7`;
  return mode==='local'
    ? `https://www.careerbuilder.com/jobs?keywords=${Q}&location=Columbia%2C+MD&radius=30&posted=7`
    : `https://www.careerbuilder.com/jobs?keywords=${Q}&location=Remote&posted=7`;
}
const BOARDS = [
  {name:'Indeed',        key:'indeed',        note:'Easily Apply is pre-applied in these links.'},
  {name:'Dice',          key:'dice',          note:'On the site, tick “Easy apply” under Filters.'},
  {name:'Monster',       key:'monster',       note:''},
  {name:'CareerBuilder', key:'careerbuilder', note:''}
];

const settings = Object.assign({goal:5, feeds:[]}, store.get('settings',{}));
const saveSettings = ()=>store.set('settings',settings);
const statuses = ()=>store.get('statuses',{});
const serverStatusByUrl = {};
function syncApplication(id, s){
  const j = (state.jobs||[]).find(x=>x.id===id);
  if(!j) return;
  const status = s==='saved' ? 'saved' : s;
  fetch('/api/applications', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      jobId: String(id),
      status,
      title: j.title,
      company: j.company,
      url: j.url,
      source: j.sourceLabel || ''
    })
  }).catch(()=>{});
}
const setStatus = (id,s)=>{ const st=statuses(); const cur=st[id];
  const clearing = !!(cur && cur.s===s);
  if(clearing) delete st[id]; else st[id]={s, at:Date.now()};
  store.set('statuses',st);
  if(!clearing) syncApplication(id, s);
};
const stOf = id => statuses()[id];

const F = { role:'all', locs:new Set(['remote','local']), activeSrc:new Set(), easy:false, q:'', sort:'fit' };
const SORTS = { fit:'BEST FIT', new:'NEWEST', company:'COMPANY A–Z' };
const ROLES = [['all','All'],['ba','Business'],['systems','Systems'],['data','Data'],['qa','QA']];
const SRC_LABEL = { remotive:'Remotive', muse:'The Muse', sample:'Sample', boards:'This app' };
function sourceChipLabel(k){
  if(SRC_LABEL[k]) return SRC_LABEL[k];
  if(String(k).indexOf('board:')===0){
    const name = k.slice(6);
    return name ? name.charAt(0).toUpperCase()+name.slice(1) : 'Board';
  }
  if(String(k).indexOf('custom:')===0) return host(k.slice(7));
  return k;
}

const state = { jobs:[], edition:null, selection:null, vis:[], lastFetch:{},
                draftOpen:false, draftMode:'short', publishing:false, knownSrc:new Set() };

function sampleRoleQuery(title){
  if(/data/i.test(title)) return '"data analyst"';
  if(/qa|quality|test/i.test(title)) return '"QA analyst"';
  if(/system/i.test(title)) return '"systems analyst"';
  return '"business analyst"';
}
const SAMPLES = [
 {title:'Senior Business Analyst — Claims & Benefits Systems', company:'Harbor Benefit Systems', location:'Columbia, MD (hybrid)', days:1, easy:true, board:'indeed', type:'Full-time', salary:'$95k–$120k',
  desc:`Harbor Benefit Systems is consolidating three claims platforms into one. The Senior Business Analyst will lead requirements gathering with clinical and administrative stakeholders, author BRDs and functional specifications, map current-state and future-state workflows, coordinate UAT and regression testing, and support the production transition. Requirements traceability, gap analysis, and Jira coordination are core to the role. SQL and Power BI used for validation and reporting. Healthcare or insurance background strongly preferred.`},
 {title:'Data Analyst — Membership & Claims Reporting', company:'Patapsco Analytics Group', location:'Baltimore, MD', days:2, easy:true, board:'dice', type:'Full-time', salary:'$80k–$100k',
  desc:`Own reporting and dashboards for a growing benefits administrator: build Power BI dashboards and KPI reporting, write SQL against claims and membership data, run data validation and root cause analysis on enrollment trends, and present findings to executive stakeholders. Healthcare data experience a plus; Power BI certification valued.`},
 {title:'QA Analyst — UAT & Regression, Benefits Platform', company:'Chesapeake Quality Partners', location:'Remote (US)', days:3, easy:true, board:'indeed', type:'Contract-to-hire',
  desc:`Join the quality practice supporting a benefits administration platform. You will write test scenarios from requirements and acceptance criteria, execute end-to-end and regression testing, document defects with root cause detail, and partner with business analysts on requirements traceability. UAT coordination with business users expected.`},
 {title:'Systems Analyst — EHR & Scheduling Systems', company:'MidAtlantic Eye Care Alliance', location:'Ellicott City, MD', days:2, board:'monster', type:'Full-time',
  desc:`Support a multi-site EHR migration: current-state assessments, interface requirements, workflow redesign, vendor coordination, implementation readiness, and training documentation. Clinical or practice-operations background helpful; healthcare environment, HIPAA compliance awareness required.`},
 {title:'Business Analyst — Benefit Operations', company:'Severn Health Administrators', location:'Fort Meade, MD', days:4, board:'careerbuilder', type:'Full-time',
  desc:`Elicit and document business and operational requirements, maintain BRDs, run stakeholder workshops, perform gap analysis and change impact assessment in a HIPAA-regulated benefits environment. Coordinate workstreams in Jira and prepare executive summaries for leadership.`},
 {title:'Business Systems Analyst — ERP Implementation', company:'Laurel Works Consulting', location:'Columbia, MD', days:5, easy:true, board:'dice', type:'Full-time',
  desc:`ERP implementation team needs a hands-on analyst: functional specifications, use cases, acceptance criteria, data migration validation, sprint participation in Jira, and end-user training materials. Agile/Scrum environment; SDLC fluency expected.`},
 {title:'Data Analyst — Power BI & KPI Dashboards', company:'Monocacy Data Studio', location:'Remote (US)', days:5, board:'monster', type:'Full-time',
  desc:`Build Power BI dashboards and KPI reporting for operations clients; SQL analysis and data validation; partner with stakeholders to define metrics and user stories; present clear recommendations to non-technical audiences. Tableau experience a plus.`},
 {title:'QA / Test Analyst — Claims Systems', company:'Gunpowder Quality Lab', location:'Remote (US)', days:6, board:'careerbuilder', type:'Contract',
  desc:`Write test scenarios from requirements; run regression and end-to-end testing on claims processing changes; document defects and support root cause analysis; assist business users through UAT. Quality assurance discipline and clear defect documentation essential.`},
 {title:'Senior Business Analyst — Process Improvement', company:'Rockwell Benefit Partners', location:'Columbia, MD (hybrid)', days:6, board:'indeed', type:'Full-time',
  desc:`Lead process improvement across benefit operations: current and future-state process mapping, gap analysis, stakeholder alignment across business and technology teams, executive summaries, and implementation readiness. Change management and training experience valued.`}
];

async function fetchRemotive(){
  const queries = ['business analyst','systems analyst','data analyst','qa analyst'];
  const rs = await Promise.allSettled(queries.map(q =>
    fetchJSON('https://remotive.com/api/remote-jobs?search='+encodeURIComponent(q)+'&limit=50')));
  let out = [];
  rs.forEach(r => { if(r.status==='fulfilled' && Array.isArray(r.value.jobs)) out.push(...r.value.jobs); });
  return out.map(j => ({
    title:j.title, company:j.company_name, url:j.url,
    location:j.candidate_required_location || 'Remote',
    postedAt:new Date(j.publication_date), description:j.description||'',
    type:(j.job_type||'').replace(/_/g,' '), salary:(j.salary&&j.salary!=='null')?j.salary:'',
    sourceKey:'remotive', sourceLabel:'Remotive', sample:false, easyApply:false
  }));
}
async function fetchMuse(){
  const cities = ['Columbia, MD','Baltimore, MD','Washington, DC','Remote'];
  const rs = await Promise.allSettled(cities.map(c =>
    fetchJSON('https://www.themuse.com/api/public/jobs?location='+encodeURIComponent(c)+'&page=1', 9000)));
  let out = [];
  rs.forEach(r => { if(r.status==='fulfilled' && Array.isArray(r.value.results)) out.push(...r.value.results); });
  return out.map(j => ({
    title:j.name, company:(j.company||{}).name, url:((j.refs||{}).landing_page),
    location:(j.locations||[]).map(l=>l.name).join(' · '),
    postedAt:new Date(j.publication_date), description:j.contents||'',
    type:((j.levels||[])[0]||{}).name||'', salary:'',
    sourceKey:'muse', sourceLabel:'The Muse', sample:false, easyApply:false
  }));
}
async function fetchCustom(url){
  const d = await fetchJSON(url, 12000);
  const arr = Array.isArray(d) ? d : (d.jobs||d.results||d.data||d.listings);
  if(!Array.isArray(arr)) throw new Error('no job array found');
  return arr.map(o => ({
    title:o.title||o.role||o.position, company:o.company||o.companyName||o.organization,
    url:o.url||o.link||o.applyUrl||o.apply_url, location:o.location||'',
    postedAt:new Date(o.postedAt||o.publication_date||o.date||o.posted||o.created_at),
    description:o.description||o.summary||o.text||'', type:o.type||o.job_type||'', salary:o.salary||'',
    easyApply:!!(o.easyApply ?? o.oneClick ?? o.easy_apply),
    sourceKey:'custom:'+url, sourceLabel:host(url), sample:false
  })).filter(j=>j.title&&j.url);
}
async function fetchLocalBoard(){
  const d = await fetchJSON('/api/jobs/daily', 8000);
  const fallback = d.generatedAt ? new Date(d.generatedAt) : new Date();
  return (d.jobs||[]).map(j => {
    const posted = j.posted ? new Date(j.posted) : fallback;
    const board = String(j.board || j.source || 'Board');
    const blob = ((j.description||'')+' '+((j.reasons||[]).join(' ')));
    if(j.url && j.applicationStatus) serverStatusByUrl[j.url] = j.applicationStatus;
    return {
      title:j.title, company:j.company, url:j.url,
      location:j.location||'',
      postedAt: isNaN(posted.getTime()) ? new Date() : posted,
      description:j.description||'',
      type:'', salary:j.salary||'',
      sourceKey:'board:'+board.toLowerCase(),
      sourceLabel:board,
      sample:false,
      easyApply:/easy apply|1-click|one-click|quick apply/i.test(blob)
    };
  }).filter(j=>j.title&&j.url);
}

function finalize(j){
  const title=(j.title||'').trim(), url=(j.url||'').trim();
  if(!title||!url) return null;
  if(!/analy/i.test(title)) return null;
  const postedAt = j.postedAt instanceof Date ? j.postedAt : new Date(j.postedAt);
  if(!j.sample){
    if(isNaN(postedAt)) return null;
    const d=(Date.now()-postedAt.getTime())/864e5;
    if(d>7.05 || d<-1) return null;
  }
  const {fit, matched} = scoreJob(j);
  return { id:jid(j), title, company:(j.company||'—').trim(), url, location:(j.location||'').trim(),
    postedAt, type:(j.type||'').trim(), salary:(j.salary||'').trim(),
    description:stripHtml(j.description||'').trim().slice(0,2600),
    sourceKey:j.sourceKey, sourceLabel:j.sourceLabel||SRC_LABEL[j.sourceKey]||j.sourceKey,
    sample:!!j.sample, easyApply:!!j.easyApply,
    role:roleOf(title), locClass:locClass(j), fit, matched, isNew:false };
}
function dedupe(list){
  const byUrl=new Set(), byRole=new Set(), out=[];
  for(const j of list){
    if(byUrl.has(j.url)) continue;
    const k=(j.title+'|'+j.company).toLowerCase().replace(/\s+/g,' ');
    if(byRole.has(k)) continue;
    byUrl.add(j.url); byRole.add(k); out.push(j);
  }
  return out;
}
function absorbServerStatuses(jobs){
  const st = statuses();
  let changed = false;
  jobs.forEach(j => {
    const s = serverStatusByUrl[j.url];
    if(!s || !/^(applied|saved|skipped)$/.test(s) || st[j.id]) return;
    st[j.id] = {s, at:Date.now()};
    changed = true;
  });
  if(changed) store.set('statuses', st);
}

let edNo = store.get('edNo', 0);
async function publishNow(auto=false){
  if(state.publishing) return;
  state.publishing = true;
  $('#btnPublish').classList.add('spin');
  $('#edLeft').textContent = auto ? 'PUBLISHING THE 9:00 AM EDITION…' : 'PUBLISHING TODAY\u2019S EDITION…';
  renderList();

  const prevSeen = new Set(store.get('seenUrls', []));
  const tasks = [
    {key:'boards', label:'Dice and captured board listings', p:fetchLocalBoard()},
    {key:'remotive', label:'Remotive',  p:fetchRemotive()},
    {key:'muse',     label:'The Muse',  p:fetchMuse()}
  ];
  (settings.feeds||[]).forEach(u => tasks.push({key:'custom:'+u, label:host(u), p:fetchCustom(u)}));

  const settled = await Promise.allSettled(tasks.map(t=>t.p));
  let raw = [], srcStatus = {};
  settled.forEach((r,i)=>{
    const t = tasks[i];
    if(r.status==='fulfilled' && r.value.length){ srcStatus[t.key]={ok:true, count:r.value.length, label:t.label}; raw.push(...r.value); }
    else srcStatus[t.key]={ok:false, err:(r.reason&&r.reason.message)||'no listings in the last 7 days', label:t.label};
  });

  let jobs = dedupe(raw.map(finalize).filter(Boolean));
  let degraded = false;
  if(!jobs.length){
    degraded = true;
    jobs = SAMPLES.map(s => finalize({
      title:s.title, company:s.company, url:boardLink(s.board, /remote/i.test(s.location)?'remote':'local', sampleRoleQuery(s.title)),
      location:s.location, postedAt:new Date(Date.now()-s.days*864e5), description:s.desc, type:s.type,
      salary:s.salary||'', easyApply:!!s.easy, sourceKey:'sample', sourceLabel:'Sample', sample:true
    })).filter(Boolean);
  }

  const first = prevSeen.size===0;
  jobs.forEach(j => { j.isNew = !first && !prevSeen.has(j.url); });
  absorbServerStatuses(jobs);

  edNo += 1; store.set('edNo', edNo);
  state.edition = { at:Date.now(), date:dateKey(new Date()), degraded,
    dateDisplay:new Date().toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'}) };
  store.set('edition', state.edition);
  store.set('jobs', {jobs, at:Date.now(), degraded});
  store.set('seenUrls', jobs.filter(j=>!j.sample).map(j=>j.url));
  state.jobs = jobs; state.lastFetch = srcStatus; state.selection = null;

  $('#btnPublish').classList.remove('spin');
  state.publishing = false;
  renderAll(true);
  if($('#drawer').classList.contains('open')) renderDrawerDynamic();

  const newN = jobs.filter(j=>j.isNew).length;
  if(degraded)
    toast('Live feeds are unreachable — showing a marked sample edition. The board buttons in Sources still run your exact search.');
  else if(auto)
    toast(`9:00 AM — today\u2019s edition just published · ${jobs.length} listings${newN?`, ${newN} new`:''}.`);
  else
    toast(`Edition №${edNo} published — ${jobs.length} listings${newN?`, ${newN} new`:''}.`);
}

function next9am(){ const d=new Date(), t=new Date(d); t.setHours(9,0,0,0); if(d>=t) t.setDate(t.getDate()+1); return t; }
function editionDue(){
  const now=new Date(), today9=new Date(); today9.setHours(9,0,0,0);
  const ed=state.edition;
  if(!ed || !state.jobs.length) return true;
  return now.getTime() >= today9.getTime() && ed.at < today9.getTime();
}

function baseList(){
  const st = statuses();
  return state.jobs.filter(j=>{
    if(st[j.id] && st[j.id].s==='skipped') return false;
    if(!F.locs.has(j.locClass)) return false;
    if(F.activeSrc.size && !F.activeSrc.has(j.sourceKey)) return false;
    if(F.easy && !j.easyApply) return false;
    if(F.q && !((j.title+' '+j.company).toLowerCase().includes(F.q))) return false;
    return true;
  });
}
function visibleList(){
  let l = F.role==='all' ? baseList() : baseList().filter(j=>j.role===F.role);
  if(F.sort==='fit')        l.sort((a,b)=> b.fit-a.fit || new Date(b.postedAt)-new Date(a.postedAt));
  else if(F.sort==='new')   l.sort((a,b)=> new Date(b.postedAt)-new Date(a.postedAt));
  else                      l.sort((a,b)=> (a.company+a.title).localeCompare(b.company+b.title));
  return l;
}

function renderAll(cascade=false){
  const present = [...new Set(state.jobs.map(j=>j.sourceKey))];
  present.forEach(k=>{
    if(!state.knownSrc.has(k)){ state.knownSrc.add(k); F.activeSrc.add(k); }
  });
  [...F.activeSrc].forEach(k=>{ if(!present.includes(k)) F.activeSrc.delete(k); });
  renderTabs(); renderChips(); renderList(cascade); renderMast(); renderTicker();
  if(!state.selection || !visibleList().find(j=>j.id===state.selection)){
    const first = visibleList()[0]; state.selection = first ? first.id : null;
  }
  markSelection(); renderDetail();
}
function renderTabs(){
  const base = baseList();
  const counts = {all:base.length};
  ROLES.slice(1).forEach(([r])=> counts[r]=base.filter(j=>j.role===r).length);
  $('#roleTabs').innerHTML = ROLES.map(([r,label])=>
    `<button class="tab ${F.role===r?'on':''}" data-role="${r}">${label}<span class="c">${counts[r]||0}</span></button>`).join('');
}
function renderChips(){
  const locDefs = [['remote','Remote'],['local','Local · ≤30 mi'],['elsewhere','Elsewhere']];
  $('#locChips').innerHTML = '<span class="clabel">Location</span>' + locDefs.map(([k,l])=>
    `<button class="chip ${F.locs.has(k)?'on':''}" data-loc="${k}">${l}</button>`).join('');
  const srcs = [...new Set(state.jobs.map(j=>j.sourceKey))];
  $('#srcChips').innerHTML = '<span class="clabel">Sources</span>' + srcs.map(k=>
    `<button class="chip ${F.activeSrc.has(k)?'on':''}" data-src="${esc(k)}">${esc(sourceChipLabel(k))}</button>`).join('');
}
function renderList(cascade=false){
  const list = visibleList();
  state.vis = list.map(j=>j.id);
  $('#idxCount').textContent = `${list.length} LISTING${list.length===1?'':'S'} — EDITION №${edNo}`;
  $('#sortBtn').textContent = 'SORT · ' + SORTS[F.sort];
  $('#sampleBanner').hidden = !(state.edition && state.edition.degraded && list.length);
  if(state.publishing && !state.jobs.length){
    $('#rows').innerHTML = '<div class="boot-line">Publishing the first edition</div>';
    $('#empty').hidden = true; return;
  }
  if(!list.length){
    $('#rows').innerHTML=''; $('#empty').hidden=false;
    const easy = F.easy ? '<br>the 1-click / easy-apply filter is hiding everything — the live feeds here apply on employer sites' : '';
    $('#empty').innerHTML = `<div class="e-title">Nothing matches this filter.</div>
      <div class="e-sub">${state.jobs.length} listings in today's edition${easy}<br><button class="linklike" id="clearF">clear filters</button> or <button class="linklike" id="openBoards">search the boards directly</button></div>`;
    $('#clearF').onclick = ()=>{ F.role='all'; F.locs=new Set(['remote','local']); F.easy=false; F.q=''; $('#q').value=''; renderAll(); };
    $('#openBoards').onclick = openDrawer;
    return;
  }
  $('#empty').hidden=true;
  const st = statuses();
  $('#rows').innerHTML = list.map((j,i)=>{
    const s = st[j.id];
    const glyph = s ? `<span class="dot ${s.s==='applied'?'applied':'saved'}"></span>` : '<span class="dot"></span>';
    const loc = j.locClass==='remote' ? 'Remote' : (j.location||'—');
    return `<article class="row ${cascade?'in':''} ${s&&s.s==='applied'?'applied-row':''}" data-id="${j.id}" ${cascade?`style="animation-delay:${Math.min(i*24,600)}ms"`:''}>
      <div class="row-glyph">${glyph}</div>
      <div class="row-num">${pad(i+1)}</div>
      <div>
        <h3 class="row-title">${j.isNew?'<span class="newflag">NEW</span>':''}${s&&s.s==='applied'?'<span class="appliedflag">APPLIED</span>':''}${esc(j.title)}${j.sample?'<span class="sampleflag">SAMPLE</span>':''}</h3>
        <div class="row-co">${esc(j.company)}</div>
        <div class="row-meta">${esc(j.sourceLabel)} · ${esc(loc)} · ${timeAgo(j.postedAt)}${j.easyApply?' · <span class="easy">1-CLICK</span>':''}</div>
      </div>
      <div class="row-fit ${j.fit>=80?'hot':''}"><span class="n">${j.fit}</span><span class="l">fit</span></div>
    </article>`;
  }).join('');
  markSelection();
}
function markSelection(){
  $$('#rows .row').forEach(r=> r.classList.toggle('sel', r.dataset.id===state.selection));
}
function renderMast(){
  const st = statuses(), today = dateKey(new Date());
  let applied=0, saved=0;
  Object.values(st).forEach(v=>{ if(v.s==='applied' && dateKey(new Date(v.at))===today) applied++; if(v.s==='saved') saved++; });
  $('#gApplied').textContent = applied;
  $('#goalInput').value = settings.goal;
  $('#gfill').style.width = Math.min(100, 100*applied/settings.goal) + '%';
  const ed = state.edition;
  if(!ed){ $('#edLeft').textContent = state.publishing ? 'PUBLISHING TODAY\u2019S EDITION…' : '—'; return; }
  const now=new Date(), today9=new Date(); today9.setHours(9,0,0,0);
  const stale = now < today9 && ed.date !== dateKey(now);
  const newN = state.jobs.filter(j=>j.isNew).length;
  $('#edLeft').innerHTML =
    `№${edNo} — ${esc(ed.dateDisplay.toUpperCase())} · ${stale?'PREVIOUS EDITION — PUBLISHES 9:00 AM':'PUBLISHED '+fmtTime(ed.at)} · ${state.jobs.length} LISTINGS${newN?` · <b>${newN} NEW</b>`:''}` +
    (saved?` · ${saved} SAVED`:'');
}
function renderTicker(){
  const newest = [...state.jobs].sort((a,b)=>new Date(b.postedAt)-new Date(a.postedAt)).slice(0,10);
  let items = '';
  if(newest.length){
    items = newest.map(j=>`<span class="tick-item">${j.isNew?'<b>NEW</b>':''}${esc(j.title)} — ${esc(j.company)} · ${esc(j.sourceLabel)}</span><span class="tick-sep">///</span>`).join('');
    items += `<span class="tick-item"><b>GOOD HUNTING</b> APPLY EARLY — EASY-APPLY ROLES CLOSE FAST</span>`;
  } else {
    items = `<span class="tick-item"><b>THE ANALYST DISPATCH</b> EDITION PUBLISHES EVERY MORNING AT 9:00 AM — REMOTE OR WITHIN 30 MILES OF COLUMBIA, MD</span>`;
  }
  $('#tickerTrack').innerHTML = items + items;
}
function locLabel(j){
  if(j.locClass==='remote') return 'Remote';
  if(j.locClass==='local') return 'Within 30 mi · Columbia, MD';
  return j.location || 'Location unspecified';
}
function renderDetail(){
  const j = state.jobs.find(x=>x.id===state.selection);
  const R = $('#reader');
  if(!j){
    const h = new Date().getHours();
    const gm = h<12 ? 'Good morning.' : h<18 ? 'Good afternoon.' : 'Good evening.';
    R.innerHTML = `<div class="rd-empty"><div class="gm">${gm}</div>
      <div class="hint">Pick a listing from today's edition<br>↑ ↓ to browse · Enter to apply</div></div>`;
    return;
  }
  const s = stOf(j.id) || {};
  const idx = state.vis.indexOf(j.id);
  const chips = [
    `<span class="mchip"><i data-lucide="map-pin"></i>${esc(locLabel(j))}</span>`,
    `<span class="mchip"><i data-lucide="clock"></i>Posted ${timeAgo(j.postedAt)}</span>`,
    j.type?`<span class="mchip">${esc(j.type)}</span>`:'',
    j.salary?`<span class="mchip">${esc(j.salary)}</span>`:'',
    j.easyApply?`<span class="mchip accent">1-click / easy apply</span>`:'',
    s.s==='applied'?`<span class="mchip applied">Applied</span>`:''
  ].join('');
  const matchedChips = j.matched.slice(0,9).map(m=>`<span class="kchip">${esc(prettyTerm(m.t))}</span>`).join('') || '<span class="kchip" style="border-style:dashed">no direct keyword overlap</span>';
  R.innerHTML = `
    <div class="rd-kicker"><span>LISTING №${pad(idx+1)} · ${esc(j.sourceLabel)}${j.sample?' · SAMPLE':''}</span><button class="rd-close" data-act="close" aria-label="close"><i data-lucide="x"></i></button></div>
    <h2 class="rd-title">${esc(j.title)}</h2>
    <div class="rd-co">${esc(j.company)}<span class="dotsep">·</span>${esc(locLabel(j))}</div>
    <div class="rd-chips">${chips}</div>
    <div class="rd-fit">
      <div class="rd-fit-num"><span class="n">${j.fit}</span><span class="l">profile fit</span></div>
      <div class="rd-fit-rest">
        <div class="gauge"><span style="width:${j.fit}%"></span></div>
        <div class="fit-label">This role aligns with your résumé on</div>
        <div>${matchedChips}</div>
      </div>
    </div>
    <div class="rd-desc">${esc(j.description || 'No description provided by the source — open the listing for details.')}</div>
    <div class="rd-actions">
      <a class="btn primary" href="${esc(j.url)}" target="_blank" rel="noopener" data-act="apply"><i data-lucide="external-link"></i>${j.sample?'Search live on the boards':'Apply — new tab'}</a>
      <button class="btn" data-act="draft">Draft intro</button>
      <button class="btn t ${s.s==='saved'?'on':''}" data-act="save"><i data-lucide="bookmark"></i>${s.s==='saved'?'Saved':'Save'}</button>
      <button class="btn t ${s.s==='applied'?'on-ap':''}" data-act="applied"><i data-lucide="check"></i>${s.s==='applied'?'Applied':'Mark applied'}</button>
      <button class="btn t" data-act="skip"><i data-lucide="x"></i>Skip</button>
    </div>
    <div class="rd-draft" ${state.draftOpen?'':'hidden'}>
      <div class="rd-draft-tabs">
        <button class="dm ${state.draftMode==='short'?'on':''}" data-dm="short">Short note</button>
        <button class="dm ${state.draftMode==='full'?'on':''}" data-dm="full">Cover note</button>
        <button class="copybtn" data-act="copydraft"><i data-lucide="copy"></i>Copy</button>
      </div>
      <textarea id="draftArea" spellcheck="false"></textarea>
    </div>
    <div class="rd-notes"><label>Notes for this role — saved on this device</label>
      <textarea id="noteArea" placeholder="Recruiter contact, resume version sent, follow-up date…">${esc(store.get('notes',{})[j.id]||'')}</textarea>
    </div>`;
  refreshIcons();
  if(state.draftOpen) $('#draftArea').value = buildDraft(j, state.draftMode);
}

function buildDraft(job, mode){
  const skills = (job.matched||[]).slice(0,4).map(m=>prettyTerm(m.t));
  const line = skills.length ? skills.join(', ') : 'business analysis, stakeholder workshops, and UAT';
  if(mode==='short')
    return `Hello — I'd like to be considered for the ${job.title} role at ${job.company}. I'm a Senior Business Analyst with 10+ years across business analysis, systems implementation, and healthcare/benefits operations; the strongest overlap here is ${line}.`;
  return `Dear Hiring Team,

I'm applying for the ${job.title} position at ${job.company}. I'm a Senior Business Analyst based in Columbia, MD, with 10+ years across business analysis, project coordination, and systems implementation in customer-facing healthcare and benefits operations.

Most recently I led a practice-wide platform migration, partnering with business, operations, and vendor technology teams on scope, requirements, configuration, data quality, testing, readiness, and production transition — including requirements discovery with clinical and administrative users, current/future-state process mapping, functional specifications, UAT coordination, and defect resolution.

Where I'd align with this role: ${line}. I work regularly with SQL and Power BI, coordinate delivery in Jira, and use AI tools (ChatGPT, Microsoft Copilot) to accelerate documentation and analysis.

I'd welcome a conversation about how I can contribute.

Yusuf Hameed · Columbia, MD · 443-823-5622 · yush_21@yahoo.com`;
}

function toast(msg, action){
  const el = document.createElement('div');
  el.className='toast';
  el.innerHTML = `<span>${esc(msg)}</span>${action?`<button class="ta">${esc(action.label)}</button>`:''}`;
  if(action) el.querySelector('.ta').onclick = ()=>{ action.fn(); el.remove(); };
  el.onclick = e=>{ if(e.target===el.querySelector('span')) el.remove(); };
  $('#toasts').appendChild(el);
  setTimeout(()=>el.remove(), 5200);
}
function copyText(text, label){
  const done = ()=>toast(label||'Copied to clipboard.');
  if(navigator.clipboard && navigator.clipboard.writeText)
    navigator.clipboard.writeText(text).then(done).catch(()=>fallbackCopy(text, done));
  else fallbackCopy(text, done);
}
function fallbackCopy(text, done){
  const ta=document.createElement('textarea'); ta.value=text; ta.style.position='fixed'; ta.style.opacity='0';
  document.body.appendChild(ta); ta.select();
  try{ document.execCommand('copy'); done(); }catch(e){ toast('Copy failed — select the text manually.'); }
  ta.remove();
}

function openDrawer(){ renderDrawerDynamic(); $('#drawer').classList.add('open'); $('#backdrop').classList.add('open'); }
function closeDrawer(){ $('#drawer').classList.remove('open'); $('#backdrop').classList.remove('open'); }
function renderBoards(){
  $('#drBoards').innerHTML = BOARDS.map(b=>`
    <div class="board">
      <div class="b-name">${b.name}</div>
      <div class="b-links">
        <a class="b-btn" href="${boardLink(b.key,'local')}" target="_blank" rel="noopener"><i data-lucide="arrow-up-right"></i>Local · ≤ 30 mi · 7 days</a>
        <a class="b-btn" href="${boardLink(b.key,'remote')}" target="_blank" rel="noopener"><i data-lucide="arrow-up-right"></i>Remote · 7 days</a>
      </div>
      ${b.note?`<div class="b-note">${b.note}</div>`:''}
    </div>`).join('');
}
function renderDrawerDynamic(){
  const lf = state.lastFetch || {};
  const rows = [
    {key:'boards', label:'Dice and captured board listings'},
    {key:'remotive', label:'Remotive — remote analyst roles'},
    {key:'muse', label:'The Muse — Columbia · Baltimore · DC · remote'},
    ...(settings.feeds||[]).map(u=>({key:'custom:'+u, label:host(u)}))
  ];
  $('#drFeeds').innerHTML = rows.map(r=>{
    const s = lf[r.key];
    const dot = !s ? '<span class="sdot wait"></span>' : s.ok ? '<span class="sdot ok"></span>' : '<span class="sdot err"></span>';
    const tail = !s ? 'next edition' : s.ok ? `${s.count} listing${s.count===1?'':'s'}` : 'unreachable — retries next edition';
    return `<div class="feedrow">${dot}<span class="fname">${esc(r.label)}</span><span class="fcnt">${esc(tail)}</span></div>`;
  }).join('');
  $('#drFeedList').innerHTML = (settings.feeds||[]).length
    ? settings.feeds.map(u=>`<div class="feedrow"><span class="sdot ok"></span><span class="fname">${esc(u)}</span><button class="rm" data-rm="${esc(u)}" aria-label="remove feed"><i data-lucide="trash-2"></i></button></div>`).join('')
    : '<div class="feedrow"><span class="sdot wait"></span><span class="fname" style="color:var(--ink3)">No custom feeds yet</span></div>';
  refreshIcons();
}
function renderProfChips(){
  $('#drProfChips').innerHTML = termRes.filter(t=>t.w>=2).slice(0,26)
    .map(t=>`<span class="kchip">${esc(prettyTerm(t.t))}</span>`).join('');
}

function select(id, openMobile=false){
  state.selection = id;
  markSelection(); renderDetail();
  if(openMobile && window.matchMedia('(max-width:960px)').matches) $('#reader').classList.add('open');
}
function nav(dir){
  if(!state.vis.length) return;
  let i = state.vis.indexOf(state.selection);
  i = i<0 ? 0 : (i+dir+state.vis.length)%state.vis.length;
  select(state.vis[i]);
  const row = $(`#rows .row[data-id="${state.vis[i]}"]`);
  if(row) row.scrollIntoView({block:'nearest'});
}
function applySelected(){
  const j = state.jobs.find(x=>x.id===state.selection);
  if(!j) return;
  window.open(j.url, '_blank', 'noopener');
  toast('Application page opened in a new tab.', {label:'Mark as applied', fn:()=>{ setStatus(j.id,'applied'); afterStatus(); }});
}
function afterStatus(){
  renderList(); renderMast(); renderDetail();
}

$('#btnPublish').addEventListener('click', ()=>publishNow(false));
$('#btnDrawer').addEventListener('click', openDrawer);
$('#drClose').addEventListener('click', closeDrawer);
$('#backdrop').addEventListener('click', closeDrawer);
$('#sbOpen').addEventListener('click', openDrawer);

$('#roleTabs').addEventListener('click', e=>{
  const t = e.target.closest('.tab'); if(!t) return;
  F.role = t.dataset.role; renderAll();
});
$('#locChips').addEventListener('click', e=>{
  const c = e.target.closest('.chip[data-loc]'); if(!c) return;
  const k = c.dataset.loc;
  F.locs.has(k) ? F.locs.delete(k) : F.locs.add(k);
  if(!F.locs.size) F.locs.add(k);
  renderAll();
});
$('#srcChips').addEventListener('click', e=>{
  const c = e.target.closest('.chip[data-src]'); if(!c) return;
  const k = c.dataset.src;
  F.activeSrc.has(k) ? F.activeSrc.delete(k) : F.activeSrc.add(k);
  renderAll();
});
$('#easySwitch').addEventListener('change', e=>{ F.easy = e.target.checked; renderAll(); });
$('#q').addEventListener('input', debounce(e=>{ F.q = e.target.value.trim().toLowerCase(); renderAll(); }, 160));
$('#sortBtn').addEventListener('click', ()=>{
  F.sort = F.sort==='fit' ? 'new' : F.sort==='new' ? 'company' : 'fit';
  renderAll();
});
$('#rows').addEventListener('click', e=>{
  const r = e.target.closest('.row'); if(r) select(r.dataset.id, true);
});
$('#reader').addEventListener('click', e=>{
  const j = state.jobs.find(x=>x.id===state.selection); if(!j) return;
  const act = e.target.closest('[data-act]');
  const dm  = e.target.closest('[data-dm]');
  if(dm){ state.draftMode = dm.dataset.dm; renderDetail(); return; }
  if(!act) return;
  const a = act.dataset.act;
  if(a==='close'){ $('#reader').classList.remove('open'); }
  if(a==='apply'){
    toast('Application page opened in a new tab.', {label:'Mark as applied', fn:()=>{ setStatus(j.id,'applied'); afterStatus(); }});
  }
  if(a==='draft'){ state.draftOpen = !state.draftOpen; renderDetail(); }
  if(a==='copydraft'){ const v = $('#draftArea').value; if(v) copyText(v, 'Draft copied — paste it into the application.'); }
  if(a==='save'){ setStatus(j.id,'saved'); afterStatus(); }
  if(a==='applied'){ setStatus(j.id,'applied'); afterStatus(); }
  if(a==='skip'){
    setStatus(j.id,'skipped'); afterStatus();
    const nextId = state.vis.find(id=>id!==j.id && !stOf(id));
    if(nextId) select(nextId);
    toast('Listing skipped.', {label:'Undo', fn:()=>{ setStatus(j.id,'skipped'); afterStatus(); }});
  }
});
$('#reader').addEventListener('input', debounce(e=>{
  const j = state.jobs.find(x=>x.id===state.selection); if(!j) return;
  if(e.target.id==='noteArea'){
    const notes = store.get('notes',{}); notes[j.id] = e.target.value; store.set('notes',notes);
  }
}, 350));
document.querySelector('.edition-bar').addEventListener('change', e=>{
  if(e.target.id!=='goalInput') return;
  const v = Math.max(1, Math.min(30, parseInt(e.target.value)||5));
  settings.goal = v; saveSettings(); renderMast();
});
$('#feedAdd').addEventListener('click', addFeed);
$('#feedUrl').addEventListener('keydown', e=>{ if(e.key==='Enter') addFeed(); });
$('#drFeedList').addEventListener('click', e=>{
  const b = e.target.closest('[data-rm]'); if(!b) return;
  settings.feeds = (settings.feeds||[]).filter(u=>u!==b.dataset.rm);
  saveSettings(); renderDrawerDynamic(); publishNow(false);
});
function addFeed(){
  const v = $('#feedUrl').value.trim(); if(!v) return;
  let u; try { u = new URL(v); } catch(e){ return toast('That does not look like a valid URL.'); }
  if(!/^https?:$/.test(u.protocol)) return toast('Feed URLs need to start with http(s)://');
  if((settings.feeds||[]).includes(u.href)) return toast('Already following that feed.');
  settings.feeds = [...(settings.feeds||[]), u.href]; saveSettings();
  $('#feedUrl').value='';
  renderDrawerDynamic(); publishNow(false);
  toast('Feed added — publishing a fresh edition.');
}
document.addEventListener('keydown', e=>{
  if($('#drawer').classList.contains('open') && e.key==='Escape'){ closeDrawer(); return; }
  if(e.key==='Escape'){ $('#reader').classList.remove('open'); return; }
  if(/INPUT|TEXTAREA|SELECT/.test(e.target.tagName) || e.target.isContentEditable) return;
  if(e.key==='ArrowDown' || e.key==='j'){ e.preventDefault(); nav(1); }
  else if(e.key==='ArrowUp' || e.key==='k'){ e.preventDefault(); nav(-1); }
  else if(e.key==='Enter'){ if(e.target.tagName!=='BUTTON') applySelected(); }
  else if(e.key==='s' || e.key==='S'){ const j=state.jobs.find(x=>x.id===state.selection); if(j){ setStatus(j.id,'saved'); afterStatus(); } }
  else if(e.key==='a' || e.key==='A'){ const j=state.jobs.find(x=>x.id===state.selection); if(j){ setStatus(j.id,'applied'); afterStatus(); } }
});

function captureBookmark(){
  const origin = location.origin;
  return "javascript:(()=>{const h=location.hostname;let board='Other';if(/indeed/i.test(h))board='Indeed';else if(/monster/i.test(h))board='Monster';else if(/careerbuilder/i.test(h))board='CareerBuilder';else if(/dice/i.test(h))board='Dice';const jobs=[];const seen=new Set();for(const a of document.querySelectorAll('a[href]')){let href=a.href.split('#')[0];const title=(a.innerText||a.getAttribute('aria-label')||'').trim().replace(/\\s+/g,' ');if(title.length<6||title.length>160||seen.has(href))continue;if(!/viewjob|[?&]jk=|job-detail|job-opening|\\/job\\//i.test(href))continue;seen.add(href);jobs.push({board,title:title.slice(0,140),url:href,snippet:((a.closest('article,li,div')||{}).innerText||'').replace(/\\s+/g,' ').slice(0,240)});if(jobs.length>=20)break;}if(!jobs.length){alert('No job links on this page yet. Scroll the results, then click Capture jobs again.');return;}window.open('"+origin+"/#import='+encodeURIComponent(JSON.stringify({jobs})));})();";
}
async function importFromHash(){
  const hash = location.hash || '';
  if(!hash.startsWith('#import=')) return false;
  const encoded = hash.slice('#import='.length);
  history.replaceState(null, '', location.pathname + location.search);
  let payload;
  try { payload = JSON.parse(decodeURIComponent(encoded)); }
  catch(e){ return false; }
  const jobs = payload.jobs || payload;
  if(!Array.isArray(jobs) || !jobs.length) return false;
  toast('Adding '+jobs.length+' listings from your browser…');
  const r = await fetch('/api/jobs/import', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({jobs})
  });
  if(!r.ok) throw new Error('import failed');
  const data = await r.json();
  toast('Added '+(data.imported||0)+' listings to today\u2019s edition.');
  return true;
}

function startClock(){
  const tick = ()=>{
    const now = new Date();
    $('#clock').textContent = now.toLocaleTimeString('en-US',{hour12:true});
    $('#clockDate').textContent = now.toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric'}).toUpperCase() + ' · №' + Math.max(edNo,1);
    const diff = next9am() - now;
    const h=Math.floor(diff/36e5), m=Math.floor(diff%36e5/6e4), s=Math.floor(diff%6e4/1e3);
    const cd = $('#countdown');
    cd.textContent = `NEXT EDITION 9:00 AM · IN ${pad(h)}:${pad(m)}:${pad(s)}`;
    cd.classList.toggle('soon', diff < 36e5);
  };
  tick(); setInterval(tick, 1000);
  setInterval(()=>{ if(editionDue() && !state.publishing) publishNow(true); }, 30000);
}

async function boot(){
  const imported = await importFromHash().catch(()=>false);
  const cache = store.get('jobs', null);
  if(cache && Array.isArray(cache.jobs) && cache.jobs.length){
    state.jobs = cache.jobs.map(j=>({...j, postedAt:new Date(j.postedAt), matched:j.matched||[]}));
    state.edition = store.get('edition', null);
  }
  renderBoards(); renderProfChips(); refreshIcons();
  renderAll(false);
  if(imported || !state.edition || editionDue() || (cache && cache.degraded))
    publishNow(!state.edition);
  startClock();
}
$('#btnCopyCapture').addEventListener('click', ()=>{
  copyText(captureBookmark(), 'Bookmark copied. Save it as “Capture jobs”, then click it on a results page.');
});
boot();
