// νοῦς Dashboard — live.js (Living Knowledge Graph)
// Enhanced: decay animations, pulse effects, reasoning path highlight, stats panel

const API = window.location.origin + '/api';
const COLOR = {
  person:'#3a8fff', project:'#2eff8a', concept:'#b06bff',
  tool:'#ff8c40', policy:'#ff6060', category:'#888888', unknown:'#555'
};
const CYAN='#00d4ff', DIM='rgba(107,127,163,.6)', GREEN='#00ff9f', RED='#ff4466',
      ORANGE='#ff8c40', PURPLE='#7b2fff';

// ── State ────────────────────────────────────────────────────────────────
let sim, svg, gRoot, nodeG, linkG, labelG;
let nodes = [], links = [], nodeMap = {};
let selectedId = null;
let _breatheInterval = null;

// ── Bootstrap ────────────────────────────────────────────────────────────
(async function boot() {
  const [kg, stats] = await Promise.all([
    fetch(API+'/kg').then(r=>r.json()).catch(()=>({entities:[],relations:[]})),
    fetch(API+'/stats').then(r=>r.json()).catch(()=>({})),
  ]);
  initGraph(kg);
  updateStats(stats);
  connectSSE();
  setInterval(refreshKG, 30000);
  // Load graph stats
  loadGraphStats();
  setInterval(loadGraphStats, 60000);
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
  // Glow filter for highlighted path
  const pathGlow = defs.append('filter').attr('id','glow-path')
    .attr('x','-50%').attr('y','-50%').attr('width','200%').attr('height','200%');
  pathGlow.append('feGaussianBlur').attr('stdDeviation','5').attr('result','blur');
  const pm = pathGlow.append('feMerge');
  pm.append('feMergeNode').attr('in','blur');
  pm.append('feMergeNode').attr('in','SourceGraphic');

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

  buildGraphData(kg);

  sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d=>d.id).distance(80).strength(.3))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(W/2, H/2).strength(.06))
    .force('collide', d3.forceCollide(d => R(d)+10))
    .on('tick', ticked);

  renderGraph();
  startBreatheEffect();
}

function buildGraphData(kg) {
  nodeMap = {};
  nodes.length = 0;
  links.length = 0;

  kg.entities.forEach(e => {
    const n = {
      id: e.id, type: e.type,
      name: (e.props||{}).name_zh ? ((e.props||{}).name_zh + ' ' + ((e.props||{}).name||'')) : ((e.props||{}).name || e.id.split(':').pop()),
      props: e.props || {},
      confidence: e.confidence || 1,
      age_hours: e.age_hours || 0,
      degree: 0, isNew: false,
    };
    nodeMap[e.id] = n;
    nodes.push(n);
  });

  kg.relations.forEach(r => {
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

  document.getElementById('cnt-e').textContent = nodes.length;
  document.getElementById('cnt-r').textContent = links.length;
}

const R = d => Math.max(5, Math.min(20, 5 + (d.degree||0) * 1.8));

function renderGraph() {
  // Links — smooth transitions for width and opacity (decay animation)
  const link = linkG.selectAll('line').data(links, d => `${sid(d.source)}-${sid(d.target)}-${d.rtype}`);
  link.exit().transition().duration(800).attr('stroke-opacity',0).remove();
  const linkEnter = link.enter().append('line')
    .attr('stroke', CYAN)
    .attr('stroke-width', 0)
    .attr('stroke-opacity', 0)
    .attr('marker-end','url(#arrow)')
    .style('transition', 'stroke-width 2s ease, stroke-opacity 2s ease');
  // Animate in new edges
  linkEnter.transition().duration(1200).ease(d3.easeCubicOut)
    .attr('stroke-width', d => Math.max(.5, d.effective_confidence * 3))
    .attr('stroke-opacity', d => Math.max(.15, .1 + d.effective_confidence * .5));
  // Update existing edges with smooth transition (decay animation)
  link.transition().duration(2000).ease(d3.easeLinear)
    .attr('stroke-width', d => Math.max(.5, d.effective_confidence * 3))
    .attr('stroke-opacity', d => Math.max(.15, .1 + d.effective_confidence * .5));

  // Edge labels
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

  // New nodes: start at center and "spring out" (self-growth animation)
  if (nodes.some(n => n.isNew)) {
    const wrap = document.getElementById('gwrap');
    const cx = wrap.clientWidth / 2, cy = wrap.clientHeight / 2;
    nodeEnter.filter(d => d.isNew)
      .attr('transform', `translate(${cx},${cy})`)
      .attr('opacity', 0)
      .transition().duration(1000).ease(d3.easeBackOut.overshoot(1.5))
      .attr('opacity', 1);
  }

  // Main circle
  nodeEnter.append('circle').attr('class','main-circle')
    .attr('r', d => d.isNew ? 0 : R(d))
    .attr('fill', d => COLOR[d.type]||COLOR.unknown)
    .attr('fill-opacity', .85)
    .attr('stroke', d => COLOR[d.type]||COLOR.unknown)
    .attr('stroke-width', 1.5).attr('stroke-opacity', .5)
    .attr('filter', d => `url(#glow-${d.type in COLOR ? d.type : 'unknown'})`)
    .transition().duration(d => d.isNew ? 1200 : 800)
    .ease(d => d.isNew ? d3.easeElasticOut : d3.easeLinear)
    .attr('r', d => R(d));

  // Confidence ring
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
    .text(d => d.name.length > 16 ? d.name.slice(0,14)+'...' : d.name);

  // Interactions
  const allNodes = nodeEnter.merge(node);
  allNodes.on('mouseover', onNodeHover).on('mousemove', onNodeMove)
    .on('mouseout', onNodeOut).on('click', onNodeClick).on('dblclick', onNodeDblClick);

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

// ── Breathing effect for high-degree nodes ──────────────────────────────
function startBreatheEffect() {
  if (_breatheInterval) clearInterval(_breatheInterval);
  _breatheInterval = setInterval(() => {
    nodeG.selectAll('g.node').select('.main-circle').each(function(d) {
      if (d.degree >= 4) {
        const el = d3.select(this);
        const baseR = R(d);
        const phase = (Date.now() / 1500) % (Math.PI * 2);
        const pulse = 1 + Math.sin(phase) * 0.12;
        el.attr('r', baseR * pulse);
        // Glow intensity modulation
        el.attr('stroke-opacity', 0.3 + Math.sin(phase) * 0.25);
      }
    });
  }, 50);
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

  linkG.selectAll('line').attr('stroke-opacity', l => {
    const s = sid(l.source), t = sid(l.target);
    if (s===d.id || t===d.id) return .8;
    return .08;
  });
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
  openEntityPanel(d);
}
function onNodeDblClick(e, d) {
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

// ── Entity Detail Panel ──────────────────────────────────────────────────
function openEntityPanel(d) {
  const panel = document.getElementById('entity-panel');
  const props = d.props || {};

  // Header
  document.getElementById('ep-id').textContent = d.id;
  document.getElementById('ep-name').textContent = props.name_zh || props.name || d.name;
  document.getElementById('ep-name-en').textContent = props.name_zh ? (props.name || '') : '';
  const badge = document.getElementById('ep-type');
  badge.textContent = d.type;
  badge.style.color = COLOR[d.type] || COLOR.unknown;
  badge.style.borderColor = COLOR[d.type] || COLOR.unknown;
  badge.style.background = (COLOR[d.type] || COLOR.unknown) + '15';

  // Confidence
  const confPct = (d.confidence * 100).toFixed(0);
  document.getElementById('ep-conf-val').textContent = confPct + '%';
  const fill = document.getElementById('ep-conf-fill');
  fill.style.width = confPct + '%';
  fill.style.background = d.confidence > .7 ? GREEN : d.confidence > .4 ? ORANGE : RED;

  // Props
  const propsEl = document.getElementById('ep-props');
  const skipKeys = new Set(['name', 'name_zh']); // already shown in header
  const sortedKeys = Object.keys(props).filter(k => !skipKeys.has(k)).sort();
  if (sortedKeys.length === 0) {
    propsEl.innerHTML = '<div style="color:var(--dim);font-size:.55rem">无额外属性</div>';
  } else {
    let html = '';
    sortedKeys.forEach(k => {
      let val = props[k];
      if (typeof val === 'object') val = JSON.stringify(val, null, 1);
      if (typeof val === 'string' && val.length > 200) val = val.slice(0, 197) + '...';
      html += `<div class="ep-prop"><span class="ep-prop-key">${k}</span><span class="ep-prop-val">${val}</span></div>`;
    });
    propsEl.innerHTML = html;
  }

  // Relations
  const relsEl = document.getElementById('ep-rels');
  const rels = [];
  links.forEach(l => {
    const s = sid(l.source), t = sid(l.target);
    if (s === d.id) {
      const target = nodeMap[t];
      rels.push({ dir: '→', rtype: l.rtype, node: target, id: t });
    } else if (t === d.id) {
      const source = nodeMap[s];
      rels.push({ dir: '←', rtype: l.rtype, node: source, id: s });
    }
  });
  if (rels.length === 0) {
    relsEl.innerHTML = '<div style="color:var(--dim);font-size:.55rem">无关联实体</div>';
  } else {
    let html = '';
    rels.sort((a, b) => a.rtype.localeCompare(b.rtype));
    rels.forEach(r => {
      const name = r.node ? r.node.name : r.id.split(':').pop();
      const type = r.node ? r.node.type : 'unknown';
      const color = COLOR[type] || COLOR.unknown;
      html += `<div class="ep-rel" onclick="openEntityPanel(nodeMap['${r.id}'])">
        <div class="ep-rel-dot" style="background:${color}"></div>
        <span class="ep-rel-arrow">${r.dir}</span>
        <span class="ep-rel-type">${r.rtype}</span>
        <span class="ep-rel-name">${name.length > 24 ? name.slice(0,22)+'...' : name}</span>
      </div>`;
    });
    relsEl.innerHTML = html;
  }

  // Highlight this node + neighbors
  selectedId = d.id;
  const nb = new Set([d.id]);
  links.forEach(l => {
    if(sid(l.source)===d.id) nb.add(sid(l.target));
    if(sid(l.target)===d.id) nb.add(sid(l.source));
  });
  nodeG.selectAll('g.node').attr('opacity', n => nb.has(n.id) ? 1 : .15);
  linkG.selectAll('line').attr('stroke-opacity', l =>
    nb.has(sid(l.source)) && nb.has(sid(l.target)) ? .8 : .03);
  labelG.selectAll('text').attr('opacity', l =>
    nb.has(sid(l.source)) && nb.has(sid(l.target)) ? .8 : 0);

  panel.classList.add('open');
}

function closeEntityPanel() {
  document.getElementById('entity-panel').classList.remove('open');
  selectedId = null;
  resetHighlight();
}
window.closeEntityPanel = closeEntityPanel;
window.openEntityPanel = openEntityPanel;
function resetHighlight() {
  nodeG.selectAll('g.node').attr('opacity', 1);
  linkG.selectAll('line').attr('stroke-opacity', d => Math.max(.15, .1 + d.effective_confidence * .5));
  labelG.selectAll('text').attr('opacity', 0);
}
svg && d3.select('#kg-svg').on('click', () => { if(selectedId){selectedId=null;resetHighlight();closeEntityPanel();} });

// ── Reasoning path highlight (electric current effect) ────────────────
function highlightReasoningPath(kgContext, proofTrace) {
  if (!kgContext || !kgContext.length) return;

  const ids = new Set(kgContext.map(c => c.id));
  const relatedEdgeIds = new Set();

  // Find edges connecting context nodes
  links.forEach(l => {
    const s = sid(l.source), t = sid(l.target);
    if (ids.has(s) && ids.has(t)) relatedEdgeIds.add(`${s}-${t}-${l.rtype}`);
    if (ids.has(s) || ids.has(t)) relatedEdgeIds.add(`${s}-${t}-${l.rtype}`);
  });

  // Sequentially light up nodes (like current flow)
  const contextIds = kgContext.map(c => c.id);
  contextIds.forEach((id, i) => {
    setTimeout(() => {
      nodeG.selectAll('g.node').filter(d => d.id === id)
        .select('.main-circle')
        .transition().duration(300)
        .attr('stroke', CYAN).attr('stroke-width', 4)
        .attr('stroke-opacity', 1)
        .attr('fill-opacity', 1)
        .transition().duration(2000)
        .attr('stroke-width', 1.5).attr('stroke-opacity', .5).attr('fill-opacity', .85);
    }, i * 200);
  });

  // Light up edges with flow animation
  linkG.selectAll('line').each(function(d) {
    const key = `${sid(d.source)}-${sid(d.target)}-${d.rtype}`;
    if (relatedEdgeIds.has(key)) {
      d3.select(this)
        .attr('stroke', PURPLE)
        .attr('stroke-opacity', .9)
        .attr('stroke-width', 3)
        .classed('path-highlight', true)
        .transition().delay(800).duration(2500)
        .attr('stroke', CYAN)
        .attr('stroke-opacity', d => Math.max(.15, .1 + d.effective_confidence * .5))
        .attr('stroke-width', d => Math.max(.5, d.effective_confidence * 3))
        .on('end', function() { d3.select(this).classed('path-highlight', false); });
    }
  });

  // Dim non-related nodes briefly
  nodeG.selectAll('g.node')
    .attr('opacity', d => ids.has(d.id) ? 1 : .15)
    .transition().delay(2000).duration(1000)
    .attr('opacity', 1);
}

// ── KG Refresh ───────────────────────────────────────────────────────────
async function refreshKG() {
  try {
    const kg = await fetch(API+'/kg').then(r=>r.json());
    const oldIds = new Set(nodes.map(n=>n.id));
    const oldConfMap = {};
    links.forEach(l => {
      const key = `${sid(l.source)}-${sid(l.target)}`;
      oldConfMap[key] = l.effective_confidence;
    });

    const born = kg.entities.filter(e => !oldIds.has(e.id));

    buildGraphData(kg);

    born.forEach(e => { if(nodeMap[e.id]) nodeMap[e.id].isNew = true; });

    // Detect confidence changes for edge weight animation
    links.forEach(l => {
      const key = `${sid(l.source)}-${sid(l.target)}`;
      const oldConf = oldConfMap[key];
      if (oldConf !== undefined && Math.abs(oldConf - l.effective_confidence) > 0.01) {
        l._confChanged = true;
        l._confDelta = l.effective_confidence - oldConf;
      }
    });

    sim.nodes(nodes);
    sim.force('link').links(links);
    sim.alpha(.3).restart();

    renderGraph();

    // Flash edges with changed confidence
    linkG.selectAll('line').each(function(d) {
      if (d._confChanged) {
        const flashColor = d._confDelta > 0 ? RED : GREEN;
        d3.select(this)
          .attr('stroke', flashColor)
          .transition().duration(300).attr('stroke-opacity', .9)
          .transition().duration(2000).attr('stroke', CYAN)
          .attr('stroke-opacity', dd => Math.max(.15, .1 + dd.effective_confidence * .5));
        delete d._confChanged;
        delete d._confDelta;
      }
    });

    born.forEach(e => {
      addEvent('kg', `新实体: ${(e.props||{}).name_zh || (e.props||{}).name || e.id.split(':').pop()} (${e.type})`);
    });

  } catch(e) { console.warn('KG refresh failed:', e); }
}

// ── Stats ────────────────────────────────────────────────────────────────
function updateStats(stats) {
  if (stats.total) {
    document.getElementById('cnt-shadow').textContent = stats.total.toLocaleString();
    document.getElementById('cnt-cons').textContent = (stats.consistency_pct||0).toFixed(1)+'%';
  }
}

// ── SSE Event Stream (Loop 42: real gate events + incremental KG) ─────────
function connectSSE() {
  const es = new EventSource(API+'/events');
  const indicator = document.getElementById('live-indicator');

  es.onmessage = (e) => {
    try {
      const evt = JSON.parse(e.data);
      if (evt.type === 'heartbeat') {
        indicator.style.color = GREEN;
        return;
      }
      if (evt.type === 'gate_decision') {
        const d = evt.data;
        const v = d.verdict;
        const cls = v === 'block' ? 'block' : v === 'confirm' ? 'confirm' : '';
        const rules = (d.matched_rules || []).join(',');
        const detail = rules ? ` [${rules}]` : '';
        addEvent(cls, `${d.tool} → ${v.toUpperCase()}${detail} (${d.layer_path||'?'}, ${d.latency_ms?.toFixed(0)||'?'}ms)`);

        // Highlight KG entities involved in this decision
        if (d.kg_entities && d.kg_entities.length) {
          highlightGateDecision(d.kg_entities, v);
        }
      }
      if (evt.type === 'shadow_decision') {
        const d = evt.data;
        addEvent('', `[shadow] ${d.tool} → ${d.verdict}`);
      }
      if (evt.type === 'kg_changed') {
        addEvent('kg', `KG 变更: ${evt.data.entities||'?'}E / ${evt.data.relations||'?'}R`);
        refreshKG();  // Incremental refresh with new entity animation
      }
    } catch(err) {}
  };
  es.onerror = () => {
    indicator.style.color = RED;
    setTimeout(() => connectSSE(), 5000);
  };
}

// ── Highlight nodes/edges for a gate decision (electric pulse) ────────────
function highlightGateDecision(entityIds, verdict) {
  if (!entityIds || !entityIds.length) return;

  const ids = new Set(entityIds);
  const vColor = verdict === 'block' ? RED : verdict === 'confirm' ? ORANGE : GREEN;

  // Pulse involved nodes
  entityIds.forEach((id, i) => {
    setTimeout(() => {
      nodeG.selectAll('g.node').filter(d => d.id === id)
        .select('.main-circle')
        .transition().duration(200)
        .attr('stroke', vColor).attr('stroke-width', 5)
        .attr('stroke-opacity', 1)
        .transition().duration(1500)
        .attr('stroke', d => COLOR[d.type]||COLOR.unknown)
        .attr('stroke-width', 1.5).attr('stroke-opacity', .5);
    }, i * 150);
  });

  // Pulse involved edges
  linkG.selectAll('line').each(function(d) {
    const s = sid(d.source), t = sid(d.target);
    if (ids.has(s) || ids.has(t)) {
      d3.select(this)
        .transition().duration(200)
        .attr('stroke', vColor).attr('stroke-opacity', .9).attr('stroke-width', 4)
        .transition().duration(2000)
        .attr('stroke', CYAN)
        .attr('stroke-opacity', dd => Math.max(.15, .1 + dd.effective_confidence * .5))
        .attr('stroke-width', dd => Math.max(.5, dd.effective_confidence * 3));
    }
  });
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
  while (list.children.length > MAX_EVENTS) list.removeChild(list.lastChild);
}

// ── Interactive Reasoning (enhanced) ─────────────────────────────────────
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

    const v = data.verdict?.action || 'unknown';
    const vColor = v==='block' ? RED : v==='allow' ? GREEN : ORANGE;
    const ruleId = data.verdict?.rule_id || '';

    // Build inline proof trace
    const trace = data.proof_trace || {};
    const steps = trace.steps || [];
    let inlineTraceHtml = '';
    if (steps.length) {
      inlineTraceHtml = `<div class="inline-trace">
        <div class="inline-trace-header" onclick="this.nextElementSibling.classList.toggle('open')">
          <span>推理轨迹 (${steps.length} steps)</span>
          <span style="font-size:.5rem">展开 ▾</span>
        </div>
        <div class="inline-trace-body">`;
      steps.forEach(step => {
        const cls = step.verdict === 'match' ? 'match' : 'no-match';
        inlineTraceHtml += `<div class="inline-trace-step ${cls}">
          <span style="color:var(--cyan);font-weight:700">${step.rule_id}</span>
          <span style="color:${step.verdict==='match'?RED:GREEN};font-size:.5rem;margin-left:6px">${step.verdict}</span>
          ${Object.keys(step.fact_bindings||{}).length ?
            `<div style="color:var(--orange);font-size:.5rem;margin-top:2px">${JSON.stringify(step.fact_bindings)}</div>` : ''}
        </div>`;
      });
      inlineTraceHtml += '</div></div>';
    }

    // Reasoning chain (Datalog path)
    let chainHtml = '';
    const chain = data.reasoning_chain || [];
    if (chain.length) {
      chainHtml = `<div style="margin-top:6px;padding:6px 8px;background:rgba(0,212,255,.04);
        border-radius:4px;border-left:2px solid var(--cyan);font-size:.55rem">
        <span style="color:var(--cyan);font-weight:700">推理链路</span>`;
      chain.forEach(c => {
        if (c.step === 'entity_lookup') {
          chainHtml += `<div>🔍 ${c.found} <span style="color:var(--dim)">(${c.type}, conf=${(c.confidence*100).toFixed(0)}%)</span></div>`;
        } else if (c.step === 'relation') {
          chainHtml += `<div>→ ${c.from} <span style="color:var(--purple)">${c.type}</span> ${c.to}</div>`;
        } else if (c.step === 'constraint_match') {
          chainHtml += `<div>⚡ <span style="color:var(--red)">${c.rule_id}</span> matched ${JSON.stringify(c.bindings||{})}</div>`;
        } else if (c.step === 'category_policy') {
          chainHtml += `<div>📋 category:${c.category} (conf=${(c.confidence*100).toFixed(0)}%)</div>`;
        }
      });
      chainHtml += '</div>';
    }

    // Semantic verdict section
    let semanticHtml = '';
    if (data.semantic_verdict) {
      const sv = data.semantic_verdict;
      semanticHtml = `<div style="margin-top:6px;padding:6px 8px;background:rgba(123,47,255,.08);
        border-radius:4px;border-left:2px solid var(--purple);font-size:.55rem">
        <span style="color:var(--purple);font-weight:700">语义层</span>
        <span style="color:${sv.action==='block'?RED:GREEN}">${sv.action}</span>
        · ${(sv.confidence*100).toFixed(0)}%
        ${sv.reason ? `<div style="color:var(--dim);margin-top:2px">${sv.reason}</div>` : ''}
      </div>`;
    }

    result.innerHTML =
      `<div style="color:${vColor};font-weight:700;font-size:.8rem">${v.toUpperCase()}</div>`+
      (ruleId ? `<div style="color:var(--dim);font-size:.55rem">rule: ${ruleId}</div>` : '')+
      `<div style="margin-top:4px">${data.verdict?.reason || ''}</div>`+
      `<div style="margin-top:4px;color:var(--dim);font-size:.55rem">层路径: ${data.layer_path||'—'} · ${data.latency_ms?.toFixed(1)||'?'}ms</div>`+
      (data.kg_context?.length ?
        `<div style="margin-top:4px;color:var(--dim);font-size:.55rem">KG 关联: ${data.kg_context.map(c=>
          `<span style="color:var(--cyan);cursor:pointer" onclick="focusNode('${c.id}')">${c.name}</span>`
        ).join(', ')}</div>` : '')+
      chainHtml +
      semanticHtml +
      inlineTraceHtml +
      `<div style="margin-top:6px"><a href="#" onclick="showTrace(event)" style="color:var(--cyan);font-size:.55rem">全屏查看轨迹 →</a></div>`;

    window._lastTrace = data;

    // Highlight reasoning path in KG (electric current animation)
    highlightReasoningPath(data.kg_context, data.proof_trace);

    addEvent(v==='block'?'block':v==='confirm'?'confirm':'',
      `Reason: "${question.slice(0,30)}..." -> ${v}`);

  } catch(err) {
    result.innerHTML = `<span style="color:var(--red)">推理失败: ${err.message}</span>`;
  }
  btn.disabled = false;
  btn.textContent = '推理 ▸';
}

// Focus on a specific node by ID
function focusNode(id) {
  const d = nodeMap[id];
  if (!d) return;
  selectedId = id;
  const nb = new Set([id]);
  links.forEach(l => {
    if(sid(l.source)===id) nb.add(sid(l.target));
    if(sid(l.target)===id) nb.add(sid(l.source));
  });
  nodeG.selectAll('g.node').attr('opacity', n => nb.has(n.id) ? 1 : .08);
  linkG.selectAll('line').attr('stroke-opacity', l =>
    nb.has(sid(l.source)) && nb.has(sid(l.target)) ? .8 : .03);
}
window.focusNode = focusNode;

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

  if (data.facts_extracted && Object.keys(data.facts_extracted).length) {
    html += `<div style="background:rgba(0,212,255,.05);padding:8px 10px;border-radius:6px;margin-bottom:12px;font-size:.65rem">
      <b style="color:var(--cyan)">提取的事实:</b><br>`;
    for (const [k,v] of Object.entries(data.facts_extracted)) {
      html += `<span style="color:var(--orange)">${k}</span>: ${JSON.stringify(v)}<br>`;
    }
    html += '</div>';
  }

  steps.forEach((step, i) => {
    const isMatch = step.verdict === 'match';
    html += `<div class="trace-step ${step.verdict}" style="animation-delay:${i*100}ms">
      <span class="rule">${step.rule_id}</span>
      <span class="verdict-tag ${isMatch?'vt-block':'vt-allow'}">${step.verdict}</span>
      ${Object.keys(step.fact_bindings||{}).length ?
        `<div class="binding">${JSON.stringify(step.fact_bindings)}</div>` : ''}
    </div>`;
  });

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

  // KG subgraph highlight
  if (data.kg_context?.length) {
    html += `<div style="margin-top:12px;padding:10px;background:rgba(0,212,255,.05);border-radius:6px;
      border-left:3px solid var(--cyan);font-size:.65rem">
      <b style="color:var(--cyan)">关联子图</b><br>`;
    data.kg_context.forEach(c => {
      html += `<span style="color:var(--text)">${c.name}</span>
        <span style="color:var(--dim)">(${c.type})</span> `;
    });
    html += '</div>';
  }

  const v = trace.final_verdict || data.verdict?.action || 'unknown';
  html += `<div class="trace-verdict ${v}">
    最终裁决: ${v.toUpperCase()}
  </div>`;

  content.innerHTML = html;
  overlay.style.display = 'block';
}
window.showTrace = showTrace;

function closeTrace(e) {
  if (e.target === document.getElementById('trace-overlay')) {
    document.getElementById('trace-overlay').style.display = 'none';
  }
}
window.closeTrace = closeTrace;

// ── Graph Stats Panel ────────────────────────────────────────────────────
function toggleStats() {
  const panel = document.getElementById('stats-panel');
  const btn = document.getElementById('stats-toggle');
  panel.classList.toggle('open');
  btn.classList.toggle('active');
  if (panel.classList.contains('open')) loadGraphStats();
}
window.toggleStats = toggleStats;

async function loadGraphStats() {
  try {
    const data = await fetch(API+'/graph-stats').then(r=>r.json());
    renderPieChart(data.type_distribution || {});
    renderTypeBars(data.type_distribution || {});
    renderTopConnected(data.top_connected || []);
    renderRecentChanges(data.recent_changes || []);
    renderConfDist(data.confidence_distribution || {});
  } catch(e) {
    // Stats panel is optional — silently fail
  }
}

function renderPieChart(dist) {
  const svg = d3.select('#pie-chart');
  svg.selectAll('*').remove();

  const entries = Object.entries(dist).filter(([,v]) => v > 0);
  if (!entries.length) return;

  const total = entries.reduce((s,[,v]) => s+v, 0);
  const g = svg.append('g').attr('transform', 'translate(60,60)');
  const arc = d3.arc().innerRadius(25).outerRadius(50);
  const pie = d3.pie().value(d => d[1]).sort(null);

  g.selectAll('path').data(pie(entries))
    .enter().append('path')
    .attr('d', arc)
    .attr('fill', d => COLOR[d.data[0]] || '#555')
    .attr('stroke', 'var(--bg)').attr('stroke-width', 1)
    .attr('opacity', 0)
    .transition().duration(800).delay((d,i) => i*100)
    .attr('opacity', .85);

  // Center text
  g.append('text').attr('text-anchor','middle').attr('dy','.35em')
    .attr('fill','var(--text)').attr('font-size','14px').attr('font-weight','700')
    .text(total);
}

function renderTypeBars(dist) {
  const el = document.getElementById('type-bars');
  const total = Object.values(dist).reduce((s,v) => s+v, 0) || 1;
  let html = '';
  for (const [type, count] of Object.entries(dist).sort((a,b) => b[1]-a[1])) {
    const pct = (count/total*100).toFixed(0);
    html += `<div class="sp-bar">
      <span class="sp-bar-label" style="color:${COLOR[type]||'#555'}">${type}</span>
      <div style="flex:1;background:rgba(255,255,255,.05);border-radius:3px;height:6px">
        <div class="sp-bar-fill" style="width:${pct}%;background:${COLOR[type]||'#555'}"></div>
      </div>
      <span class="sp-bar-val">${count}</span>
    </div>`;
  }
  el.innerHTML = html;
}

function renderTopConnected(top5) {
  const el = document.getElementById('top-connected');
  if (!top5.length) { el.innerHTML = '<span style="color:var(--dim);font-size:.55rem">-</span>'; return; }
  let html = '';
  top5.forEach((item, i) => {
    html += `<div class="sp-top-item">
      <span class="sp-top-name" style="cursor:pointer" onclick="focusNode('${item.id}')">${i+1}. ${item.name}</span>
      <span class="sp-top-deg">${item.degree}</span>
    </div>`;
  });
  el.innerHTML = html;
}

function renderRecentChanges(recent) {
  const el = document.getElementById('recent-changes');
  if (!recent.length) { el.innerHTML = '<span style="color:var(--dim);font-size:.55rem">-</span>'; return; }
  let html = '';
  recent.forEach(item => {
    html += `<div class="sp-recent">
      <span class="sp-recent-type">${item.type}</span>
      <span style="cursor:pointer" onclick="focusNode('${item.id}')">${item.name}</span>
      <span class="sp-recent-age">${item.age_hours < 1 ? '<1h' : item.age_hours.toFixed(0)+'h'}</span>
    </div>`;
  });
  el.innerHTML = html;
}

function renderConfDist(dist) {
  const el = document.getElementById('conf-dist');
  const max = Math.max(1, ...Object.values(dist));
  const colors = [RED, ORANGE, '#ffd700', '#a0e060', GREEN];
  let html = '';
  Object.entries(dist).forEach(([range, count], i) => {
    const pct = (count/max*100).toFixed(0);
    html += `<div class="sp-bar">
      <span class="sp-bar-label">${range}</span>
      <div style="flex:1;background:rgba(255,255,255,.05);border-radius:3px;height:6px">
        <div class="sp-bar-fill" style="width:${pct}%;background:${colors[i]||CYAN}"></div>
      </div>
      <span class="sp-bar-val">${count}</span>
    </div>`;
  });
  el.innerHTML = html;
}

// ── Expose functions for onclick handlers ────────────────────────────────
window.askNous = askNous;
