/* Chat routing is server-side; only actual classifier results get prediction feedback. */
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const LABELS = ['positive','negative','neutral','mixed','unknown'];
const label = value => value === 'unknown' ? 'Not determined' : value.charAt(0).toUpperCase() + value.slice(1);
const CONSENT_KEY = 'reviewmind_processing_consent_v1';
let processingConsent = 'unknown', pendingConsent = null;
function setProcessingConsent(value) {
  processingConsent = ['accepted','declined'].includes(value) ? value : 'unknown';
  $('#processingConsent').value = processingConsent;
  try { localStorage.setItem(CONSENT_KEY,processingConsent); } catch { toast('Your processing choice stays in this tab because device storage is unavailable.'); }
}
let signedUser=null,accountEpoch=0,historyLoading=false;
const GUEST_HISTORY_KEY='reviewmind_guest_history_v1';
let rememberGuest=false;
const I18N = {
  en:{hello:'Understand a product review',sub:'Explore overall sentiment and product aspects with our trained classifier.',placeholder:''},
  hi:{hello:'AI के साथ प्रोडक्ट रिव्यू समझें',sub:'रिव्यू का समग्र भाव और प्रोडक्ट फीचर देखें। हिन्दी की सटीकता अभी प्रमाणित नहीं है।',placeholder:'विश्लेषण के लिए प्रोडक्ट रिव्यू यहाँ लिखें…'},
  hinglish:{hello:'AI se product reviews samjhein',sub:'Review paste karein aur overall sentiment aur product features dekhein. Hinglish accuracy abhi verified nahi hai.',placeholder:'Product review yahan paste karein…'}
};
let chats = [], current = null, busy = false, feedbackTarget = null;
const feedbackStates = new Map();
function renderAnalysis(data) {
  const mentions = data.aspects.length ? `<ul class="aspect-list">${data.aspects.map(a => `<li><span>${esc(a.name)}${a.evidence ? `<small class="aspect-evidence">Evidence: “${esc(a.evidence)}”</small>` : ''}</span><span class="${esc(a.sentiment)}">${esc(label(a.sentiment))}</span></li>`).join('')}</ul>` : '<p class="note">No matching product features were found. Check the selected category. Some features may not be covered by our rules.</p>';
  const score = data.confidence === null ? 'This model does not provide an analysis score.' : `Analysis score: <strong>${Number(data.confidence).toFixed(3)}</strong>`;
  return `<div class="ai-full"><article class="card"><div class="result-top"><h3>Overall sentiment</h3><span class="sentiment ${esc(data.sentiment)}">${esc(label(data.sentiment))}</span></div>
    <p class="analysis-score">${score}</p><p class="note">A model score, not a reliability percentage or product rating.</p>
    <h3>Product aspects</h3>${mentions}<p class="note">Feature mentions and their sentiment use keyword rules, separate from the overall AI prediction.</p>
    <details class="analysis-about"><summary>About this analysis</summary><p>Model: ${esc(data.model_version)}</p><p>The overall model learned from star ratings rather than independently annotated sentiment. Scores are uncalibrated. Aspect rules can miss context and are not a trained aspect sentiment model.</p><ul>${data.warnings.map(w => `<li>${esc(w)}</li>`).join('')}</ul></details>
    <div class="analysis-actions"><button class="btn prediction-feedback" data-request="${esc(data.request_id)}">Give feedback on this analysis</button></div></article></div>`;
}
function productCards(products = []) {
  return products.slice(0,4).filter(p => p && typeof p.title === 'string' && safeSource(p.source_url)).map(p => `<article class="card product-card"><h3>${esc(p.title)}</h3><p>${Number.isFinite(p.price_inr) ? '₹'+Number(p.price_inr).toLocaleString('en-IN') : 'Price unavailable'}</p><ul>${(Array.isArray(p.specifications) ? p.specifications : []).filter(s => typeof s === 'string').slice(0,8).map(s => `<li>${esc(s)}</li>`).join('')}</ul>${!p.specifications?.length ? '<p class="note">Specifications unknown.</p>' : ''}<p class="note">${p.rating != null ? `Listing rating: ${esc(p.rating)}/5${p.review_count != null ? ' · '+esc(p.review_count)+' reviews' : ''}. ` : ''}Availability unconfirmed. Check the source before buying.</p><a href="${esc(p.source_url)}" target="_blank" rel="noopener noreferrer">${esc(p.source || 'View source')}</a><p class="note">Retrieved: ${esc(p.retrieved_at)}</p></article>`).join('');
}
function productNotice(status) {
  const notes={not_configured:'Live shopping search is not configured. No current products were verified.',
    not_searched:'No live search was performed for this answer.',no_results:'Search completed, but no source listings matched the requested filters.',
    timeout:'Shopping search timed out. Retry your message.',quota_exhausted:'Shopping search quota is exhausted. Try again later.',
    authentication_failed:'Shopping search credentials were rejected. The owner needs to check the provider configuration.',
    unavailable:'Shopping search is temporarily unavailable. Retry your message.',provider_error:'Shopping search reported a provider error. Retry later.',
    invalid_query:'Shopping search could not use that query. Rephrase and retry.',rate_limited:'Shopping search reached its local limit. Try again later.'};
  return notes[status] ? `<p class="note" role="status">${esc(notes[status])}</p>` : '';
}
function safeSource(value) {
  try { const u = new URL(value); return u.protocol === 'https:' && !u.username && !u.password && (!u.port || u.port === '443') && u.hostname.includes('.') && !/^(?:localhost|127\.|10\.|192\.168\.|169\.254\.)/.test(u.hostname); } catch { return false; }
}
function addMessage(message) {
  const el = document.createElement('div'); el.className = 'msg ' + (message.role === 'user' ? 'user' : 'ai');
  if (message.role === 'user') el.innerHTML = `<div class="bubble">${esc(message.text)}</div>`;
  else if (message.result?.type === 'analysis') el.innerHTML = renderAnalysis(message.result);
  else if (message.result?.type === 'chat') {
    const r = message.result;
    el.innerHTML = `<article class="card chat-answer"><div class="reply-text">${esc(r.reply)}</div>${productCards(r.products)}${productNotice(r.product_status)}${r.product_status==='ok' && r.provider_status!=='ready' ? '<p class="note">The conversational comparison could not complete ('+esc(r.provider_status.replaceAll('_',' '))+').</p>' : ''}${message.retry ? '<button class="btn retry">Retry message</button>' : ''}</article>`;
  }
  else if (message.result?.type === 'analysis_only') el.innerHTML = '<div class="card"><p>Product recommendations are not available. Paste a product review to analyze its sentiment instead.</p></div>';
  else el.innerHTML = `<div class="card error-card"><p role="alert">${esc(message.text || 'Analysis is unavailable. Please try again.')}</p>${message.retry ? '<button class="btn retry">Retry message</button>' : ''}</div>`;
  const meta = document.createElement('div'); meta.className = 'meta'; meta.textContent = message.time?.includes('T') ? new Date(message.time).toLocaleString() : message.time || '';
  if (message.role === 'ai') {
    const copy = document.createElement('button'); copy.className = 'copy'; copy.textContent = 'Copy result';
    copy.onclick = () => navigator.clipboard?.writeText(el.innerText).then(() => toast('Result copied.'),() => toast('Select the result and copy it manually.'));
    meta.appendChild(copy);
  }
  el.appendChild(meta); $('#chat').appendChild(el);
  const retry = el.querySelector('.retry');
  if (retry) retry.onclick = () => send(message);
}
function persist() {
  if (!signedUser && rememberGuest) {
    // shortcut: keep the newest 20 guest chats, add storage management before increasing this limit.
    try { localStorage.setItem(GUEST_HISTORY_KEY,JSON.stringify(chats.slice(0,20))); }
    catch { toast('Device history could not be saved.'); }
  }
  $('#historyNote').textContent=signedUser ? 'Chats are saved to your account until you delete them.' : rememberGuest ? 'Guest chats are saved on this device.' : 'Guest chats stay in this tab. Enable device history in Settings to keep them.';
}
function renderHistory() {
  $('#hist').innerHTML = chats.length ? chats.map(c => `<li><button data-chat="${esc(c.id)}" ${c === current ? 'aria-current="true"' : ''}>${esc(c.title)}</button><button class="btn delete-chat" data-delete-chat="${esc(c.id)}" aria-label="Delete ${esc(c.title)}">Delete</button></li>`).join('') : '<li class="empty">No saved chats yet.</li>';
  $('#startNew').hidden = !current;
}
function showCurrent() {
  $('#chat').replaceChildren();
  if (current) current.messages.forEach(addMessage);
  else $('#chat').replaceChildren();
  renderHistory();
}
function newAnalysis() {
  if (busy) return toast('Please wait for the current reply.');
  current = null; showCurrent(); persist(); closeHistory(); $('#q').value = ''; $('#q').focus();
}
function rememberPreferences(chat,text) {
  chat.preferences ||= {};
  const patterns = {budget:/₹|\b(?:budget|rupees|rs)\b|\b(?:under|below)\s+\d/i,
    brand:/\b(?:prefer|brand|only)\b/i,priorities:/\b(?:priorit\w*|matters most|important|care about)\b/i};
  for (const [key,pattern] of Object.entries(patterns)) if (pattern.test(text)) chat.preferences[key] = text.slice(0,200);
}
function contextFor(messages,preferences = {}) {
  const notes = Object.entries(preferences).filter(([k,v]) => ['budget','brand','priorities'].includes(k) && typeof v === 'string').map(([k,v]) => `${k}: ${v.slice(0,200)}`).join('\n');
  const anchor = notes ? 'Previously stated preferences (user-provided, not verified product data):\n'+notes : '';
  let total = anchor.length; const history = [];
  for (const m of [...messages].reverse()) {
    let text = m.role === 'user' ? m.text : m.result?.type === 'chat' && m.result.response_source === 'gemini' ? m.result.reply : m.result?.type === 'analysis' ?
      `Review analysis: overall ${m.result.sentiment}. Rule-based aspects: ${m.result.aspects.map(a => a.name+': '+a.sentiment).join(', ')}. Scores are uncalibrated.` : null;
    if (!text || history.length >= (anchor ? 7 : 8) || total >= 4000) continue;
    text = text.slice(0,Math.min(1000,4000-total)); total += text.length;
    history.unshift({role:m.role === 'user' ? 'user' : 'assistant',text});
  }
  return anchor ? [{role:'user',text:anchor},...history] : history;
}
async function send(failedMessage = null) {
  const retry = failedMessage?.retry;
  const text = (retry?.text ?? $('#q').value).trim(); $('#hint').textContent = '';
  if (busy || historyLoading) return;
  if (!ReviewMindAuth.ready()) return toast('Sign in with Google to continue.');
  if (!text || text.length > 5000) { $('#hint').textContent = 'Enter a message between 1 and 5,000 characters.'; $('#q').focus(); return; }
  if (processingConsent === 'unknown' && (retry?.mode || $('#mode').value) !== 'review') {
    pendingConsent = failedMessage; $('#consentModal').showModal(); return;
  }
  const preferences = {category:retry?.category ?? $('#cat').value,language:retry?.language ?? $('#lang').value,mode:retry?.mode || $('#mode').value};
  if (!current) { current = {id:crypto.randomUUID(),title:text.slice(0,100),messages:[],preferences:{}}; chats.unshift(current); }
  const chat=current,epoch=accountEpoch;
  if (!retry) rememberPreferences(chat,text);
  const messages = retry ? chat.messages.slice(0,chat.messages.indexOf(failedMessage)-1) : chat.messages;
  const previous = [...messages].reverse().find(m => m.result?.type === 'analysis');
  const body = {text,...preferences,history:retry?.history || contextFor(messages,chat.preferences),analysis_request_id:retry?.analysis_request_id || previous?.result.request_id || null,allow_gemini:processingConsent === 'accepted',allow_product_search:processingConsent === 'accepted'};
  busy = true; $('#send').disabled = true; $('#send').textContent = 'Sending…'; $('#loading').hidden = false;
  $('#loading').textContent = 'Connecting to the assistant… The service may take up to a minute to wake up.';
  $('#results').setAttribute('aria-busy','true'); $('#welcome')?.remove();
  if (retry) chat.messages.splice(chat.messages.indexOf(failedMessage),1);
  else chat.messages.push({role:'user',text,time:new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})});
  if (!retry || $('#q').value.trim() === text) $('#q').value = '';
  showCurrent(); $('#results').scrollTop = $('#results').scrollHeight;
  try {
    if (signedUser && !chat.saved) {
      const saved=await ReviewMindAPI.createChat(chat.title);
      if (epoch!==accountEpoch) return;
      chat.id=saved.id;chat.saved=true;renderHistory();
    }
    if (signedUser) body.chat_id=chat.id;
    const result = await ReviewMindAPI.chat(body,() => { $('#loading').textContent = 'Finding an answer for you…'; });
    if (epoch!==accountEpoch) return;
    const recoverable=result.type==='chat' && (['timeout','quota_exhausted','authentication_failed','unavailable','provider_error','rate_limited','invalid_query','not_configured'].includes(result.product_status) || (result.product_status==='ok' && result.provider_status!=='ready'));
    chat.messages.push({role:'ai',result,...(recoverable ? {retry:body} : {}),time:new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})});
    if(recoverable && !$('#q').value) $('#q').value=text;
  } catch (error) {
    if (epoch!==accountEpoch) return;
    chat.messages.push({role:'ai',text:error.message,retry:body});
    if (current===chat && !$('#q').value) $('#q').value = text;
  } finally {
    busy = false; $('#send').disabled = false; $('#send').textContent = $('#mode').value==='review' ? 'Analyze' : 'Send'; $('#loading').hidden = true;
    $('#results').setAttribute('aria-busy','false'); showCurrent(); if (current===chat) persist();
    const latest = $('#chat .msg.ai:last-child'), area = $('#results');
    if (latest) latest.scrollIntoView?.({block:'start'});
  }
}
function closeHistory() { $('#side').hidden = true; $('#historyBtn').setAttribute('aria-expanded','false'); }
function toast(message) { $('#toast').textContent = message; $('#toast').classList.add('show'); setTimeout(() => $('#toast').classList.remove('show'),4000); }
function feedbackState(id) {
  if (!feedbackStates.has(id)) feedbackStates.set(id,{pending:false,receipt:null,exists:false,draft:{},status:''});
  return feedbackStates.get(id);
}
function updateFeedback() {
  const state = feedbackState(feedbackTarget);
  $('#sendFb').disabled = state.pending || !!state.receipt || state.exists;
  $('#sendFb').textContent = state.pending ? 'Submitting…' : (state.receipt || state.exists) ? 'Feedback submitted' : 'Submit Feedback';
  $('#deleteFeedback').hidden = !state.receipt;
  $('#deleteFeedback').disabled = !!state.deleting;
  $('#feedbackStatus').textContent = state.status;
  $('#feedbackForm').setAttribute('aria-busy',String(state.pending));
}
function openFeedback(id) {
  const prediction = chats.flatMap(c => c.messages).find(m => m.result?.request_id === id && m.result.type === 'analysis');
  if (!prediction) return toast('This prediction is no longer available in this session.');
  feedbackTarget = id; const state = feedbackState(id); $('#feedbackForm').reset();
  $('#feedbackRating').value = state.draft.rating || ''; $('#feedbackCorrection').value = state.draft.correction || '';
  $('#feedbackMessage').value = state.draft.message || ''; $('#feedbackConsent').checked = !!state.draft.consent;
  $('#feedbackTarget').textContent = `Overall sentiment: ${label(prediction.result.sentiment)} · Analysis ${id.slice(0,8)}`;
  updateFeedback(); $('#modal').showModal(); $('#modal .dialog-body').scrollTop = 0;
}
function rememberDraft() {
  if (feedbackTarget) feedbackState(feedbackTarget).draft = {rating:$('#feedbackRating').value,correction:$('#feedbackCorrection').value,message:$('#feedbackMessage').value,consent:$('#feedbackConsent').checked};
}
function validStoredMessage(m) {
  if (!m || typeof m !== 'object') return false;
  if (m.role === 'user') return typeof m.text === 'string' && m.text.length <= 5000;
  if (m.role !== 'ai') return false;
  if (!m.result) return typeof m.text === 'string' && m.text.length <= 2000 && (!m.retry ||
    (typeof m.retry.text === 'string' && m.retry.text.length <= 5000 && typeof m.retry.category === 'string' && ['en','hi','hinglish'].includes(m.retry.language) &&
      (!m.retry.history || (Array.isArray(m.retry.history) && m.retry.history.length <= 8 && m.retry.history.every(h => h && ['user','assistant'].includes(h.role) && typeof h.text === 'string' && h.text.length <= 1000)))));
  const r = m.result;
  if (r.type === 'chat') return typeof r.reply === 'string' && r.reply.length <= 6000 && ['built_in','gemini'].includes(r.response_source) && typeof r.provider_status === 'string';
  if (r.type === 'analysis_only') return r.status === 'not_available';
  return r.type === 'analysis' && ['positive','neutral','negative'].includes(r.sentiment) && typeof r.request_id === 'string' && typeof r.model_version === 'string' &&
    (r.confidence === null || (Number.isFinite(r.confidence) && r.confidence >= 0 && r.confidence <= 1)) && Array.isArray(r.warnings) && r.warnings.every(w => typeof w === 'string') &&
    Array.isArray(r.aspects) && r.aspects.every(a => a && typeof a.name === 'string' && LABELS.includes(a.sentiment));
}
(function init() {
  try {
    const savedConsent = localStorage.getItem(CONSENT_KEY);
    if (['accepted','declined'].includes(savedConsent)) processingConsent = savedConsent;
  } catch {}
  $('#processingConsent').value = processingConsent;
  $('#processingConsent').onchange = () => {
    if ($('#processingConsent').value === 'accepted' && processingConsent !== 'accepted') {
      $('#processingConsent').value = processingConsent; pendingConsent = undefined; $('#consentModal').showModal();
    } else setProcessingConsent($('#processingConsent').value);
  };
  for (const [id,choice] of [['acceptProcessing','accepted'],['declineProcessing','declined']]) $("#"+id).onclick = () => {
    const pending = pendingConsent; setProcessingConsent(choice); $('#consentModal').close();
    if (pending !== undefined) send(pending);
  };
  showCurrent();
  const submit = () => {
    const failed=current?.messages.at(-1);
    send(failed?.retry?.text === $('#q').value.trim() ? failed : undefined);
  };
  $('#analysisForm').onsubmit = e => { e.preventDefault(); submit(); };
  $('#mode').value='review';
  const updateMode=() => {
    const review=$('#mode').value==='review';
    $('#reviewOptions').hidden=!review;$('#sampleReview').hidden=!review;
    $('#send').textContent=review ? 'Analyze' : 'Send';
  };
  $('#mode').onchange=updateMode;updateMode();
  $('#sampleReview').onclick=() => {
    if (busy) return;
    $('#mode').value='review';$('#cat').value='Smartphones';$('#lang').value='en';updateMode();
    $('#q').value='The camera is excellent in daylight, but the battery drains by noon and charging is painfully slow.';
    $('#q').focus();
  };
  try {
    rememberGuest=localStorage.getItem('reviewmind_remember_guest')==='true';
  } catch {}
  $('#rememberGuest').checked=rememberGuest;
  $('#rememberGuest').onchange=() => {
    rememberGuest=$('#rememberGuest').checked;
    try {localStorage.setItem('reviewmind_remember_guest',String(rememberGuest));if(!rememberGuest)localStorage.removeItem(GUEST_HISTORY_KEY);} catch {}
    persist();
  };
  $('#q').onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); } };
  $('#lang').onchange = () => { const t = I18N[$('#lang').value]; $('[data-i="hello"]').textContent = t.hello; $('[data-i="sub"]').textContent = t.sub; $('#q').placeholder = t.placeholder; document.documentElement.lang = $('#lang').value === 'hi' ? 'hi' : 'en'; };
  $('#newChat').onclick = newAnalysis; $('#startNew').onclick = newAnalysis;
  $('#historyBtn').onclick = () => { $('#side').hidden = !$('#side').hidden; $('#historyBtn').setAttribute('aria-expanded',String(!$('#side').hidden)); if (!$('#side').hidden) $('#closeSide').focus(); };
  $('#closeSide').onclick = () => { closeHistory(); $('#historyBtn').focus(); };
  $('#settingsBtn').onclick = () => { closeHistory(); $('#settingsModal').showModal(); };
  $('#sideSettings').onclick = $('#settingsBtn').onclick;
  $('#helpBtn').onclick = () => { closeHistory(); $('#helpModal').showModal(); };
  $('#sideHelp').onclick = $('#helpBtn').onclick; $('#closeHelp').onclick = () => $('#helpModal').close();
  $('#closeSettings').onclick = () => $('#settingsModal').close();
  $('#mclose').onclick = () => $('#modal').close(); $('#modal').addEventListener('close',rememberDraft);
  $('#feedbackForm').oninput = rememberDraft;
  document.addEventListener('click',async e => {
    const deletion=e.target.closest('[data-delete-chat]');
    if (deletion && !busy && !historyLoading) {
      const chat=chats.find(c => c.id===deletion.dataset.deleteChat);
      if (!chat || !window.confirm('Delete this chat? This cannot be undone.')) return;
      const epoch=accountEpoch;busy=true;
      try {
        if (signedUser && chat.saved) await ReviewMindAPI.deleteChat(chat.id);
        if (epoch!==accountEpoch) return;
        chats=chats.filter(c => c!==chat);if(current===chat)current=null;showCurrent();persist();toast('Chat deleted.');
      } catch(error) {toast(error.message);} finally {busy=false;}
    }
    const chatButton=e.target.closest('[data-chat]');
    if (chatButton && !busy && !historyLoading) {
      const chat=chats.find(c => c.id===chatButton.dataset.chat),epoch=accountEpoch;
      if (!chat)return;
      busy=true;
      try {
        if (chat.saved) {
          const saved=await ReviewMindAPI.getChat(chat.id);
          if (epoch!==accountEpoch)return;
          chat.messages=(saved.messages || []).filter(validStoredMessage);chat.preferences={};
          chat.messages.filter(m => m.role==='user').forEach(m => rememberPreferences(chat,m.text));
        }
        current=chat;showCurrent();persist();closeHistory();
      } catch(error) {toast(error.message);} finally {busy=false;}
    }
    const button=e.target.closest('[data-request]');if(button)openFeedback(button.dataset.request);
  });
  document.addEventListener('keydown',e => { if (e.key === 'Escape' && !$('#side').hidden) { closeHistory(); $('#historyBtn').focus(); } });
  $('#clearHist').onclick = async () => {
    if (busy || historyLoading) return toast('Please wait for the current request.');
    if (!chats.length || !window.confirm('Delete all your saved chats? This cannot be undone.')) return;
    const epoch=accountEpoch;busy=true;
    try {
      if (signedUser) await ReviewMindAPI.clearChats();
      if (epoch!==accountEpoch) return;
      chats=[];current=null;showCurrent();persist();toast('Chats deleted.');
    } catch(error) {toast(error.message);} finally {busy=false;}
  };
  $('#themeBtn').onclick = () => { const dark = document.documentElement.dataset.theme !== 'dark'; document.documentElement.dataset.theme = dark ? 'dark' : 'light'; $('#themeBtn').textContent = dark ? 'Light theme' : 'Dark theme'; $('#themeBtn').setAttribute('aria-label',dark ? 'Switch to light theme' : 'Switch to dark theme'); };
  $('#feedbackForm').onsubmit = async e => {
    e.preventDefault(); if (!feedbackTarget || !$('#feedbackForm').reportValidity()) return;
    const id = feedbackTarget, state = feedbackState(id);
    if (state.pending || state.receipt || state.exists) return;
    rememberDraft(); state.pending = true; state.status = 'Submitting your feedback…'; updateFeedback();
    try {
      state.receipt = await ReviewMindAPI.feedback({request_id:id,rating:Number(state.draft.rating),correction:state.draft.correction || null,message:state.draft.message.trim() || null,consent:state.draft.consent});
      state.status = 'Feedback saved. Thank you. You can delete it below while this session is open.';
    } catch (error) { state.exists = error.status === 409; state.status = state.exists ? 'Feedback has already been saved for this analysis. Another submission will not be sent.' : error.message; }
    finally { state.pending = false; if (feedbackTarget === id) updateFeedback(); }
  };
  $('#deleteFeedback').onclick = async () => {
    const id = feedbackTarget, state = feedbackState(id); if (!state.receipt || state.deleting) return;
    state.deleting = true; updateFeedback();
    try { await ReviewMindAPI.deleteFeedback(state.receipt.feedback_id,state.receipt.delete_token); state.receipt = null; state.exists = false; state.status = 'Feedback deleted.'; }
    catch (error) { state.status = error.message; }
    finally { state.deleting = false; if (feedbackTarget === id) updateFeedback(); }
  };
})();


window.addEventListener('reviewmind-auth',async event => {
  const epoch=++accountEpoch;signedUser=event.detail;
  chats=[];current=null;$('#q').value='';$('#hint').textContent='';closeHistory();
  document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close());
  feedbackTarget=null;feedbackStates.clear();showCurrent();
  $('#deviceHistoryOption').hidden=!!signedUser;
  if (!signedUser) {
    historyLoading=false;
    if(rememberGuest) try {
      const saved=JSON.parse(localStorage.getItem(GUEST_HISTORY_KEY) || '[]');
      if(Array.isArray(saved)) chats=saved.slice(0,20).filter(c => typeof c.id==='string' && typeof c.title==='string' && Array.isArray(c.messages) && c.messages.every(validStoredMessage)).map(c => ({...c,saved:false}));
    } catch {}
    showCurrent();persist();return;
  }
  historyLoading=true;$('#send').disabled=true;$('#historyNote').textContent='Loading your chats…';
  try {
    const result=await ReviewMindAPI.chats();
    if (epoch!==accountEpoch)return;
    chats=result.chats.map(c => ({...c,saved:true,messages:[],preferences:{}}));
    showCurrent();persist();
  } catch(error) {if(epoch===accountEpoch) $('#historyNote').textContent=error.message;}
  finally {if(epoch===accountEpoch){historyLoading=false;$('#send').disabled=busy;}}
});
ReviewMindAuth.init();
