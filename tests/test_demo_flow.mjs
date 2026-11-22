/* Exercise real UI handlers with a small DOM fixture; no external provider calls. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';
function setup() {
  const elements=new Map(),calls=[];
  const makeElement=() => ({value:'',checked:false,hidden:false,children:[],dataset:{},scrollTop:0,scrollHeight:0,
    classList:{add(){},remove(){}},replaceChildren(){this.children=[];},appendChild(child){this.children.push(child);},
    setAttribute(name,value){this[name]=value;},addEventListener(){},querySelector(){return null;},getBoundingClientRect(){return {top:0};},close(){},focus(){},remove(){}});
  const element=id => {if(!elements.has(id))elements.set(id,makeElement());return elements.get(id);};
  const result={type:'analysis',sentiment:'negative',confidence:.6,aspects:[],warnings:[],request_id:'fixture',model_version:'real-format-fixture'};
  const api={chat:async body => {calls.push(body);return result;}};
  const context=vm.createContext({ReviewMindAuth:{init(){},ready:() => true},ReviewMindAPI:api,Date,Map,Object,String,Array,Number,JSON,URL,crypto:{randomUUID},setTimeout(){},
    window:{addEventListener(){}},document:{querySelector:element,querySelectorAll:() => [],createElement:makeElement,addEventListener(){},documentElement:{dataset:{}}},localStorage:{getItem:() => null,setItem(){}}});
  vm.runInContext(readFileSync(new URL('../frontend/assets/app.js',import.meta.url),'utf8'),context);
  return {element,context,calls,api,result};
}
test('sample fills editable smartphone review and routes classifier without third-party consent',async () => {
  const s=setup();assert.equal(s.element('#mode').value,'review');
  s.element('#sampleReview').onclick();
  assert.equal(s.calls.length,0);assert.equal(s.element('#cat').value,'Smartphones');
  assert.equal(s.element('#q').value,'The camera is excellent in daylight, but the battery drains by noon and charging is painfully slow.');
  s.element('#q').value+=' Edited by visitor.';
  await vm.runInContext('send()',s.context);
  assert.equal(s.calls[0].mode,'review');assert.equal(s.calls[0].allow_gemini,false);
  assert.match(s.calls[0].text,/Edited by visitor/);assert.equal(s.element('#loading').hidden,true);
  assert.equal(s.element('#send').disabled,false);
});
test('timeout preserves request and retry replaces failed reply without duplicating the user message',async () => {
  const s=setup();s.element('#mode').value='auto';s.element('#mode').onchange();
  assert.equal(s.element('#reviewOptions').hidden,true);
  vm.runInContext("processingConsent='accepted'",s.context);
  s.element('#q').value='Wireless earbuds under ₹3,000';
  s.api.chat=async body => {s.calls.push(body);throw new Error('Provider timed out');};
  await vm.runInContext('send()',s.context);
  assert.equal(s.element('#q').value,'Wireless earbuds under ₹3,000');
  assert.equal(s.element('#send').disabled,false);assert.equal(s.element('#results')['aria-busy'],'false');
  s.api.chat=async body => {s.calls.push(body);return s.result;};
  s.element('#analysisForm').onsubmit({preventDefault(){}});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(s.calls.length,2);
  assert.equal(vm.runInContext("current.messages.filter(m => m.role==='user').length",s.context),1);
  assert.equal(vm.runInContext("current.messages.filter(m => m.role==='ai').length",s.context),1);
  assert.equal(s.element('#loading').hidden,true);
});
