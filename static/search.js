/* Shared browser/Node search engine. Queries never leave the browser. */
(function (root) {
  const stop = new Set('a an the and or to of for in on with is are was be do does can could would should i me my you your customer wants want know about please tell what which how much many any it that this they need have has get use using thanks thank'.split(' '));
  const aliases = {mortart:'mortar',hoses:'hose',bags:'bag',silos:'silo',electricity:'power electrical',electric:'electrical',power:'power electrical',supply:'supply requirements',require:'requirements',setup:'site requirements',blocked:'blockage',blockages:'blockage',cleaning:'clean maintenance',tonnes:'tonne',weight:'weight kg',cost:'price',prices:'price',stock:'availability',refill:'delivery',mixing:'mix mixer',pallets:'pallet',size:'size diameter',hosepipe:'hose'};
  function words(text) {
    return (text.normalize('NFKC').toLowerCase().match(/[a-z0-9]+/g)||[]).filter(w=>!stop.has(w)).flatMap(w=>(aliases[w]||w).split(' ')).map(w=>w.length>4&&w.endsWith('s')?w.slice(0,-1):w);
  }
  const terms = text => [...new Set(words(text))].slice(0,32);
  class Search {
    constructor(data) {
      this.data=data;this.chunks=[];this.df=new Map();
      for (const doc of data.documents) for(const section of doc.sections) {
        const blocks=[];let part='';
        for(const line of section.text.split('\n').map(s=>s.trim()).filter(Boolean)) {
          if(part.length>1200&&doc.kind!=='pdf'){blocks.push(part);part='';}
          part+='\n'+line;
        }
        if(part.trim())blocks.push(part.trim());
        for(const text of blocks){
          const bodyWords=words(text), freq=new Map();
          for(const w of bodyWords)freq.set(w,(freq.get(w)||0)+1);
          for(const w of words(doc.title))freq.set(w,(freq.get(w)||0)+3);
          for(const w of freq.keys())this.df.set(w,(this.df.get(w)||0)+1);
          this.chunks.push({title:doc.title,text,url:doc.url+(section.page?'#page='+section.page:''),page:section.page,kind:doc.kind,table:/FAULT\/ISSUE\s+CAUSE\s+SOLUTION/.test(text),freq,length:bodyWords.length});
        }
      }
      this.avg=this.chunks.reduce((n,c)=>n+c.length,0)/Math.max(1,this.chunks.length);
    }
    status(){return {updated:this.data.updated,pages:this.data.documents.filter(d=>d.kind==='page').length,pdfs:this.data.documents.filter(d=>d.kind==='pdf').length,failures:this.data.errors.length,errors:this.data.errors};}
    answer(question,previous='',category='All products'){
      const original=terms(question);
      if(!original.length)return {message:'Ask about a Kilsaran product or a specific customer question.',sources:[],query:question};
      let query=question;
      if(previous&&(original.length<5||/\b(it|that|those|they|its)\b/i.test(question)))query=previous+' '+question;
      if(category!=='All products')query+=' '+category;
      const ts=terms(query),has=(...options)=>options.some(w=>ts.includes(w));
      const ranked=[];
      for(const chunk of this.chunks){
        const direct=original.filter(t=>chunk.freq.has(t)).length;
        if(!direct)continue;
        let score=0;
        for(const t of ts){
          const f=chunk.freq.get(t)||0;
          if(f)score+=Math.log(1+(this.chunks.length-(this.df.get(t)||0)+.5)/((this.df.get(t)||0)+.5))*f*2.2/(f+1.2*(.25+.75*chunk.length/this.avg));
        }
        score*=.3+ts.filter(t=>chunk.freq.has(t)).length/ts.length;
        score+=direct*2;
        if(has('silo')&&/silo/i.test(chunk.title))score+=7;
        if(has('hose')&&/hose/i.test(chunk.text))score+=3;
        if(has('silo')&&chunk.kind==='pdf'&&/silo user guide/i.test(chunk.title)){
          score+=5;
          if(has('water','electrical','power','hose','requirement')&&chunk.text.includes('Electrical Requirements')&&chunk.text.includes('Water Requirements'))score+=20;
          if(has('clean','maintenance')&&chunk.text.includes('Daily Cleaning'))score+=18;
        }
        if(has('bag')&&has('mortar')&&/masonry/i.test(chunk.title))score+=5;
        ranked.push({chunk,score,direct});
      }
      ranked.sort((a,b)=>b.score-a.score);
      const seen=new Set(),sources=[];
      for(const {chunk} of ranked){if(seen.has(chunk.url))continue;seen.add(chunk.url);const {freq,length,...source}=chunk;sources.push(source);if(sources.length===4)break;}
      let message='Here are the closest passages from Kilsaran’s published information. Check the linked document for the full instructions and product suitability.';
      if(!sources.length)message='I couldn’t find supporting information in the indexed Kilsaran sources. Please confirm with Kilsaran; I don’t have a verified answer.';
      else if(original.some(t=>['price','availability','discount','quote'].includes(t)))message='Current prices, stock and delivery commitments need confirmation from Kilsaran. These published references may help identify the product.';
      else if(ranked[0].direct<Math.max(1,original.length*.55))message='I found related information, but not a verified answer to every part of this question. Please confirm missing details with Kilsaran.';
      const caution=/hose|silo|electri|blockage|blocked|pressure|repair/i.test(query)?'For equipment work, follow the complete current silo guide and its isolation and safety instructions. Confirm unlisted hose sizes, fittings or replacement parts with Kilsaran support.':null;
      return {message,sources,caution,query};
    }
  }
  root.KilsaranSearch=Search;
  if(typeof module!=='undefined')module.exports={Search,terms};
})(typeof globalThis!=='undefined'?globalThis:this);
