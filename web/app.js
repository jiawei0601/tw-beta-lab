const $ = id => document.getElementById(id);
let last = null;
const percent = (x, digits=2) => (x * 100).toFixed(digits) + '%';
const freq = {daily:'日',weekly:'週',monthly:'月'};
const iso = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
function preset(years){const d = new Date($('end').value + 'T12:00:00');d.setFullYear(d.getFullYear()-years);$('start').value=iso(d);document.querySelectorAll('[data-years]').forEach(b=>b.classList.toggle('active',+b.dataset.years===years));}
const taipeiToday = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
$('end').value=taipeiToday;$('end').max=taipeiToday;$('start').max=taipeiToday;preset(3);
document.querySelectorAll('[data-years]').forEach(b=>b.onclick=()=>preset(+b.dataset.years));
document.querySelectorAll('[data-code]').forEach(b=>b.onclick=()=>{const a=$('codes').value.trim().split(/[\s,，、]+/).filter(Boolean);if(!a.includes(b.dataset.code))a.push(b.dataset.code);$('codes').value=a.join(', ');});
for(const id of ['start','end'])$(id).addEventListener('input',()=>document.querySelectorAll('[data-years]').forEach(b=>b.classList.remove('active')));
function status(text,error=false){$('status').textContent=text;$('status').className=error?'error':'';}
function cell(tr,text){const td=document.createElement('td');td.textContent=text;tr.append(td);return td;}
$('query').addEventListener('submit',async e=>{
  e.preventDefault();$('submit').disabled=true;$('export').disabled=true;last=null;$('results').hidden=true;
  status('正在取得歷史行情並對齊報酬，首次查詢約需數秒至一分鐘…');
  try{
    const payload={codes:$('codes').value,start:$('start').value,end:$('end').value,frequency:$('frequency').value,mode:$('mode').value,rf:$('rf').value};
    const r=await fetch('/api/calculate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await r.json();if(!r.ok)throw new Error(data.error||'查詢失敗');
    last=data;render();const good=data.results.filter(r=>!r.error);
    status(`完成 ${good.length} / ${data.results.length} 檔。資料取得時間：${data.benchmark_fetched_at.replace('T',' ')}。今日與未完成週／月不納入。`,!good.length);
  }catch(err){status(err.message,true);}finally{$('submit').disabled=false;$('export').disabled=!last?.results.some(r=>!r.error);}
});
function render(){
  $('results').hidden=false;$('rows').replaceChildren();
  $('context').textContent=`基準 ${last.benchmark} · ${freq[last.frequency]}報酬 · 無風險年利率 ${percent(last.rf_annual)} · ${last.mode==='price'?'價格報酬，不含現金股利再投資':'Yahoo 含息調整價，0050 為代理基準'}。${last.note}`;
  last.results.forEach((r,i)=>{
    const tr=document.createElement('tr');tr.dataset.index=i;
    const title=cell(tr,r.symbol||r.code);const small=document.createElement('small');small.textContent=r.name||'';title.append(small);
    if(r.error){const td=cell(tr,r.error);td.colSpan=6;td.className='warning';}
    else{const b=cell(tr,'');const strong=document.createElement('strong');strong.textContent=r.beta.toFixed(3);b.append(strong);cell(tr,percent(r.r2,1));cell(tr,r.correlation.toFixed(3));cell(tr,percent(r.intercept,3));const sample=cell(tr,`${r.n} 筆`);const dates=document.createElement('small');dates.textContent=`${r.from} → ${r.to}`;sample.append(dates);const td=cell(tr,'');const button=document.createElement('button');button.type='button';button.className='selectchart';button.textContent='查看 ↗';button.onclick=()=>select(i);td.append(button);}
    $('rows').append(tr);
  });
  const first=last.results.findIndex(r=>!r.error);document.querySelector('.chartlayout').hidden=first<0;if(first>=0)select(first);
}
const ns='http://www.w3.org/2000/svg';
function el(name,attrs={},text){const n=document.createElementNS(ns,name);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;$('chart').append(n);return n;}
function select(i){
  const r=last.results[i];document.querySelectorAll('#rows tr').forEach(tr=>tr.classList.toggle('selected',+tr.dataset.index===i));
  $('charttitle').textContent=`${r.symbol} 的${freq[last.frequency]}報酬`;
  $('equation').textContent=`y = ${percent(r.intercept,3)} ${r.beta>=0?'+':'−'} ${Math.abs(r.beta).toFixed(3)}x`;
  $('bigbeta').textContent=r.beta.toFixed(3);
  $('interpretation').textContent=`這段歷史期間，基準超額報酬每增加 1 個百分點，模型估計標的超額報酬平均${r.beta>=0?'增加':'減少'} ${Math.abs(r.beta).toFixed(3)} 個百分點。這是敏感度，並非固定漲跌倍數。`;
  $('warnings').textContent=[...r.warnings, r.rejected?`${r.rejected} 個候選期間因端點或前期資料不符而未納入。`:''].filter(Boolean).join(' ');
  $('chartcaption').textContent=`橫軸：${last.benchmark} 超額報酬；縱軸：標的超額報酬。每點代表一個有效${freq[last.frequency]}期，綠線為 OLS 迴歸；藍綠點為截距。Beta 標準誤 ${r.beta_se.toFixed(4)}（傳統 OLS，未調整異質變異與自相關）。`;
  const svg=$('chart');svg.replaceChildren();
  const xs=r.points.map(p=>p.x),ys=r.points.map(p=>p.y);
  let xmin=Math.min(0,...xs),xmax=Math.max(0,...xs);let dx=Math.max(.005,xmax-xmin);xmin-=dx*.1;xmax+=dx*.1;
  let ymin=Math.min(0,...ys,r.intercept+r.beta*xmin,r.intercept+r.beta*xmax),ymax=Math.max(0,...ys,r.intercept+r.beta*xmin,r.intercept+r.beta*xmax);let dy=Math.max(.005,ymax-ymin);ymin-=dy*.12;ymax+=dy*.12;
  const X=x=>75+(x-xmin)/(xmax-xmin)*685,Y=y=>390-(y-ymin)/(ymax-ymin)*345;
  for(let j=0;j<=5;j++){let x=xmin+(xmax-xmin)*j/5,y=ymin+(ymax-ymin)*j/5;el('line',{x1:X(x),x2:X(x),y1:45,y2:390,class:'grid'});el('text',{x:X(x),y:414,'text-anchor':'middle'},percent(x,1));el('line',{x1:75,x2:760,y1:Y(y),y2:Y(y),class:'grid'});el('text',{x:64,y:Y(y)+4,'text-anchor':'end'},percent(y,1));}
  el('line',{x1:75,x2:760,y1:Y(0),y2:Y(0),class:'axis'});el('line',{x1:X(0),x2:X(0),y1:45,y2:390,class:'axis'});
  r.points.forEach(p=>{const dot=el('circle',{cx:X(p.x),cy:Y(p.y),r:3.4});const t=document.createElementNS(ns,'title');t.textContent=`${p.from} → ${p.date}\n基準 ${percent(p.x,3)}\n標的 ${percent(p.y,3)}`;dot.append(t);});
  el('line',{x1:X(xmin),y1:Y(r.intercept+r.beta*xmin),x2:X(xmax),y2:Y(r.intercept+r.beta*xmax),class:'fit'});
  el('circle',{cx:X(0),cy:Y(r.intercept),r:5,class:'intercept'});
  el('text',{x:76,y:25,class:'label'},'標的超額報酬');el('text',{x:760,y:445,'text-anchor':'end',class:'label'},'基準超額報酬');
}
$('export').onclick=()=>{
  if(!last)return;
  const records=[['symbol','name','benchmark','mode','frequency','annual_rf','beta','intercept_per_period','r2','beta_se','n','sample_start','sample_end','period_start','period_end','stock_return','market_return','stock_excess_return','market_excess_return','fetched_at']];
  for(const r of last.results.filter(r=>!r.error))for(const p of r.points)records.push([r.symbol,r.name,last.benchmark,last.mode,last.frequency,last.rf_annual,r.beta,r.intercept,r.r2,r.beta_se,r.n,r.from,r.to,p.from,p.date,p.stock,p.market,p.y,p.x,r.fetched_at]);
  const safe=v=>{let s=String(v);if(/^[=+@\t\r]/.test(s)||(/^\-/.test(s)&&!Number.isFinite(Number(s))))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
  const csv='\uFEFF'+records.map(a=>a.map(safe).join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`tw-beta-${last.start}-${last.end}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
