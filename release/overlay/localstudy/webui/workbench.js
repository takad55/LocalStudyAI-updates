'use strict';
let wbSelection=new Set(),wbKey='',wbTimer=null,wbLastJob='',wbOutput=null,wbEdits={};
const wbMarkup=`
<section id="workbench" class="view">
 <div class="wb-heading"><div><div class="eyebrow">LOCAL WORKBENCH</div><h1>PCの整理を、ひとつの窓口で。</h1><p>調査から提案までまとめて処理。ファイルの変更は、最後に確認します。</p></div><span class="wb-local">● ローカル処理</span></div>
 <div class="wb-panel wb-scope"><div><small>今回の対象フォルダ</small><strong id="wbRoot">未選択</strong></div><div class="wb-actions"><button id="wbChoose" class="btn secondary">フォルダを選ぶ</button><button id="wbOpen" class="btn ghost">エクスプローラーで開く</button></div></div>
 <div class="wb-panel wb-command"><label for="wbCommand">やりたいこと</label><div class="wb-command-line"><input id="wbCommand" value="このフォルダを整理して" placeholder="例：大学資料を科目ごとに整理して"><button id="wbRun" class="btn primary">調査して提案</button></div><div class="wb-chips"><button data-wb-command="このフォルダを整理して">全体を整理</button><button data-wb-command="大学資料を科目ごとに分類して">大学資料を分類</button><button data-wb-command="不要ファイルの候補を調べて">不要候補</button><button data-wb-command="重複ファイルを整理して">重複を整理</button></div><div class="wb-options"><label><input id="wbAI" type="checkbox" checked> 必要な分類にローカルAIを使う</label><span>調査だけでは削除しません。移動先は選択フォルダの中です。</span></div></div>
 <div class="wb-summary"><div id="wbSummary"><b>対象を選んで調査を開始</b><span>結果と理由をまとめて確認できます。</span></div><button id="wbPractice" class="btn ghost">練習データ</button><button id="wbRestore" class="btn ghost">前回の調査</button></div>
 <div class="wb-panel"><div class="wb-section-head"><h2>整理候補</h2><div class="wb-actions"><button id="wbSelect" class="btn ghost small">推奨候補を選択</button><button id="wbNone" class="btn ghost small">選択を解除</button></div></div><div class="wb-filter"><input id="wbFilter" placeholder="名前・分類・理由で絞り込み"><span id="wbCount">0件選択</span></div><div id="wbCandidates" class="wb-candidates"><div class="empty-cell">まだ調査していません。</div></div><details class="wb-details"><summary id="wbSkipLabel">対象外・調査の制限</summary><pre id="wbSkipped">—</pre></details></div>
 <div class="wb-bottom"><div><b>候補から整理案を作る</b><small>次の画面で移動先・削除対象を確認し、承認して実行します。</small></div><button id="wbPlan" class="btn primary">整理案を確認する →</button></div>
 <div class="wb-panel wb-consult"><h2>難しい判断はChatGPTに相談</h2><p>選択した候補の情報をまとめてコピーできます。自動送信・有料APIは使いません。</p><label><input id="wbInclude" type="checkbox"> 本文の一部も含める（送信前に個人情報を確認）</label><div class="wb-actions"><button id="wbConsult" class="btn secondary">相談文を作る</button><button id="wbAdvice" class="btn ghost">回答のJSONを取り込む</button></div><small>回答は未選択の提案になります。回答内容からコマンドを実行することはありません。</small></div>
</section>
<section id="library" class="view">
 <div class="wb-heading"><div><div class="eyebrow">EVIDENCE FIRST</div><h1>大学資料を、探して理解する。</h1><p>PDFのページ・スライド・シートの位置と一緒に、根拠を確認できます。</p></div></div>
 <div class="wb-panel wb-scope"><div><small>索引の対象フォルダ</small><strong id="wbLibraryRoot">未選択</strong></div><div class="wb-actions"><button id="wbLibraryChoose" class="btn secondary">フォルダを選ぶ</button><button id="wbIndex" class="btn primary">索引を作成・更新</button></div></div>
 <div class="wb-panel wb-search"><label for="wbQuery">検索語・資料への質問</label><input id="wbQuery" placeholder="例：ベルヌーイの式の適用条件は？"><div class="wb-actions"><button id="wbSearch" class="btn secondary">原文を検索</button><button id="wbAnswer" class="btn primary">出典付きで回答</button><label><input id="wbAcross" type="checkbox"> 登録済みの全フォルダから検索</label></div><p class="smalltext">図・画像の意味や複雑な数式は未対応です。AIの説明は原資料と照合してください。</p></div>
 <div class="wb-panel"><div class="wb-section-head"><h2>登録済み資料</h2><button id="wbDocRefresh" class="btn ghost small">一覧を更新</button></div><div id="wbDocuments" class="wb-documents"><div class="empty-cell">索引を作成すると表示されます。</div></div><div class="wb-actions"><button id="wbSummaryRun" class="btn secondary">選択した資料を一括要約</button><button id="wbForget" class="btn ghost">このフォルダの索引を削除</button></div><p class="smalltext">1回に12資料まで。抽出・要約の上限と読んだ範囲を結果に明記します。原本は変更しません。</p></div>
 <div class="wb-panel"><div class="wb-section-head"><h2>検索・回答・要約の結果</h2><div class="wb-actions"><button id="wbCopy" class="btn ghost small">コピー</button><button id="wbSave" class="btn ghost small">保存</button></div></div><div id="wbWarnings"></div><pre id="wbOutput">まだ検索していません。</pre><div id="wbSources"></div></div>
</section>`;
function wbReport(){return app?.workbench?.report||null;}
function renderWorkbench(){
 if(!app||!$('wbRoot'))return;
 $('wbRoot').textContent=app.root||'未選択';$('wbLibraryRoot').textContent=app.root||'未選択';
 const r=wbReport();const key=r?r.id+'|'+r.candidates.map(c=>c.action+c.reason+c.destination+c.selected).join(''):'';
 if(key!==wbKey){wbKey=key;wbEdits={};wbSelection=new Set((r?.candidates||[]).filter(c=>c.selected).map(c=>c.id));wbDraw();}
 if(r){const moves=r.candidates.filter(c=>c.action==='move').length,trash=r.candidates.filter(c=>c.action==='trash').length;
 $('wbSummary').innerHTML=`<b>${esc(r.scanned)}ファイル調査 · ${moves}件の移動候補 · ${trash}件のごみ箱候補</b><span>${r.complete?'調査終了':'中断・上限による部分結果'} / まだファイルは変更していません。</span>`;
 $('wbSkipped').textContent=r.skipped.join('\n')||'なし';$('wbSkipLabel').textContent=`対象外・調査の制限 (${r.skipped.length}件)`;
 }else{$('wbSummary').innerHTML='<b>対象を選んで調査を開始</b><span>結果と判断理由をまとめて確認できます。</span>';$('wbSkipped').textContent='—';}
}
window.renderWorkbench=renderWorkbench;
function wbDraw(){
 const r=wbReport();if(!r){$('wbCandidates').innerHTML='<div class="empty-cell">まだ調査していません。</div>';$('wbCount').textContent='0件選択';return;}
 const q=$('wbFilter').value.toLocaleLowerCase();
 const rows=r.candidates.filter(c=>[c.relative,c.category,c.reason].join(' ').toLocaleLowerCase().includes(q));
 $('wbCandidates').innerHTML=rows.map(c=>`<article class="wb-candidate"><input class="wb-check" type="checkbox" data-id="${esc(c.id)}" ${wbSelection.has(c.id)?'checked':''} aria-label="${esc(c.relative)}を選択"><div class="wb-body"><div class="wb-title"><b>${esc(c.relative)}</b><span class="category-badge">${esc(c.category)}</span></div><p>${esc(c.reason)}</p><small>${esc(c.method)} · ${esc(bytes(c.size))} · 更新 ${esc(c.modified)}</small>${c.action==='move'?`<label class="wb-dest-label">移動先<input class="wb-dest" data-id="${esc(c.id)}" value="${esc(wbEdits[c.id]??c.destination)}"></label>`:`<div class="wb-action-note">${c.action==='trash'?'ごみ箱への移動候補（完全削除はしません）':'判断保留：相談または手動の整理へ'}</div>`}</div></article>`).join('')||'<div class="empty-cell">この条件の候補はありません。</div>';
 $('wbCount').textContent=wbSelection.size+'件選択';
}
async function wbChoose(){
 if(app.actions.length&&!confirm('未実行の整理案を破棄してフォルダを変更しますか？'))return;
 const r=await req('choose',{kind:'folder'});if(r?.path)await req('root',{path:r.path});
}
async function wbRaw(action,fields={}){
 const res=await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json','X-LocalStudy-Token':app.token},body:JSON.stringify({action,...fields})});
 const data=await res.json();if(!data.ok)throw new Error(data.error||'処理に失敗しました。');app=data.state;render();return data.result;
}
async function wbStart(fields){const r=await req('wb_start',fields,'処理を開始しています…');if(r?.job){wbLastJob='';wbHandleJob(r.job);wbPoll();}}
function wbPoll(){clearTimeout(wbTimer);wbTimer=setTimeout(async()=>{try{const r=await wbRaw('wb_job');wbHandleJob(r.job);if(r.job?.status==='running')wbPoll();}catch(e){toast(e.message,true);}},1500);}
function wbHandleJob(j){
 if(!j){$('wbJob').classList.add('hide');return;}
 $('wbJob').classList.remove('hide');$('wbJobTitle').textContent=j.title;$('wbJobText').textContent=(j.error||j.message)+` · ${Math.round(j.elapsed)}秒`;
 $('wbProgress').max=j.total||1;if(j.total)$('wbProgress').value=j.current;else $('wbProgress').removeAttribute('value');
 $('wbCancel').disabled=j.status!=='running'||j.cancel_requested;$('wbCancel').textContent=j.cancel_requested?'中断要求済み':'中断';
 if(j.status==='running')return;
 clearTimeout(wbTimer);if(wbLastJob===j.id)return;wbLastJob=j.id;
 if(j.status==='failed'){toast(j.error,true);return;}
 if(j.status==='cancelled')toast('中断しました。元ファイルは変更していません。');
 const r=j.result;if(!r)return;
 if(r.kind==='analysis'){wbKey='';renderWorkbench();toast('整理候補を作成しました。内容を確認して整理案へ進んでください。');}
 else if(r.kind==='index'){wbLoadDocs();$('wbOutput').textContent=`索引を更新しました。新規・更新 ${r.updated}件 / 再利用 ${r.reused}件 / 古い索引除去 ${r.removed}件\n${r.complete?'調査終了':'部分結果'}\n${(r.skipped||[]).join('\n')}`;$('wbWarnings').textContent='';$('wbSources').textContent='';wbOutput=null;toast('索引の処理が終わりました。');}
 else{wbOutput=r;wbShowOutput(r);navigate('library');}
}
function wbOutputText(r){return [r.answer||r.message||'検索結果',...(r.warnings||[]).map(w=>'注意: '+w),...(r.coverage||[]).map(c=>`${c.relative}: ${c.characters_used}/${c.indexed_characters}字を要約`),...(r.sources||[]).map(s=>`[${s.citation}] ${s.relative} / ${s.location}\n${s.text}`)].join('\n\n');}
function wbShowOutput(r){
 $('wbOutput').textContent=r.answer||r.message||'検索結果';
 $('wbWarnings').innerHTML=(r.warnings||[]).map(w=>`<div class="wb-warning">${esc(w)}</div>`).join('')+(r.coverage||[]).map(c=>`<div class="smalltext">${esc(c.relative)}: ${c.characters_used}/${c.indexed_characters}字 ${c.complete?'':'（未要約部分あり）'} ${(c.warnings||[]).map(esc).join(' / ')}</div>`).join('');
 $('wbSources').innerHTML=(r.sources||[]).map(s=>`<details class="wb-source"><summary><b>[${esc(s.citation)}] ${esc(s.relative)}</b> <span>${esc(s.location)}</span></summary><pre>${esc(s.text)}</pre><button class="btn ghost small wb-open-source" data-id="${Number(s.id)}">原本のフォルダを開く</button><small>${esc((s.warnings||[]).join(' / '))}</small></details>`).join('');
}
async function wbLoadDocs(){const r=await req('wb_documents',{},'資料一覧を読み込み中…');if(r)$('wbDocuments').innerHTML=r.documents.map(d=>`<label><input type="checkbox" class="wb-doc" value="${esc(d.relative)}"><span>${esc(d.relative)}<small>${esc(d.updated)} ${(d.warnings||[]).length?'· 抽出制限あり':''}</small></span></label>`).join('')||'<div class="empty-cell">索引がありません。「索引を作成・更新」を押してください。</div>';}
function setupWorkbench(){
 views.workbench='まとめて整理';views.library='資料検索・要約';
 document.querySelector('.content').insertAdjacentHTML('afterbegin',wbMarkup);
 const nav=document.querySelector('.nav');
 for(const [id,icon,label] of [['library','search','資料検索・要約'],['workbench','spark','まとめて整理']]){const b=document.createElement('button');b.className='nav-link';b.dataset.view=id;b.innerHTML=ico(icon)+' '+label;b.onclick=()=>navigate(id);nav.prepend(b);}
 const progress=document.createElement('div');progress.id='wbJob';progress.className='wb-job hide';progress.setAttribute('role','status');progress.innerHTML='<div><b id="wbJobTitle"></b><span id="wbJobText"></span><progress id="wbProgress" max="1"></progress></div><button id="wbCancel" class="btn secondary small">中断</button>';document.querySelector('.content').prepend(progress);
 $('wbChoose').onclick=$('wbLibraryChoose').onclick=wbChoose;$('wbOpen').onclick=()=>req('open',{item:'root'});
 $('wbPractice').onclick=async()=>{if(app.actions.length&&!confirm('未実行の案を破棄して練習データへ切り替えますか？'))return;await req('wb_practice');};
 $('wbRestore').onclick=async()=>{if(app.actions.length&&!confirm('未実行の案を破棄して前回の調査を読み込みますか？'))return;await req('wb_restore');};
 document.querySelectorAll('[data-wb-command]').forEach(b=>b.onclick=()=>{$('wbCommand').value=b.dataset.wbCommand;});
 $('wbRun').onclick=()=>wbStart({task:'command',command:$('wbCommand').value,use_ai:$('wbAI').checked});
 $('wbCommand').onkeydown=e=>{if(e.key==='Enter'&&!e.isComposing)$('wbRun').click();};
 $('wbCancel').onclick=async()=>{try{const r=await wbRaw('wb_cancel');wbHandleJob(r.job);toast(r.message);}catch(e){toast(e.message,true);}};
 $('wbFilter').oninput=wbDraw;
 $('wbCandidates').oninput=e=>{if(e.target.matches('.wb-dest'))wbEdits[e.target.dataset.id]=e.target.value;};
 $('wbCandidates').onchange=e=>{if(e.target.matches('.wb-check')){if(e.target.checked)wbSelection.add(e.target.dataset.id);else wbSelection.delete(e.target.dataset.id);$('wbCount').textContent=wbSelection.size+'件選択';}};
 $('wbSelect').onclick=()=>{wbSelection=new Set((wbReport()?.candidates||[]).filter(c=>c.selected).map(c=>c.id));wbDraw();};$('wbNone').onclick=()=>{wbSelection.clear();wbDraw();};
 $('wbPlan').onclick=async()=>{
 const report=wbReport();if(!report)return toast('先に調査してください。',true);
 const chosen=[...wbSelection].filter(id=>report.candidates.find(c=>c.id===id)?.action!=='keep');if(!chosen.length)return toast('実行可能な候補を選んでください。保留候補は相談できます。',true);
 if(app.actions.length&&!confirm('現在の未実行の整理案を置き換えますか？'))return;
 const destinations={};for(const id of chosen)if(id in wbEdits)destinations[id]=wbEdits[id];
 const r=await req('wb_plan',{report_id:report.id,selected:chosen,destinations,replace:!!app.actions.length},'元の内容と移動先を検証中…');if(r){navigate('files');$('planList').scrollIntoView({behavior:'smooth',block:'center'});toast(r.message);}
 };
 $('wbConsult').onclick=async()=>{const r=await req('wb_consult',{report_id:wbReport()?.id,selected:[...wbSelection],include_text:$('wbInclude').checked});if(r)showText('ChatGPTへの相談文（送信前に個人情報を確認）',r.content,{editable:true,localAdvice:true});};
 $('wbAdvice').onclick=async()=>{const r=await makeModal({title:'ChatGPTの回答からJSONだけを貼り付け',description:'取り込むのは提案だけです。実行前に対象を選んで確認します。',large:true,inputs:[{id:'answer',kind:'textarea',label:'回答のJSON',placeholder:'{"report_id": ...}'}],confirmText:'案として取り込む'});if(r?.answer){wbKey='';const x=await req('wb_advice',{text:r.answer});if(x)toast(x.message);}};
 $('wbIndex').onclick=()=>wbStart({task:'index'});$('wbSearch').onclick=()=>wbStart({task:'search',query:$('wbQuery').value,across_all:$('wbAcross').checked});$('wbAnswer').onclick=()=>wbStart({task:'answer',query:$('wbQuery').value,across_all:$('wbAcross').checked});
 $('wbDocRefresh').onclick=wbLoadDocs;$('wbSummaryRun').onclick=()=>wbStart({task:'summary',selected:[...document.querySelectorAll('.wb-doc:checked')].map(e=>e.value)});
 $('wbForget').onclick=async()=>{if(confirm('選択フォルダの索引だけを削除しますか？元資料は残ります。')){const r=await req('wb_forget',{approval:'索引を削除'});if(r)wbLoadDocs();}};
 $('wbCopy').onclick=async()=>{if(wbOutput){try{await navigator.clipboard.writeText(wbOutputText(wbOutput));toast('出典付きでコピーしました。');}catch{showText('結果をコピー',wbOutputText(wbOutput));}}};
 $('wbSave').onclick=async()=>{if(wbOutput){const r=await req('save_text',{content:wbOutputText(wbOutput)});if(r)toast(r.message);}};
 $('wbSources').onclick=async e=>{const b=e.target.closest('.wb-open-source');if(b)await req('wb_source',{id:Number(b.dataset.id),open_folder:true});};
 const h=document.createElement('div');h.className='wb-panel';h.innerHTML='<h2>v1.0 動作診断</h2><p>履歴・索引・Ollama接続を確認します。実ファイルは変更しません。</p><button id="wbHealth" class="btn secondary">診断を実行</button><pre id="wbHealthResult">未実行</pre>';$('settings').append(h);
 $('wbHealth').onclick=async()=>{const r=await req('wb_health');if(r)$('wbHealthResult').textContent=r.checks.map(c=>`${c.ok?'✓':'要確認'} ${c.name}: ${c.detail}`).join('\n');};
 navigate('workbench');let attempts=0;const ready=setInterval(async()=>{if(app){clearInterval(ready);renderWorkbench();try{const r=await wbRaw('wb_job');if(r.job){wbHandleJob(r.job);if(r.job.status==='running')wbPoll();}}catch{}}else if(++attempts>60)clearInterval(ready);},200);
}
window.addEventListener('DOMContentLoaded',setupWorkbench);
