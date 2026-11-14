import {samples} from '../sample.js';
export class EmailProvider {async listThreads(){throw new Error('Not implemented');}async getThread(){throw new Error('Not implemented');}async sendReply(){throw new Error('Not implemented');}}
export class MockEmailProvider extends EmailProvider {
 async listThreads(){return Array.from({length:25},(_,i)=>{const sample=samples[i%samples.length];return {...sample,id:i+1,s:i<9?sample.s:`${sample.s} · Follow-up ${Math.floor(i/9)}`,th:sample.th.length>1?sample.th:[['Alex (for Maya)','Earlier',`Following up on ${sample.s.toLowerCase()}.`],...sample.th]};});}
 async getThread(id){return (await this.listThreads()).find(t=>t.id===id);}
 async sendReply(){return {simulated:true};}
}
