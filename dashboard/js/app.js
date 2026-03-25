// νοῦς Dashboard — app.js

const COLOR = {
  person:  '#3a8fff',
  project: '#2eff8a',
  concept: '#b06bff',
  event:   '#ff6060',
  resource:'#888888',
  unknown: '#ff8c40'
};
const CYAN='#00d4ff', DIM='rgba(107,127,163,.6)';

// ── Animated counter ────────────────────────────────────────────────────────
function animCount(el, target, suffix='', duration=1400, decimals=0) {
  let start=null;
  const to = typeof target==='number'?target:parseFloat(target);
  const fmt = v => decimals>0 ? v.toFixed(decimals) : Math.round(v).toString();
  const step = ts => {
    if(!start) start=ts;
    const ease = 1-Math.pow(1-Math.min((ts-start)/duration,1),3);
    el.textContent = fmt(to*ease)+suffix;
    if(ease<1) requestAnimationFrame(step);
    else el.textContent = fmt(to)+suffix;
  };
  requestAnimationFrame(step);
}

// ── Bootstrap ────────────────────────────────────────────────────────────────
Promise.all([
  fetch('data/kg.json').then(r=>r.json()),
  fetch('data/stats.json').then(r=>r.json())
]).then(([kg, stats]) => {
  initGraph(kg);
  initMonitor(stats);
}).catch(err => { console.error('Data load failed:', err); });

// ── Knowledge Graph ──────────────────────────────────────────────────────────
function initGraph(kg) {
  const nodeMap = {};
  kg.entities.forEach(e => {
    nodeMap[e.id] = {
      id: e.id, type: e.type,
      name: e.props.name || e.id.split(':').pop(),
      confidence: e.confidence||1, degree: 0
    };
  });
  const links = [];
  kg.relations.forEach(r => {
    [r.from, r.to].forEach(id => {
      if(!nodeMap[id]) {
        const n = id.split(':').pop();
        nodeMap[id] = {id, type:'unknown', name:n, confidence:.5, degree:0};
      }
    });
    links.push({source:r.from, target:r.to, rtype:r.type||'RELATED_TO'});
  });
  const nodes = Object.values(nodeMap);
  links.forEach(l => {
    if(nodeMap[l.source]) nodeMap[l.source].degree++;
    if(nodeMap[l.target]) nodeMap[l.target].degree++;
  });

  // Update navbar counts
  document.getElementById('cnt-e').textContent = nodes.length;
  document.getElementById('cnt-r').textContent = links.length;

  const R = d => Math.max(6, Math.min(22, 6 + d.degree*2));
  const svg = d3.select('#kg-svg');
  const wrap = document.getElementById('gwrap');
  const W = wrap.clientWidth, H = wrap.clientHeight;
  svg.attr('viewBox',`0 0 ${W} ${H}`);

  // Defs
  const defs = svg.append('defs');
  // Glow filters per type
  Object.entries(COLOR).forEach(([type, col]) => {
    const f = defs.append('filter').attr('id',`glow-${type}`).attr('x','-50%').attr('y','-50%').attr('width','200%').attr('height','200%');
    f.append('feGaussianBlur').attr('stdDeviation','4').attr('result','blur');
    const m = f.append('feMerge');
    m.append('feMergeNode').attr('in','blur');
    m.append('feMergeNode').attr('in','SourceGraphic');
  });
  // Arrow marker
  defs.append('marker').attr('id','arrow')
    .attr('viewBox','0 0 10 10').attr('refX',15).attr('refY',5)
    .attr('markerWidth',5).attr('markerHeight',5).attr('orient','auto')
    .append('path').attr('d','M0,0 L10,5 L0,10 Z').attr('fill',CYAN).attr('opacity',.55);

  // Grid background
  const bgG = svg.append('g').attr('class','bg-grid');
  const gridSpacing=40;
  for(let x=0;x<W;x+=gridSpacing) bgG.append('line').attr('x1',x).attr('y1',0).attr('x2',x).attr('y2',H).attr('stroke','rgba(0,212,255,.04)').attr('stroke-width',1);
  for(let y=0;y<H;y+=gridSpacing) bgG.append('line').attr('x1',0).attr('y1',y).attr('x2',W).attr('y2',y).attr('stroke','rgba(0,212,255,.04)').attr('stroke-width',1);

  // Scan line animation
  const scanLine = svg.append('rect').attr('x',0).attr('width',W).attr('height',2)
    .attr('fill','url(#scan-grad)').attr('opacity',.5);
  defs.append('linearGradient').attr('id','scan-grad').attr('x1',0).attr('x2',0).attr('y1',0).attr('y2',1)
    .call(g=>{
      g.append('stop').attr('offset','0%').attr('stop-color',CYAN).attr('stop-opacity',0);
      g.append('stop').attr('offset','50%').attr('stop-color',CYAN).attr('stop-opacity',0.6);
      g.append('stop').attr('offset','100%').attr('stop-color',CYAN).attr('stop-opacity',0);
    });
  (function scanAnim(){
    scanLine.attr('y',-3)
      .transition().duration(4000).ease(d3.easeLinear).attr('y',H)
      .on('end',scanAnim);
  })();

  const g = svg.append('g');

  // Zoom
  svg.call(d3.zoom().scaleExtent([.2,4]).on('zoom', e=>g.attr('transform',e.transform)));

  // Force
  nodes.forEach(n => { n.x=W/2+(Math.random()-.5)*30; n.y=H/2+(Math.random()-.5)*30; });
  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d=>d.id).distance(d=>{
      const s=d.source,t=d.target;
      return (s.type==='unknown'||t.type==='unknown')?90:70;
    }).strength(.35))
    .force('charge', d3.forceManyBody().strength(d=>d.type==='unknown'?-120:-220))
    .force('center', d3.forceCenter(W/2, H/2).strength(.08))
    .force('collide', d3.forceCollide(d=>R(d)+12));

  // Links
  const link = g.append('g').selectAll('line').data(links).join('line')
    .attr('stroke',CYAN).attr('stroke-opacity',.35).attr('stroke-width',1.2)
    .attr('marker-end','url(#arrow)');

  // Link labels (hidden - rtype shown in tooltip on link hover)
  const linkLabel = g.append('g').selectAll('text').data(links).join('text')
    .attr('text-anchor','middle').attr('font-size','7px').attr('fill',DIM)
    .attr('pointer-events','none').attr('opacity',0).text(d=>d.rtype);

  // Nodes
  const node = g.append('g').selectAll('g').data(nodes).join('g')
    .attr('cursor','pointer')
    .call(d3.drag()
      .on('start',(e,d)=>{ if(!e.active) sim.alphaTarget(.3).restart(); d.fx=d.x;d.fy=d.y; })
      .on('drag',(e,d)=>{ d.fx=e.x;d.fy=e.y; })
      .on('end',(e,d)=>{ if(!e.active) sim.alphaTarget(0); d.fx=null;d.fy=null; }));

  node.append('circle')
    .attr('r', d=>R(d))
    .attr('fill', d=>COLOR[d.type]||COLOR.unknown)
    .attr('fill-opacity',.85)
    .attr('stroke',d=>COLOR[d.type]||COLOR.unknown)
    .attr('stroke-width',1.5).attr('stroke-opacity',.6)
    .attr('filter',d=>`url(#glow-${d.type})`);

  // Pulse ring for high-degree nodes
  node.filter(d=>d.degree>=4).append('circle')
    .attr('r', d=>R(d)+4).attr('fill','none')
    .attr('stroke',d=>COLOR[d.type]||COLOR.unknown).attr('stroke-width',.6)
    .attr('stroke-opacity',.3).attr('stroke-dasharray','3,4');

  const nodeLabel = node.append('text')
    .attr('text-anchor','middle').attr('dy','-.7em')
    .attr('font-size', d=>d.type==='unknown'?'7px':'8.5px')
    .attr('fill',d=>d.type==='unknown'?'rgba(255,140,64,.7)':'rgba(226,232,240,.9)')
    .attr('pointer-events','none')
    .text(d=>d.name.length>18?d.name.slice(0,16)+'…':d.name);

  // Tooltip
  const tt=document.getElementById('tt');
  const ttType=document.getElementById('tt-type');
  const ttName=document.getElementById('tt-name');
  const ttMeta=document.getElementById('tt-meta');

  node.on('mouseover',(e,d)=>{
    ttType.textContent=d.type; ttType.style.color=COLOR[d.type]||COLOR.unknown;
    ttName.textContent=d.name;
    const deg=`Connections: ${d.degree}`;
    const conf=`置信度: ${(d.confidence*100).toFixed(0)}%`;
    ttMeta.textContent=`${deg}  ·  ${conf}`;
    tt.style.display='block';
    link.attr('stroke-opacity', l=>{
      const s=l.source.id||l.source, t=l.target.id||l.target;
      return (s===d.id||t===d.id)?.75:.15;
    });
  })
  .on('mousemove',e=>{ tt.style.left=(e.clientX+14)+'px'; tt.style.top=(e.clientY-10)+'px'; })
  .on('mouseout',()=>{ tt.style.display='none'; link.attr('stroke-opacity',.35); });

  // Click highlight
  let sel=null;
  node.on('click',(e,d)=>{
    e.stopPropagation();
    if(sel===d.id){sel=null;node.attr('opacity',1);link.attr('stroke-opacity',.35);nodeLabel.attr('opacity',1);return;}
    sel=d.id;
    const nb=new Set([d.id]);
    links.forEach(l=>{
      const s=l.source.id||l.source, t=l.target.id||l.target;
      if(s===d.id)nb.add(t); if(t===d.id)nb.add(s);
    });
    node.attr('opacity',n=>nb.has(n.id)?1:.08);
    link.attr('stroke-opacity',l=>{
      const s=l.source.id||l.source,t=l.target.id||l.target;
      return(nb.has(s)&&nb.has(t))?.8:.04;
    });
    nodeLabel.attr('opacity',n=>nb.has(n.id)?1:.05);
  });
  svg.on('click',()=>{if(sel){sel=null;node.attr('opacity',1);link.attr('stroke-opacity',.35);nodeLabel.attr('opacity',1);}});

  sim.on('tick',()=>{
    link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
        .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
    linkLabel.attr('x',d=>(d.source.x+d.target.x)/2).attr('y',d=>(d.source.y+d.target.y)/2);
    node.attr('transform',d=>`translate(${d.x},${d.y})`);
  });
}

// ── Monitor Panel ────────────────────────────────────────────────────────────
function initMonitor(stats) {
  const s=stats.shadow;
  animCount(document.getElementById('sv-cons'), s.consistency_pct, '%', 1400, 2);
  animCount(document.getElementById('sv-tot'), s.total, '', 1200);
  animCount(document.getElementById('sv-fp'), s.fp, '', 800);
  animCount(document.getElementById('sv-fn'), s.fn, '', 1000);
  document.getElementById('lat-avg').textContent = stats.latency_avg_us.toLocaleString();
  document.getElementById('lat-p95').textContent = stats.latency_p95_us.toLocaleString();
  document.getElementById('lat-p99').textContent = stats.latency_p99_us.toLocaleString();
  const d=new Date(s.last_run);
  document.getElementById('upd').textContent='更新于 '+d.toLocaleString('zh-CN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  drawLatency(stats.latency_sample);
  drawRules(stats.rule_counts);
  drawTools(stats.tool_counts);
}

function drawLatency(lats) {
  const el=document.getElementById('lat-chart');
  const W=el.clientWidth||300, H=90, pad={l:30,r:10,t:6,b:22};
  const svg=d3.select(el).attr('viewBox',`0 0 ${W} ${H}`);
  const x=d3.scaleLinear().domain(d3.extent(lats)).range([pad.l,W-pad.r]).nice();
  const bins=d3.bin().domain(x.domain()).thresholds(30)(lats);
  const y=d3.scaleLinear().domain([0,d3.max(bins,b=>b.length)]).range([H-pad.b,pad.t]);
  const color=d3.scaleSequential(d3.interpolateCool).domain(x.domain());
  svg.append('g').selectAll('rect').data(bins).join('rect')
    .attr('x',d=>x(d.x0)+.5).attr('width',d=>Math.max(0,x(d.x1)-x(d.x0)-1))
    .attr('y',d=>y(d.length)).attr('height',d=>y(0)-y(d.length))
    .attr('fill',d=>color((d.x0+d.x1)/2)).attr('opacity',.8);
  const fmt=d3.format('.0s');
  svg.append('g').attr('transform',`translate(0,${H-pad.b})`).call(
    d3.axisBottom(x).ticks(5).tickFormat(fmt)).call(g=>{
      g.select('.domain').attr('stroke',DIM);
      g.selectAll('text').attr('fill',DIM).attr('font-size','7px');
      g.selectAll('.tick line').attr('stroke',DIM);
    });
}

function drawRules(rules) {
  const el=document.getElementById('rules-chart');
  const W=el.clientWidth||300, H=70, pad={l:30,r:10,t:6,b:4};
  const svg=d3.select(el).attr('viewBox',`0 0 ${W} ${H}`);
  const data=Object.entries(rules).sort((a,b)=>b[1]-a[1]);
  const y=d3.scaleBand().domain(data.map(d=>d[0])).range([pad.t,H-pad.b]).padding(.3);
  const x=d3.scaleLinear().domain([0,d3.max(data,d=>d[1])]).range([pad.l+60,W-pad.r]);
  svg.append('g').selectAll('rect').data(data).join('rect')
    .attr('x',pad.l+60).attr('y',d=>y(d[0])).attr('height',y.bandwidth())
    .attr('width',0).attr('fill',CYAN).attr('opacity',.7)
    .transition().duration(800).delay((_,i)=>i*80)
    .attr('width',d=>x(d[1])-x(0));
  svg.append('g').selectAll('text.lbl').data(data).join('text')
    .attr('x',pad.l+56).attr('y',d=>y(d[0])+y.bandwidth()/2+.35*12)
    .attr('text-anchor','end').attr('font-size','9px').attr('fill',DIM).text(d=>d[0]);
  svg.append('g').selectAll('text.val').data(data).join('text')
    .attr('x',d=>x(d[1])+3).attr('y',d=>y(d[0])+y.bandwidth()/2+.35*12)
    .attr('font-size','8px').attr('fill',CYAN).text(d=>d[1]);
}

function drawTools(toolObj) {
  const data=Object.entries(toolObj).sort((a,b)=>b[1]-a[1]).slice(0,9);
  const total=data.reduce((s,d)=>s+d[1],0);
  const schemeSet=[CYAN,'#7b2fff','#2eff8a','#ff8c40','#ff6060','#ffd700','#00cfcf','#ff66cc','#6699ff'];
  const pie=d3.pie().value(d=>d[1]).sort(null);
  const arc=d3.arc().innerRadius(32).outerRadius(56);
  const arcHover=d3.arc().innerRadius(32).outerRadius(62);
  const svg=d3.select('#pie-chart').append('g').attr('transform','translate(65,65)');
  const arcs=svg.selectAll('g').data(pie(data)).join('g');
  arcs.append('path')
    .attr('d',arc).attr('fill',(_,i)=>schemeSet[i%schemeSet.length])
    .attr('stroke','#0a0a1a').attr('stroke-width',1.5).attr('opacity',.85)
    .on('mouseover',function(){d3.select(this).transition().duration(150).attr('d',arcHover);})
    .on('mouseout',function(){d3.select(this).transition().duration(150).attr('d',arc);});
  // Legend
  const leg=document.getElementById('pie-legend');
  leg.innerHTML=data.map(([k,v],i)=>
    `<div style="display:flex;align-items:center;gap:6px">
      <div style="width:8px;height:8px;border-radius:2px;background:${schemeSet[i%schemeSet.length]};flex-shrink:0"></div>
      <span style="color:rgba(107,127,163,.9)">${k}</span>
      <span style="margin-left:auto;color:${CYAN};font-weight:600">${v}</span>
      <span style="color:rgba(107,127,163,.5);font-size:.5rem">${((v/total)*100).toFixed(0)}%</span>
    </div>`).join('');
}
