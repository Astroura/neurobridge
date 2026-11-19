/* Shared SVG figure renderer. Presentation comes from CSS tokens; coordinates come from data. */
window.NeuroBridgePlot={draw(svg,series,options={}){
 const style=getComputedStyle(document.documentElement),size=key=>parseFloat(style.getPropertyValue('--'+key));
 const w=Math.max(280,svg.getBoundingClientRect().width),h=size('chart-height'),left=size('chart-left'),right=size('chart-right'),top=size('chart-top'),bottom=size('chart-bottom');
 svg.setAttribute('viewBox',`0 0 ${w} ${h}`);const lo=options.start||0,hi=Math.max(lo+.001,options.end||1);
 const lines=series.map(s=>({...s,points:s.points.filter(p=>p[0]>=lo&&p[0]<=hi)}));const values=lines.flatMap(s=>s.points.filter(p=>p[1]!==null&&Number.isFinite(p[1])).map(p=>p[1]));
 if(!values.length){svg.innerHTML='<text class="plot-label" x="'+left+'" y="'+(h/2)+'">No samples for this view.</text>';return;}
 let min=Math.min(...values),max=Math.max(...values);if(options.log){min=Math.floor(min);max=Math.ceil(max);}else{const pad=Math.max(5,(max-min)*.08);min-=pad;max+=pad;}if(max===min)max=min+1;
 const x=t=>left+(t-lo)/(hi-lo)*(w-left-right),y=v=>top+(max-v)/(max-min)*(h-top-bottom);let markup='';
 for(let j=0;j<=4;j++){const yy=top+j*(h-top-bottom)/4,xx=left+j*(w-left-right)/4,v=max-j*(max-min)/4;markup+=`<line class="plot-grid" x1="${left}" y1="${yy}" x2="${w-right}" y2="${yy}"/><text class="plot-label" x="${left-8}" y="${yy+4}" text-anchor="end">${options.log?'10^'+v.toFixed(1):v.toFixed(0)}</text><text class="plot-label" x="${xx}" y="${h-8}" text-anchor="middle">${(lo+j*(hi-lo)/4).toFixed(options.log?0:1)}</text>`;}
 markup+=`<text class="plot-label" x="${left}" y="${top-8}">${options.log?'PSD · µV²/Hz (log)':'Amplitude · µV'}</text><text class="plot-label" x="${w-right}" y="${top-8}" text-anchor="end">${options.log?'Hz':'Seconds'}</text>`;
 for(const item of options.intervals||[]){if(item.end<=lo||item.start>=hi)continue;const a=x(Math.max(lo,item.start)),b=x(Math.min(hi,item.end));markup+=`<rect class="plot-rejected" x="${a}" y="${top}" width="${b-a}" height="${h-top-bottom}"/><line class="plot-rejected-rule" x1="${a}" y1="${top}" x2="${b}" y2="${top}"/>`;}
 for(const line of lines){let d='',pen=false;for(const [t,v] of line.points){if(v===null||!Number.isFinite(v)){pen=false;continue;}d+=(pen?'L':'M')+x(t).toFixed(2)+','+y(v).toFixed(2);pen=true;}markup+=`<path class="${line.className||'plot-trace'}" d="${d}"/>`;}
 svg.innerHTML=markup;
}};
