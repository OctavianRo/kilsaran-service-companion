/* The model key lives on the backend. This client holds only a separate access code in memory. */
let ragURL='',ragCode='',ragHistory=[];
const configReady=fetch('./config.json').then(r=>r.ok?r.json():{}).then(c=>{ragURL=c.ragApiUrl||localStorage.getItem('ragApiUrl')||'';}).catch(()=>{});
function wrapRagEngine(reference){
  const setting=document.createElement('button');setting.type='button';setting.className='copy';setting.textContent='Assistant connection';document.querySelector('.focus-line').append(setting);
  const dialog=document.createElement('dialog');dialog.className='rag-settings';
  dialog.innerHTML='<h2>Connect the AI assistant</h2><p>The AI assistant sends your question and recent conversation to the configured backend and OpenAI. Avoid including customer personal details.</p><label>Backend address<input id="rag-url" type="url" placeholder="https://your-backend.example.com"></label><label>Assistant access code<input id="rag-code" type="password" autocomplete="off"></label><p>This is the assistant access code, never your OpenAI API key. The code stays in memory until you reload.</p><button type="button" id="rag-connect">Connect</button><button type="button" id="rag-close">Cancel</button><p id="rag-error" role="status"></p>';
  document.body.append(dialog);
  const mode=()=>{document.querySelector('#focus-label').textContent=ragURL&&ragCode?'AI answers · managed retrieval':'Reference search · AI not connected';};
  configReady.then(mode);
  setting.onclick=async()=>{await configReady;dialog.querySelector('#rag-url').value=ragURL;dialog.querySelector('#rag-code').value=ragCode;dialog.showModal();};
  dialog.querySelector('#rag-close').onclick=()=>dialog.close();
  dialog.querySelector('#rag-connect').onclick=async()=>{
    const error=dialog.querySelector('#rag-error');
    try{const u=new URL(dialog.querySelector('#rag-url').value);if(u.protocol!=='https:'||u.username||u.password||u.search||u.hash)throw Error('Enter a secure HTTPS backend address.');const code=dialog.querySelector('#rag-code').value;if(!code||code.startsWith('sk-'))throw Error('Enter the assistant access code, not an OpenAI key.');
      const result=await fetch(u.href.replace(/\/$/,'')+'/health',{signal:AbortSignal.timeout(15000)});const health=await result.json();if(!result.ok||!health.ready)throw Error('The backend is not configured yet.');
      ragURL=u.href.replace(/\/$/,'');ragCode=code;localStorage.setItem('ragApiUrl',ragURL);ragHistory=[];dialog.close();mode();
    }catch(e){error.textContent=e.message;}
  };
  document.querySelector('#new').addEventListener('click',()=>{ragHistory=[];mode();});
  return {status:()=>reference.status(),answer:async(q,previous,category)=>{
    await configReady;
    if(!ragURL||!ragCode){const result=reference.answer(q,previous,category);result.message='Reference search only — the AI assistant is not connected yet. '+result.message;return result;}
    const response=await fetch(ragURL+'/chat',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+ragCode},body:JSON.stringify({question:q,history:ragHistory.slice(-6),category}),signal:AbortSignal.timeout(120000)});
    const data=await response.json();if(!response.ok)throw Error(data.error||'The AI assistant could not answer.');
    const message=data.status==='answered'?data.claims.map(c=>c.text+' '+c.source_ids.map(id=>'['+id+']').join(' ')).join('\n\n'):data.answer;
    ragHistory.push({role:'user',content:q.slice(0,2000)},{role:'assistant',content:message.slice(0,2000)});ragHistory=ragHistory.slice(-6);
    return {...data,message:message+(data.follow_up?'\n\n'+data.follow_up:''),query:q,sources:data.sources.map(s=>({...s,title:'['+s.id+'] '+s.title}))};
  }};
}
