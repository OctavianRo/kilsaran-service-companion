const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function client(chatResponse){
 const calls=[];
 const node=()=>({append(){},addEventListener(){},querySelector(){return node();}});
 const context=vm.createContext({document:{createElement:node,querySelector:node,body:node()},localStorage:{getItem(){return null;}},fetch:async(url)=>{calls.push(url);return url==='./config.json'?{ok:true,json:async()=>({})}:chatResponse;},AbortSignal,URL});
 vm.runInContext(fs.readFileSync('docs/rag-client.js','utf8'),context);
 return {context,calls,engine:vm.runInContext('createRagEngine({pages:325,pdfs:34})',context)};
}
test('disconnected assistant returns setup only and performs no corpus search',async()=>{
 const {engine,calls}=client();const result=await engine.answer('silo water hose','','All products');
 assert.equal(result.status,'not_connected');assert.equal(result.sources.length,0);assert.match(result.message,/not connected/);assert.deepEqual(calls,['./config.json']);
});
test('backend failure surfaces an error instead of falling back to extracts',async()=>{
 const {engine,context,calls}=client({ok:false,json:async()=>({error:'Service unavailable'})});
 await vm.runInContext('configReady',context);vm.runInContext("ragURL='https://test.example';ragCode='test-code'",context);
 await assert.rejects(engine.answer('silo','','All products'),/Service unavailable/);assert.deepEqual(calls,['./config.json','https://test.example/chat']);
});
