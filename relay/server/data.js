import {Thread,Message,Client,ActivityLog} from './models.js';
import {classify} from './ai/service.js';
import {MockEmailProvider} from './providers/Mock.js';
export async function reclassify(thread,inbound=false){
 if(thread.classification?.source==='manual'&&!inbound)return thread;
 const messages=await Message.find({threadId:thread._id}).sort({sentAt:1,_id:1}).lean();const client=await Client.findById(thread.clientId);
 const result=await classify({thread:{subject:thread.subject},messages,client:{name:client.name}});
 if(inbound&&thread.classification?.source==='manual'){result.owner='review';result.reason='A new inbound message changed the context since your manual assignment. Please review. '+result.reason;}
 thread.classification={owner:result.owner,confidence:result.confidence,reason:result.reason,source:'ai',updatedAt:new Date()};thread.summary=result.summary;thread.extractedDates=result.dates;thread.isMeeting=result.isMeeting;thread.waiting=result.waiting;thread.messageCount=messages.length;
 await thread.save();await ActivityLog.create({threadId:thread._id,actor:'ai',action:'Classified as '+result.owner});return thread;
}
export async function syncAccount(account){
 account.status='syncing';await account.save();
 try{if(!await Thread.exists({accountId:account._id}))for(const sample of await new MockEmailProvider().listThreads()){
 const thread=await Thread.create({accountId:account._id,clientId:account.clientId,subject:sample.s,participants:[sample.f,sample.e],lastMessageAt:new Date(Date.now()-sample.id*3600000),unread:!!sample.u,important:!!sample.im,archived:false,done:false});
 for(const [i,m]of sample.th.entries())await Message.create({threadId:thread._id,from:m[0],to:m[0].startsWith('Alex')?sample.e:account.address,body:m[2],sentAt:new Date(Date.now()-sample.id*3600000-(sample.th.length-i)*60000),direction:m[0].startsWith('Alex')?'outbound':'inbound'});
 await reclassify(thread);
 }else for(const thread of await Thread.find({accountId:account._id}))await reclassify(thread);
 account.status='connected';account.lastSyncedAt=new Date();await account.save();return account;
 }catch(error){account.status='error';await account.save();throw error;}
}
