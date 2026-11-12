/* Transport fixtures verify browser policy; they are not live Gemini evidence. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

test('provider quota error preserves preference anchor and never automatically retries POST', async () => {
  const calls = [];
  const context = vm.createContext({window:{},TextEncoder,AbortController,setTimeout,clearTimeout,
    fetch:async (path,options) => {
      calls.push({path,options});
      return options.method === 'GET' ? {ok:true,json:async () => ({configured:true})} :
        {ok:false,status:429,json:async () => ({error:{code:'provider_rate_limited',message:'Private provider body'}})};
    }});
  vm.runInContext(readFileSync(new URL('../frontend/assets/api-client.js',import.meta.url),'utf8'),context);
  const anchor={role:'user',text:'Previously stated preferences: budget ₹20,000; prefer Samsung; battery priority.'};
  const body={text:'अ'.repeat(4500),history:[anchor,{role:'user',text:'x'.repeat(1000)},{role:'assistant',text:'y'.repeat(1000)}]};
  await assert.rejects(context.window.ReviewMindAPI.chat(body),error => error.code === 'provider_rate_limited' && /Google reported/.test(error.message) && !/Private provider/.test(error.message));
  assert.equal(calls.length,2);
  const sent=JSON.parse(calls[1].options.body);
  assert.deepEqual(sent.history[0],anchor);
  assert.ok(new TextEncoder().encode(calls[1].options.body).length<=15000);
  assert.equal(body.history.length,3);
});
