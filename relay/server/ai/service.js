import {z} from 'zod';
import {classificationPrompt,draftPrompt,askPrompt} from './prompts.js';
import {classifyMock,askMock,draftMock} from './mock.js';
export const classificationSchema=z.object({owner:z.enum(['assistant','client','none','review']),confidence:z.number().min(0).max(100),reason:z.string().min(1).max(600),summary:z.string().min(1).max(1200),dates:z.array(z.object({label:z.string(),date:z.string()})).max(20),isMeeting:z.boolean(),waiting:z.boolean()});
async function llm(system,input){
 const anthropic=process.env.AI_PROVIDER==='anthropic';
 const response=await fetch(anthropic?'https://api.anthropic.com/v1/messages':'https://api.openai.com/v1/chat/completions',{method:'POST',signal:AbortSignal.timeout(25000),headers:anthropic?{'Content-Type':'application/json','x-api-key':process.env.AI_API_KEY,'anthropic-version':'2023-06-01'}:{'Content-Type':'application/json',Authorization:`Bearer ${process.env.AI_API_KEY}`},body:JSON.stringify(anthropic?{model:process.env.AI_MODEL||'claude-sonnet-4-5',max_tokens:1600,system,messages:[{role:'user',content:JSON.stringify(input)}]}:{model:process.env.AI_MODEL||'gpt-4o-mini',messages:[{role:'system',content:system},{role:'user',content:JSON.stringify(input)}]})});
 if(!response.ok)throw new Error('AI provider unavailable');
 const data=await response.json();return anthropic?data.content.filter(c=>c.type==='text').map(c=>c.text).join(''):data.choices[0].message.content;
}
async function structured(prompt,input,schema,fallback){if(!process.env.AI_API_KEY)return fallback();for(let attempt=0;attempt<2;attempt++){try{return schema.parse(JSON.parse((await llm(prompt,input)).replace(/^```(?:json)?\s*|\s*```$/g,'')));}catch{}}return fallback();}
export async function classify(input){
 const result=await structured(classificationPrompt,input,classificationSchema,()=>process.env.AI_API_KEY?{...classifyMock(input),owner:'review',confidence:0,reason:'You should review this because the AI response could not be validated.'}:classifyMock(input));
 if(result.confidence<60)result.owner='review';result.waiting=input.messages.at(-1)?.direction==='outbound';return result;
}
export async function ask(question,threads){const result=await structured(askPrompt,{question,threads},z.object({answer:z.string(),threadIds:z.array(z.string())}),()=>askMock(question,threads));result.threadIds=result.threadIds.filter(id=>threads.some(t=>t.id===id));return result;}
export async function draft(input){if(!process.env.AI_API_KEY)return draftMock(input);try{return (await llm(draftPrompt,input)).slice(0,20000);}catch{return draftMock(input);}}
