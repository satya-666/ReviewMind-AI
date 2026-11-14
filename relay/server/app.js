import express from 'express';
import cookieParser from 'cookie-parser';
import cors from 'cors';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import mongoose from 'mongoose';
import {z,ZodError} from 'zod';
import {User,Client,EmailAccount,Thread,Message,Draft,ActivityLog,owners} from './models.js';
import {syncAccount,reclassify} from './data.js';
import {ask,draft} from './ai/service.js';
import {MockEmailProvider} from './providers/Mock.js';
export function createApp(){
 const app=express();app.set('trust proxy',1);
 const origin=process.env.CLIENT_ORIGIN||'http://localhost:5173';
 const secret=process.env.JWT_SECRET;if(!secret||secret.length<32)throw new Error('JWT_SECRET must contain at least 32 characters');
 app.use(helmet(),cors({origin,credentials:true}),express.json({limit:'64kb'}),cookieParser());
 app.use((req,res,next)=>{if(!['GET','HEAD','OPTIONS'].includes(req.method)&&req.headers.origin&&req.headers.origin!==origin)return res.status(403).json({error:'Origin not allowed'});next();});
 const route=fn=>(req,res,next)=>Promise.resolve(fn(req,res,next)).catch(next);
 const fail=(status,message)=>{throw Object.assign(new Error(message),{status});};
 const cookie={httpOnly:true,secure:process.env.NODE_ENV==='production',sameSite:'lax',maxAge:7*86400000,path:'/'};
 const publicUser=u=>({id:u.id,name:u.name,email:u.email,role:u.role});
 const session=(res,u)=>{res.cookie('relay_session',jwt.sign({id:u.id},secret,{expiresIn:'7d'}),cookie);return publicUser(u);};
 const auth=route(async(req,res,next)=>{try{const payload=jwt.verify(req.cookies.relay_session||'',secret);req.user=await User.findById(payload.id);if(!req.user)fail(401,'Please log in');}catch{fail(401,'Please log in');}next();});
 const assistant=(req,res,next)=>req.user.role==='assistant'?next():res.status(403).json({error:'Assistant access required'});
 async function clientIds(user){return user.role==='client'?[user.clientId]:(await Client.find({assistantId:user._id}).select('_id')).map(c=>c._id);}
 async function scope(user){return {clientId:{$in:await clientIds(user)}};}
 function id(value){if(!mongoose.isValidObjectId(value))fail(400,'Invalid ID');return value;}
 async function threadFor(req){const thread=await Thread.findOne({_id:id(req.params.id||req.params.threadId),...await scope(req.user)});if(!thread)fail(404,'Conversation not found');if(req.user.role==='client'&&(thread.classification.owner!=='client'||thread.done||thread.archived))fail(404,'Conversation not found');return thread;}
 async function log(thread,user,action){await ActivityLog.create({threadId:thread._id,actor:user.role,action});}
 app.get('/api/health',(req,res)=>res.status(mongoose.connection.readyState===1?200:503).json({ok:mongoose.connection.readyState===1,simulated:true}));
 app.use('/api/auth',rateLimit({windowMs:900000,limit:60,standardHeaders:true,legacyHeaders:false}));
 const credentials=z.object({email:z.string().email().max(254).transform(v=>v.toLowerCase()),password:z.string().min(8).max(72)});
 app.post('/api/auth/signup',route(async(req,res)=>{
 const input=credentials.extend({name:z.string().trim().min(1).max(100),role:z.enum(['assistant','client']).default('assistant')}).parse(req.body);
 if(input.role==='client')fail(400,'Client accounts must be provisioned by an assistant; use the seeded client for this prototype.');
 const u=await User.create({...input,passwordHash:await bcrypt.hash(input.password,12)});await Client.create({name:input.name,email:input.email,assistantId:u._id});res.status(201).json(session(res,u));
 }));
 app.post('/api/auth/login',route(async(req,res)=>{const input=credentials.parse(req.body);const u=await User.findOne({email:input.email});if(!u||!await bcrypt.compare(input.password,u.passwordHash))fail(401,'Email or password is incorrect');res.json(session(res,u));}));
 app.post('/api/auth/logout',(req,res)=>{res.clearCookie('relay_session',{...cookie,maxAge:undefined});res.json({ok:true});});
 app.get('/api/auth/me',auth,(req,res)=>res.json(publicUser(req.user)));
 app.use('/api',auth);
 app.get('/api/accounts',assistant,route(async(req,res)=>res.json(await EmailAccount.find(await scope(req.user)))));
 app.post('/api/accounts/connect',assistant,route(async(req,res)=>{const {provider}=z.object({provider:z.enum(['gmail','outlook'])}).parse(req.body);const client=await Client.findOne({assistantId:req.user._id});let account=await EmailAccount.findOne({clientId:client._id,provider});if(account)return res.json(account);if(!account)account=await EmailAccount.create({clientId:client._id,provider,address:client.email,status:'syncing',simulated:true});res.status(201).json(account);syncAccount(account).catch(()=>{});}));
 app.post('/api/accounts/:id/sync',assistant,route(async(req,res)=>{const account=await EmailAccount.findOne({_id:id(req.params.id),...await scope(req.user)});if(!account)fail(404,'Account not found');if(account.status==='syncing')fail(409,'Sync already in progress');account.status='syncing';await account.save();res.json(account);syncAccount(account).catch(()=>{});}));
 app.delete('/api/accounts/:id',assistant,route(async(req,res)=>{const account=await EmailAccount.findOne({_id:id(req.params.id),...await scope(req.user)});if(!account)fail(404,'Account not found');if(account.status==='syncing')fail(409,'Wait for sync to finish before disconnecting');const ids=(await Thread.find({accountId:account._id}).select('_id')).map(t=>t._id);await Promise.all([Message.deleteMany({threadId:{$in:ids}}),Draft.deleteMany({threadId:{$in:ids}}),ActivityLog.deleteMany({threadId:{$in:ids}})]);await Thread.deleteMany({accountId:account._id});await account.deleteOne();res.json({ok:true});}));
 const segmentSchema=z.enum(['all','review','assistant','client','none','waiting','meetings','important','archived']);
 function segmentFilter(segment){const filter={done:{$ne:true},archived:segment==='archived'};if(owners.includes(segment))filter['classification.owner']=segment;if(segment==='waiting')filter.waiting=true;if(segment==='meetings')filter.isMeeting=true;if(segment==='important')filter.important=true;return filter;}
 app.get('/api/threads',assistant,route(async(req,res)=>{const {segment,q,unread}=z.object({segment:segmentSchema.default('all'),q:z.string().max(300).default(''),unread:z.enum(['true','false']).optional()}).parse(req.query);const filter={...await scope(req.user),...segmentFilter(segment)};if(unread)filter.unread=unread==='true';if(q){const escaped=q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');filter.$or=['subject','participants','summary'].map(key=>({[key]:{$regex:escaped,$options:'i'}}));}res.json(await Thread.find(filter).sort({lastMessageAt:-1}));}));
 app.get('/api/stats',assistant,route(async(req,res)=>{const filter=await scope(req.user),result={};for(const segment of ['all','review','assistant','client','none','waiting','meetings','important','archived'])result[segment]=await Thread.countDocuments({...filter,...segmentFilter(segment)});result.unread=await Thread.countDocuments({...filter,...segmentFilter('all'),unread:true});res.json(result);}));
 app.get('/api/threads/:id',route(async(req,res)=>{const t=await threadFor(req);res.json({...t.toObject(),messages:await Message.find({threadId:t._id}).sort({sentAt:1,_id:1}),draft:await Draft.findOne({threadId:t._id,status:'draft'}).sort({_id:-1}),activity:await ActivityLog.find({threadId:t._id}).sort({at:-1}).limit(30)});}));
 app.patch('/api/threads/:id',assistant,route(async(req,res)=>{const input=z.object({important:z.boolean().optional(),unread:z.boolean().optional(),archived:z.boolean().optional(),done:z.boolean().optional(),classification:z.object({owner:z.enum(owners)}).optional()}).strict().parse(req.body);const thread=await threadFor(req);const {classification,...flags}=input;Object.assign(thread,flags);if(classification){thread.classification={owner:classification.owner,confidence:100,reason:'Set manually by you.',source:'manual',updatedAt:new Date()};}await thread.save();await log(thread,req.user,classification?'Owner set to '+classification.owner:'Conversation updated');res.json(thread);}));
 app.use('/api/ai',assistant,rateLimit({windowMs:60000,limit:30,standardHeaders:true,legacyHeaders:false}));
 app.post('/api/ai/classify/:threadId',route(async(req,res)=>res.json(await reclassify(await threadFor(req)))));
 app.post('/api/ai/summarize/:threadId',route(async(req,res)=>{const t=await reclassify(await threadFor(req));res.json({summary:t.summary,dates:t.extractedDates});}));
 app.post('/api/ai/draft/:threadId',route(async(req,res)=>{const t=await threadFor(req);const body=await draft({thread:{subject:t.subject},messages:await Message.find({threadId:t._id}).sort({sentAt:1,_id:1}).lean(),client:await Client.findById(t.clientId).lean()});const saved=await Draft.create({threadId:t._id,body,status:'draft',generatedByAI:true});res.json(saved);}));
 app.post('/api/ai/ask',route(async(req,res)=>{const {question}=z.object({question:z.string().trim().min(1).max(1000)}).parse(req.body);const threads=await Thread.find({...await scope(req.user),done:{$ne:true},archived:{$ne:true}}).sort({lastMessageAt:-1}).limit(200).lean();res.json(await ask(question,threads.map(t=>({id:String(t._id),sender:t.participants[0],subject:t.subject,owner:t.classification.owner,reason:t.classification.reason,waiting:t.waiting,summary:t.summary}))));}));
 app.post('/api/threads/:id/reply',assistant,route(async(req,res)=>{const {body,approved}=z.object({body:z.string().trim().min(1).max(20000),approved:z.literal(true)}).parse(req.body);const thread=await threadFor(req);const client=await Client.findById(thread.clientId);await new MockEmailProvider().sendReply({threadId:thread.id,body,approved});await Draft.updateMany({threadId:thread._id,status:'draft'},{$set:{body,status:'sent'}});await Message.create({threadId:thread._id,from:`${req.user.name} (for ${client.name})`,to:thread.participants[1],body,sentAt:new Date(),direction:'outbound'});thread.lastMessageAt=new Date();thread.waiting=true;await thread.save();await log(thread,req.user,'Approved and sent simulated reply');res.json(await reclassify(thread));}));
 app.get('/api/client/threads',route(async(req,res)=>{res.json(await Thread.find({...await scope(req.user),'classification.owner':'client',done:{$ne:true},archived:{$ne:true}}).sort({lastMessageAt:-1}));}));
 for(const action of ['handled','handoff'])app.post('/api/client/threads/:id/'+action,route(async(req,res)=>{const t=await threadFor(req);if(t.classification.owner!=='client')fail(409,'Thread is no longer assigned to client');if(action==='handled')t.done=true;else t.classification={owner:'assistant',confidence:100,source:'manual',reason:'Client asked the assistant to take over.',updatedAt:new Date()};await t.save();await log(t,req.user,action==='handled'?'Marked handled':'Handed off to assistant');res.json(t);}));
 app.post('/api/dev/incoming',assistant,rateLimit({windowMs:60000,limit:10}),route(async(req,res)=>{
 const input=z.object({threadId:z.string().optional(),body:z.string().trim().min(1).max(20000).optional()}).parse(req.body||{});let thread;
 if(input.threadId){req.params.id=input.threadId;thread=await threadFor(req);}else{const account=await EmailAccount.findOne(await scope(req.user));if(!account)fail(400,'Connect an account first');thread=await Thread.create({clientId:account.clientId,accountId:account._id,subject:'Updated term sheet: your approval needed',participants:['Priya Nair','priya@northwind.co'],archived:false,done:false});}
 await Message.create({threadId:thread._id,from:thread.participants[0],to:req.user.email,body:input.body||'Maya, the allocation changed to 20%. We need your personal approval on these financial terms by 2026-11-20.',sentAt:new Date(),direction:'inbound'});thread.unread=true;thread.done=false;thread.lastMessageAt=new Date();res.status(201).json(await reclassify(thread,true));
 }));
 app.use('/api',(req,res)=>res.status(404).json({error:'Endpoint not found'}));
 app.use((error,req,res,next)=>{const status=error instanceof ZodError?400:error.code===11000?409:error.status||500;res.status(status).json({error:status===500?'Something went wrong. Please retry.':error instanceof ZodError?'Invalid input: '+error.issues.map(i=>i.path.join('.')+' '+i.message).join('; '):error.code===11000?'This email is already registered':error.message});});
 return app;
}
