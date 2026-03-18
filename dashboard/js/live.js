// νοῦς Dashboard — live.js (Living Knowledge Graph)
// API-driven, SSE real-time, interactive reasoning

const API = window.location.origin + '/api';
const COLOR = {
  person:'#3a8fff', project:'#2eff8a', concept:'#b06bff',
  tool:'#ff8c40', policy:'#ff6060', category:'#888888', unknown:'#555'
};
const CYAN='#00d4ff', DIM='rgba(107,127,163,.6)', GREEN='#00ff9f', RED='#ff4466', ORANGE='#ff8c40';

// ── State ────────────────────────────────────────────────────────────────
let sim, svg, gRoot, nodeG, linkG, labelG;
let nodes = [], links = [], nodeMap = {};
let selectedId = null;

// ── Bootstrap ────────────────────────────────────────────────────────────
(async function boot() {
  const [kg, stats] = await Promise.all([
    fetch(API+'/kg').then(r=>r.json()).catch(()=>({entities:[],relations:[]})),
    fetch(API+'/stats').then(r=>r.json()).catch(()=>({})),
  ]);
  initGraph(kg);
  updateStats(stats);
  connectSSE();
  // Periodic KG refresh (every 30s — detect new nodes/edges)
  setInterval(refreshKG, 30000);
})();

// ── Graph Init ───────────────────────────────────────────────────────────
function initGraph(kg) {
  const wrap = document.getElementById('gwrap');
  const W = wrap.clientWidth, H = wrap.clientHeight;
  svg = d3.select('#kg-svg').attr('viewBox', `0 0 ${W} ${H}`);

  // Defs
  const defs = svg.append('defs');
  Object.entries(COLOR).forEach(([type, col]) => {
    const f = defs.append('filter').attr('id',`glow-${type}`)
      .attr('x','-50%').attr('y','-50%').attr('width','200%').attr('height','200%');
    f.append('feGaussianBlur').attr('stdDeviation','3').attr('result','blur');
    const m = f.append('feMerge');
    m.append('feMergeNode').attr('in','blur');
    m.append('feMergeNode').attr('in','SourceGraphic');
  });
  defs.append('marker').attr('id','arrow')
    .attr('viewBox','0 0 10 10').attr('refX',18).attr('refY',5)
    .attr('markerWidth',4).attr('markerHeight',4).attr('orient','auto')
    .append('path').attr('d','M0,0 L10,5 L0,10 Z').attr('fill',CYAN).attr('opacity',.4);

  // Grid
  const bgG = svg.append('g');
  for(let x=0;x<W;x+=50) bgG.append('line').attr('x1',x).attr('y1',0).attr('x2',x).attr('y2',H)
    .attr('stroke','rgba(0,212,255,.03)');
  for(let y=0;y<H;y+=50) bgG.append('line').attr('x1',0).attr('y1',y).attr('x2',W).attr('y2',y)
    .attr('stroke','rgba(0,212,255,.03)');

  // Scan line
  const scanGrad = defs.append('linearGradient').attr('id','scanG').attr('x1',0).attr('x2',0).attr('y1',0).attr('y2',1);
  scanGrad.append('stop').attr('offset','0%').attr('stop-color',CYAN).attr('stop-opacity',0);
  scanGrad.append('stop').attr('offset','50%').attr('stop-color',CYAN).attr('stop-opacity',.4);
  scanGrad.append('stop').attr('offset','100%').attr('stop-color',CYAN).attr('stop-opacity',0);
  const scanLine = svg.append('rect').attr('x',0).attr('width',W).attr('height',2).attr('fill','url(#scanG)');
  (function scanAnim(){
    scanLine.attr('y',-3).transition().duration(5000).ease(d3.easeLinear).attr('y',H).on('end',scanAnim);
  })();

  gRoot = svg.append('g');
  svg.call(d3.zoom().scaleExtent([.15,5]).on('zoom', e => gRoot.attr('transform', e.transform)));

  linkG = gRoot.append('g');
  labelG = gRoot.append('g');
  nodeG = gRoot.append('g');

  // Build initial data
  buildGraphData(kg);

  // Force simulation
  sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d=>d.id).distance(80).strength(.3))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(W/2, H/2).strength(.06))
    .force('collide', d3.forceCollide(d => R(d)+10))
    .on('tick', ticked);

  renderGraph();
}

function buildGraphData(kg) {
  nodeMap = {};
  nodes.length = 0;
  links.length = 0;

  kg.entities.forEach(e => {
    const n = {
      id: e.id, type: e.type,
      name: (e.props||{}).name || e.id.split(':').pop(),
      confidence: e.confidence || 1,
      age_hours: e.age_hours || 0,
      degree: 0, isNew: false,
    };
    nodeMap[e.id] = n;
    nodes.push(n);
  });

  kg.relations.forEach(r => {
    // Ensure both endpoints exist
    [r.from, r.to].forEach(id => {
      if (!nodeMap[id]) {
        const n = {id, type:'unknown', name:id.split(':').pop(), confidence:.5, degree:0, isNew:false};
        nodeMap[id] = n;
        nodes.push(n);
      }
    });
    links.push({
      source: r.from, target: r.to,
      rtype: r.type || 'RELATED_TO',
      effective_confidence: r.effective_confidence || r.confidence || 1,
      age_hours: r.age_hours || 0,
    });
  });

  links.forEach(l => {
    if(nodeMap[l.source]) nodeMap[l.source].degree++;
    if(nodeMap[l.target]) nodeMap[l.target].degree++;
  });

  // Update counts
  document.getElementById('cnt-e').textContent = nodes.length;
  document.getElementById('cnt-r').textContent = links.length;
}

const R = d => Math.max(5, Math.min(20, 5 + (d.degree||0) * 1.8));

function renderGraph() {
  // Links — width = effective_confidence, opacity = freshness
  const link = linkG.selectAll('line').data(links, d => `${sid(d.source)}-${sid(d.target)}-${d.rtype}`);
  link.exit().transition().duration(500).attr('stroke-opacity',0).remove();
  const linkEnter = link.enter().append('line')
    .attr('stroke', CYAN)
    .attr('stroke-width', d => Math.max(.5, d.effective_confidence * 3))
    .attr('stroke-opacity', d => Math.max(.15, .1 + d.effective_confidence * .5))
    .attr('marker-end','url(#arrow)');
  linkEnter.merge(link)
    .transition().duration(800)
    .attr('stroke-width', d => Math.max(.5, d.effective_confidence * 3))
    .attr('stroke-opacity', d => Math.max(.15, .1 + d.effective_confidence * .5));

  // Edge labels (on hover, show rtype)
  const edgeLabel = labelG.selectAll('text').data(links, d => `${sid(d.source)}-${sid(d.target)}-${d.rtype}`);
  edgeLabel.exit().remove();
  edgeLabel.enter().append('text')
    .attr('text-anchor','middle').attr('font-size','6px').attr('fill',DIM)
    .attr('pointer-events','none').attr('opacity',0)
    .text(d => d.rtype);

  // Nodes
  const node = nodeG.selectAll('g.node').data(nodes, d => d.id);
  node.exit().transition().duration(500).attr('opacity',0).remove();

  const nodeEnter = node.enter().append('g').attr('class','node').attr('cursor','pointer')
    .call(d3.drag()
      .on('start',(e,d)=>{if(!e.active) sim.alphaTarget(.3).restart(); d.fx=d.x;d.fy=d.y;})
      .on('drag',(e,d)=>{d.fx=e.x;d.fy=e.y;})
      .on('end',(e,d)=>{if(!e.active) sim.alphaTarget(0); d.fx=null;d.fy=null;}));

  // Main circle
  nodeEnter.append('circle').attr('class','main-circle')
    .attr('r', d => d.isNew ? 0 : R(d))
    .attr('fill', d => COLOR[d.type]||COLOR.unknown)
    .attr('fill-opacity', .85)
    .attr('stroke', d => COLOR[d.type]||COLOR.unknown)
    .attr('stroke-width', 1.5).attr('stroke-opacity', .5)
    .attr('filter', d => `url(#glow-${d.type in COLOR ? d.type : 'unknown'})`)
    .transition().duration(800).attr('r', d => R(d));

  // Confidence ring (decaying over time — visual weight indicator)
  nodeEnter.append('circle').attr('class','conf-ring')
    .attr('r', d => R(d) + 3)
    .attr('fill','none')
    .attr('stroke', d => COLOR[d.type]||COLOR.unknown)
    .attr('stroke-width', d => d.confidence * 2)
    .attr('stroke-opacity', .2)
    .attr('stroke-dasharray', d => d.age_hours > 24 ? '2,3' : 'none');

  // Label
  nodeEnter.append('text').attr('class','node-label')
    .attr('text-anchor','middle').attr('dy','-.6em')
    .attr('font-size', d => d.type==='unknown' ? '6px' : '8px')
    .attr('fill', d => d.type==='unknown' ? 'rgba(255,140,64,.6)' : 'rgba(226,232,240,.85)')
    .attr('pointer-events','none')
    .text(d => d.name.length > 16 ? d.name.slice(0,14)+'…' : d.name);

  // Interactions
  const allNodes = nodeEnter.merge(node);
  allNodes.on('mouseover', onNodeHover).on('mousemove', onNodeMove)
    .on('mouseout', onNodeOut).on('click', onNodeClick);

  // Update existing nodes' confidence ring
  allNodes.select('.conf-ring')
    .transition().duration(600)
    .attr('stroke-width', d => d.confidence * 2)
    .attr('stroke-dasharray', d => d.age_hours > 24 ? '2,3' : 'none');
}

function sid(d) { return typeof d === 'object' ? d.id : d; }

function ticked() {
  linkG.selectAll('line')
    .attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
    .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
  labelG.selectAll('text')
    .attr('x',d=>(d.source.x+d.target.x)/2).attr('y',d=>(d.source.y+d.target.y)/2);
  nodeG.selectAll('g.node').attr('transform',d=>`translate(${d.x},${d.y})`);
}

// ── Node Interactions ────────────────────────────────────────────────────
function onNodeHover(e, d) {
  const tt = document.getElementById('tt');
  document.getElementById('tt-type').textContent = d.type;
  document.getElementById('tt-type').style.color = COLOR[d.type]||COLOR.unknown;
  document.getElementById('tt-name').textContent = d.name;
  document.getElementById('tt-meta').innerHTML =
    `连接: ${d.degree} · 置信: ${(d.confidence*100).toFixed(0)}%<br>`+
    `年龄: ${d.age_hours < 1 ? '<1h' : d.age_hours.toFixed(0)+'h'}`;
  const fill = document.getElementById('tt-conf-fill');
  fill.style.width = (d.confidence*100)+'%';
  fill.style.background = d.confidence > .7 ? GREEN : d.confidence > .4 ? ORANGE : RED;
  tt.style.display = 'block';

  // Highlight connected edges
  linkG.selectAll('line').attr('stroke-opacity', l => {
    const s = sid(l.source), t = sid(l.target);
    if (s===d.id || t===d.id) return .8;
    return .08;
  });
  // Show edge labels for connected
  labelG.selectAll('text').attr('opacity', l => {
    const s = sid(l.source), t = sid(l.target);
    return (s===d.id || t===d.id) ? .8 : 0;
  });
}
function onNodeMove(e) {
  const tt = document.getElementById('tt');
  tt.style.left = (e.clientX+14)+'px'; tt.style.top = (e.clientY-10)+'px';
}
function onNodeOut() {
  document.getElementById('tt').style.display = 'none';
  linkG.selectAll('line').attr('stroke-opacity', d => Math.max(.15, .1 + d.effective_confidence * .5));
  labelG.selectAll('text').attr('opacity', 0);
}
function onNodeClick(e, d) {
  e.stopPropagation();
  if (selectedId === d.id) { selectedId = null; resetHighlight(); return; }
  selectedId = d.id;
  const nb = new Set([d.id]);
  links.forEach(l => {
    if(sid(l.source)===d.id) nb.add(sid(l.target));
    if(sid(l.target)===d.id) nb.add(sid(l.source));
  });
  nodeG.selectAll('g.node').attr('opacity', n => nb.has(n.id) ? 1 : .08);
  linkG.selectAll('line').attr('stroke-opacity', l =>
    nb.has(sid(l.source)) && nb.has(sid(l.target)) ? .8 : .03);
  labelG.selectAll('text').attr('opacity', l =>
    nb.has(sid(l.source)) && nb.has(sid(l.target)) ? .8 : 0);
}
function resetHighlight() {
  nodeG.selectAll('g.node').attr('opacity', 1);
  linkG.selectAll('line').attr('stroke-opacity', d => Math.max(.15, .1 + d.effective_confidence * .5));
  labelG.selectAll('text').attr('opacity', 0);
}
svg && d3.select('#kg-svg').on('click', () => { if(selectedId){selectedId=null;resetHighlight();} });

// ── KG Refresh (detect growth/decay) ─────────────────────────────────────
async function refreshKG() {
  try {
    const kg = await fetch(API+'/kg').then(r=>r.json());
    const oldIds = new Set(nodes.map(n=>n.id));
    const newIds = new Set(kg.entities.map(e=>e.id));

    // Detect new nodes
    const born = kg.entities.filter(e => !oldIds.has(e.id));

    // Rebuild
    buildGraphData(kg);

    // Mark new nodes
    born.forEach(e => { if(nodeMap[e.id]) nodeMap[e.id].isNew = true; });

    // Update simulation
    sim.nodes(nodes);
    sim.force('link').links(links);
    sim.alpha(.3).restart();

    renderGraph();

    // Add birth events to feed
    born.forEach(e => {
      addEvent('kg', `🌱 新实体: ${(e.props||{}).name || e.id.split(':').pop()} (${e.type})`);
    });

    // Update edge weights visually (decay animation)
    linkG.selectAll('line').transition().duration(1000)
      .attr('stroke-width', d => Math.max(.5, d.effective_confidence * 3))
      .attr('stroke-opacity', d => Math.max(.15, .1 + d.effective_confidence * .5));

  } catch(e) { console.warn('KG refresh failed:', e); }
}

// ── Stats ────────────────────────────────────────────────────────────────
function updateStats(stats) {
  if (stats.total) {
    document.getElementById('cnt-shadow').textContent = stats.total.toLocaleString();
    document.getElementById('cnt-cons').textContent = (stats.consistency_pct||0).toFixed(1)+'%';
  }
}

// ── SSE Event Stream ─────────────────────────────────────────────────────
function connectSSE() {
  const es = new EventSource(API+'/events');
  const indicator = document.getElementById('live-indicator');

  es.onmessage = (e) => {
    try {
      const evt = JSON.parse(e.data);
      if (evt.type === 'heartbeat') {
        indicator.style.color = GREEN;
        setTimeout(() => indicator.style.color = GREEN, 300);
        return;
      }
      if (evt.type === 'gate_decision') {
        const v = evt.data.verdict;
        const cls = v === 'block' ? 'block' : v === 'confirm' ? 'confirm' : '';
        addEvent(cls, `⚡ ${evt.data.tool} → ${v}`);
      }
      if (evt.type === 'kg_changed') {
        addEvent('kg', `📊 KG 变更: ${evt.data.count} 总元素`);
        refreshKG(); // Trigger immediate refresh
      }
    } catch(err) {}
  };
  es.onerror = () => {
    indicator.style.color = RED;
    setTimeout(() => connectSSE(), 5000);
  };
}

// ── Event Feed ───────────────────────────────────────────────────────────
const MAX_EVENTS = 50;
function addEvent(cls, text) {
  const list = document.getElementById('feed-list');
  const div = document.createElement('div');
  div.className = 'evt ' + cls;
  const now = new Date().toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
  div.innerHTML = `<span class="evt-time">${now}</span> ${text}`;
  list.insertBefore(div, list.firstChild);
  // Trim old events
  while (list.children.length > MAX_EVENTS) list.removeChild(list.lastChild);
}

// ── Interactive Reasoning ────────────────────────────────────────────────
async function askNous() {
  const input = document.getElementById('ask-input');
  const btn = document.getElementById('ask-btn');
  const result = document.getElementById('reason-result');
  const question = input.value.trim();
  if (!question) return;

  btn.disabled = true;
  btn.textContent = '推理中...';
  result.innerHTML = '<span style="color:var(--dim)">正在通过决策引擎推理...</span>';

  try {
    const resp = await fetch(API+'/reason', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({question}),
    });
    const data = await resp.json();

    // Show brief result
    const v = data.verdict?.action || 'unknown';
    const vColor = v==='block' ? RED : v==='allow' ? GREEN : ORANGE;
    result.innerHTML =
      `<div style="color:${vColor};font-weight:700;font-size:.8rem">${v.toUpperCase()}</div>`+
      `<div style="margin-top:4px">${data.verdict?.reason || ''}</div>`+
      `<div style="margin-top:4px;color:var(--dim)">层路径: ${data.layer_path||'—'} · ${data.latency_ms?.toFixed(1)||'?'}ms</div>`+
      (data.kg_context?.length ?
        `<div style="margin-top:6px;color:var(--dim)">KG 关联: ${data.kg_context.map(c=>c.name).join(', ')}</div>` : '')+
      `<div style="margin-top:8px"><a href="#" onclick="showTrace(event)" style="color:var(--cyan);font-size:.6rem">查看完整推理轨迹 →</a></div>`;

    // Store for trace overlay
    window._lastTrace = data;

    // Highlight KG nodes involved
    if (data.kg_context?.length) {
      const ids = new Set(data.kg_context.map(c => c.id));
      nodeG.selectAll('g.node').select('.main-circle')
        .transition().duration(400)
        .attr('stroke-width', d => ids.has(d.id) ? 3 : 1.5)
        .attr('stroke', d => ids.has(d.id) ? CYAN : (COLOR[d.type]||COLOR.unknown));
      // Reset after 3s
      setTimeout(() => {
        nodeG.selectAll('g.node').select('.main-circle')
          .transition().duration(600)
          .attr('stroke-width', 1.5)
          .attr('stroke', d => COLOR[d.type]||COLOR.unknown);
      }, 3000);
    }

    // Add to event feed
    addEvent(v==='block'?'block':v==='confirm'?'confirm':'',
      `🔍 推理: "${question.slice(0,30)}..." → ${v}`);

  } catch(err) {
    result.innerHTML = `<span style="color:var(--red)">推理失败: ${err.message}</span>`;
  }
  btn.disabled = false;
  btn.textContent = '推理 ▸';
}

// Enter key to submit
document.getElementById('ask-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); askNous(); }
});

// ── Proof Trace Overlay ──────────────────────────────────────────────────
function showTrace(e) {
  if(e) e.preventDefault();
  const data = window._lastTrace;
  if (!data) return;

  const overlay = document.getElementById('trace-overlay');
  const content = document.getElementById('trace-content');

  const trace = data.proof_trace || {};
  const steps = trace.steps || [];

  let html = `<h3 style="color:var(--cyan);margin-bottom:12px;font-size:1rem">
    推理轨迹 · Proof Trace</h3>`;
  html += `<div style="color:var(--dim);font-size:.65rem;margin-bottom:16px">
    问题: "${data.question}" · 层路径: ${data.layer_path||'—'} · ${trace.total_ms?.toFixed(1)||'?'}ms</div>`;

  // Facts extracted
  if (data.facts_extracted && Object.keys(data.facts_extracted).length) {
    html += `<div style="background:rgba(0,212,255,.05);padding:8px 10px;border-radius:6px;margin-bottom:12px;font-size:.65rem">
      <b style="color:var(--cyan)">提取的事实:</b><br>`;
    for (const [k,v] of Object.entries(data.facts_extracted)) {
      html += `<span style="color:var(--orange)">${k}</span>: ${JSON.stringify(v)}<br>`;
    }
    html += '</div>';
  }

  // Steps with sequential animation delay
  steps.forEach((step, i) => {
    const isMatch = step.verdict === 'match';
    html += `<div class="trace-step ${step.verdict}" style="animation-delay:${i*100}ms">
      <span class="rule">${step.rule_id}</span>
      <span class="verdict-tag ${isMatch?'vt-block':'vt-allow'}">${step.verdict}</span>
      ${Object.keys(step.fact_bindings||{}).length ?
        `<div class="binding">${JSON.stringify(step.fact_bindings)}</div>` : ''}
    </div>`;
  });

  // Semantic verdict
  if (data.semantic_verdict) {
    const sv = data.semantic_verdict;
    html += `<div style="margin-top:12px;padding:10px;background:rgba(123,47,255,.08);border-radius:6px;
      border-left:3px solid var(--purple);font-size:.65rem">
      <b style="color:var(--purple)">语义判断 (Layer 3)</b><br>
      结论: <span style="color:${sv.action==='block'?RED:GREEN}">${sv.action}</span>
      · 置信: ${(sv.confidence*100).toFixed(0)}%
      · ${sv.latency_ms?.toFixed(0)||'?'}ms<br>
      <span style="color:var(--dim)">${sv.reason||''}</span>
    </div>`;
  }

  // Final verdict
  const v = trace.final_verdict || data.verdict?.action || 'unknown';
  html += `<div class="trace-verdict ${v}">
    最终裁决: ${v.toUpperCase()}
  </div>`;

  content.innerHTML = html;
  overlay.style.display = 'block';
}

function closeTrace(e) {
  if (e.target === document.getElementById('trace-overlay')) {
    document.getElementById('trace-overlay').style.display = 'none';
  }
}
