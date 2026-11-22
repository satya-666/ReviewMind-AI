/* Browser auth lifecycle fixtures; real Google login still needs the owner's client ID. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

function setup(config={required:true,client_id:'fixture.apps.googleusercontent.com'}) {
  const elements=new Map(),events=[],timers=[];
  const element=id => {
    if (!elements.has(id)) elements.set(id,{hidden:false,textContent:'',replaceChildren(){}});
    return elements.get(id);
  };
  let callback;
  const google={accounts:{id:{initialize:options => callback=options.callback,renderButton(){},disableAutoSelect(){}}}};
  const api={authConfig:async () => config,me:async () => ({user:{id:'google-id',email:'person@gmail.com',expires_at:Math.floor(Date.now()/1000)+600}})};
  const window={google,dispatchEvent:event => events.push(event)};
  const context=vm.createContext({window,google,ReviewMindAPI:api,Date,Number,Math,Error,
    CustomEvent:class {constructor(type,options){this.type=type;this.detail=options.detail;}},
    document:{getElementById:element,querySelector:element},clearTimeout(){},
    setTimeout:(fn,ms) => {timers.push({fn,ms});return 1;}});
  vm.runInContext(readFileSync(new URL('../frontend/assets/auth.js',import.meta.url),'utf8'),context);
  return {auth:window.ReviewMindAuth,element,events,timers,api,credential:response => callback(response)};
}

test('verified login, expiry and sign-out protect the chat and clear bearer credentials',async () => {
  const s=setup();await s.auth.init();
  assert.equal(s.auth.ready(),true);
  assert.equal(s.element('chatApp').hidden,false);
  assert.equal(s.element('authPanel').hidden,false);
  await s.credential({credential:'fixture-token'});
  assert.equal(s.auth.headers().Authorization,'Bearer fixture-token');
  assert.equal(s.auth.ready(),true);
  assert.equal(s.element('accountEmail').textContent,'person@gmail.com');
  assert.equal(s.events.at(-1).detail.id,'google-id');
  s.timers[0].fn();
  assert.equal(s.auth.ready(),true);
  assert.equal(s.auth.headers().Authorization,undefined);
  assert.equal(s.element('chatApp').hidden,false);
  await s.credential({credential:'another-fixture-token'});
  s.element('signOut').onclick();
  assert.equal(s.auth.ready(),true);
  assert.equal(s.events.at(-1).detail,null);
});

test('missing configuration and failed verification keep guest demo available without credentials',async () => {
  const missing=setup({required:true,client_id:''});await missing.auth.init();
  assert.equal(missing.auth.ready(),true);
  assert.equal(missing.element('retryAuth').hidden,false);
  const failed=setup();await failed.auth.init();
  failed.api.me=async () => {throw new Error('Sign-in rejected');};
  await failed.credential({credential:'forged'});
  assert.equal(failed.auth.ready(),true);
  assert.equal(failed.auth.headers().Authorization,undefined);
  assert.equal(failed.element('authStatus').textContent,'Sign-in rejected');
});

test('account changes load only server-owned chats and clear unsent messages',async () => {
  const elements=new Map(),listeners=new Map();
  const makeElement=() => ({value:'',checked:false,hidden:false,children:[],dataset:{},
    replaceChildren(){this.children=[];},appendChild(child){this.children.push(child);},
    setAttribute(){},addEventListener(){},querySelector(){return null;},close(){},focus(){}});
  const element=id => {if(!elements.has(id)) elements.set(id,makeElement());return elements.get(id);};
  let owner='alice';
  const auth={init(){},required:() => true,ready:() => true};
  const context=vm.createContext({ReviewMindAuth:auth,ReviewMindAPI:{chats:async () => ({chats:[{id:owner,title:owner+' private chat'}]})},Date,Map,Object,String,Array,Number,JSON,
    window:{addEventListener:(name,fn) => listeners.set(name,fn)},
    document:{querySelector:element,querySelectorAll:() => [],createElement:makeElement,addEventListener(){}},
    localStorage:{getItem:() => null}});
  vm.runInContext(readFileSync(new URL('../frontend/assets/app.js',import.meta.url),'utf8'),context);
  const change=detail => listeners.get('reviewmind-auth')({detail});
  await change({id:'alice'});
  assert.equal(vm.runInContext('chats[0].title',context),'alice private chat');
  element('#q').value='Private unsent message';
  await change(null);
  assert.equal(vm.runInContext('chats.length',context),0);
  assert.equal(element('#q').value,'');
  owner='bob';await change({id:'bob'});
  assert.equal(vm.runInContext('chats[0].title',context),'bob private chat');
  assert.equal(vm.runInContext('current',context),null);
});
