/* Chat routing is server-side; only actual classifier results get prediction feedback. */
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const LABELS = ['positive','negative','neutral','mixed','unknown'];
const label = value => value === 'unknown' ? 'Not determined' : value.charAt(0).toUpperCase() + value.slice(1);
const HISTORY_KEY = 'reviewmind_guest_history_v1';
const I18N = {
  en:{hello:'Let’s understand your product reviews',sub:'Ask a question, paste a review, or follow up on an analysis.',placeholder:'Ask about a review, or paste one to analyze…'},
  hi:{hello:'AI के साथ प्रोडक्ट रिव्यू समझें',sub:'रिव्यू का समग्र भाव और प्रोडक्ट फीचर देखें। हिन्दी की सटीकता अभी प्रमाणित नहीं है।',placeholder:'विश्लेषण के लिए प्रोडक्ट रिव्यू यहाँ लिखें…'},
  hinglish:{hello:'AI se product reviews samjhein',sub:'Review paste karein aur overall sentiment aur product features dekhein. Hinglish accuracy abhi verified nahi hai.',placeholder:'Product review yahan paste karein…'}
};
let chats = [], current = null, busy = false, feedbackTarget = null;
const feedbackStates = new Map();
function renderAnalysis(data) {
  const mentions = data.aspects.length ? `<ul class="aspect-list">${data.aspects.map(a => `<li><span>${esc(a.name)}</span><span class="${esc(a.sentiment)}">${esc(label(a.sentiment))}</span></li>`).join('')}</ul>` : '<p class="note">No matching product features were found. Check the selected category. Some features may not be covered by our rules.</p>';
  const score = data.confidence === null ? 'This model does not provide an analysis score.' : `Analysis score: <strong>${Number(data.confidence).toFixed(3)}</strong>`;
  return `<div class="ai-full"><article class="card"><div class="result-top"><h3>Overall sentiment</h3><span class="sentiment ${esc(data.sentiment)}">${esc(label(data.sentiment))}</span></div>
    <p class="analysis-score">${score}</p><p class="note">A model score, not a reliability percentage or product rating.</p>
    <h3>Product aspects</h3>${mentions}<p class="note">Feature mentions and their sentiment use keyword rules, separate from the overall AI prediction.</p>
    <details class="analysis-about"><summary>About this analysis</summary><p>Model: ${esc(data.model_version)}</p><p>The overall model learned from star ratings rather than independently annotated sentiment. Scores are uncalibrated. Aspect rules can miss context and are not a trained aspect sentiment model.</p><ul>${data.warnings.map(w => `<li>${esc(w)}</li>`).join('')}</ul></details>
    <div class="analysis-actions"><button class="btn prediction-feedback" data-request="${esc(data.request_id)}">Give feedback on this analysis</button></div></article></div>`;
}
function addMessage(message) {
  const el = document.createElement('div'); el.className = 'msg ' + (message.role === 'user' ? 'user' : 'ai');
  if (message.role === 'user') el.innerHTML = `<div class="bubble">${esc(message.text)}</div>`;
  else if (message.result?.type === 'analysis') el.innerHTML = renderAnalysis(message.result);
  else if (message.result?.type === 'chat') {
    const r = message.result;
    el.innerHTML = `<article class="card chat-answer"><p class="response-source">${r.response_source === 'gemini' ? 'Gemini · conversational answer' : 'Built-in guide · not a language-model answer'}</p><div class="reply-text">${esc(r.reply)}</div>${['timeout','unavailable','busy','rate_limited','invalid_response','blocked','ungrounded_response'].includes(r.provider_status) ? '<p class="note">The conversational provider did not return an answer. You can resend your message when it is available.</p>' : ''}</article>`;
  }
  else if (message.result?.type === 'analysis_only') el.innerHTML = '<div class="card"><p>Product recommendations are not available. Paste a product review to analyze its sentiment instead.</p></div>';
  else el.innerHTML = `<div class="card error-card"><p role="alert">${esc(message.text || 'Analysis is unavailable. Please try again.')}</p>${message.retry ? '<button class="btn retry">Retry message</button>' : ''}</div>`;
  const meta = document.createElement('div'); meta.className = 'meta'; meta.textContent = message.time || '';
  if (message.role === 'ai') {
    const copy = document.createElement('button'); copy.className = 'copy'; copy.textContent = 'Copy result';
    copy.onclick = () => navigator.clipboard?.writeText(el.innerText).then(() => toast('Result copied.'),() => toast('Select the result and copy it manually.'));
    meta.appendChild(copy);
  }
  el.appendChild(meta); $('#chat').appendChild(el);
  const retry = el.querySelector('.retry');
  if (retry) retry.onclick = () => { $('#q').value = message.retry.text; $('#cat').value = message.retry.category; $('#lang').value = message.retry.language; $('#mode').value = message.retry.mode || 'auto'; send(); };
}
function persist() {
  try {
    if ($('#remember').checked) localStorage.setItem(HISTORY_KEY,JSON.stringify({chats:chats.slice(0,20),current:current?.id || null}));
    else localStorage.removeItem(HISTORY_KEY);
  } catch { toast('Device storage is unavailable. This history stays in the current session.'); }
  $('#historyNote').textContent = $('#remember').checked ? 'History is saved on this device. Clear it in Settings.' : 'History stays in this session unless you choose to save it on this device.';
}
function renderHistory() {
  $('#hist').innerHTML = chats.length ? chats.map(c => `<li><button data-chat="${esc(c.id)}" ${c === current ? 'aria-current="true"' : ''}>${esc(c.title)}</button></li>`).join('') : '<li class="empty">No local chats yet.</li>';
  $('#startNew').hidden = !current;
}
function showCurrent() {
  $('#chat').replaceChildren();
  if (current) current.messages.forEach(addMessage);
  else $('#chat').innerHTML = '<p class="empty" id="welcome">No messages yet. Say hello or paste a product review to get started.</p>';
  renderHistory();
}
function newAnalysis() {
  if (busy) return toast('Please wait for the current reply.');
  current = null; showCurrent(); persist(); closeHistory(); $('#q').value = ''; $('#q').focus();
}
function contextFor(messages) {
  let total = 0; const history = [];
  for (const m of [...messages].reverse()) {
    let text = m.role === 'user' ? m.text : m.result?.type === 'chat' ? m.result.reply : m.result?.type === 'analysis' ?
      `Review analysis: overall ${m.result.sentiment}. Rule-based aspects: ${m.result.aspects.map(a => a.name+': '+a.sentiment).join(', ')}. Scores are uncalibrated.` : null;
    if (!text || history.length >= 8 || total >= 4000) continue;
    text = text.slice(0,Math.min(1000,4000-total)); total += text.length;
    history.unshift({role:m.role === 'user' ? 'user' : 'assistant',text});
  }
  return history;
}
async function send() {
  const text = $('#q').value.trim(); $('#hint').textContent = '';
  if (busy) return;
  if (!text || text.length > 5000) { $('#hint').textContent = 'Enter a message between 1 and 5,000 characters.'; $('#q').focus(); return; }
  const preferences = {category:$('#cat').value,language:$('#lang').value,mode:$('#mode').value};
  const messages = current?.messages || [];
  const previous = [...messages].reverse().find(m => m.result?.type === 'analysis');
  const body = {text,...preferences,history:contextFor(messages),analysis_request_id:previous?.result.request_id || null,allow_gemini:$('#allowGemini').checked};
  busy = true; $('#send').disabled = true; $('#send').textContent = 'Sending…'; $('#loading').hidden = false;
  $('#loading').textContent = 'Connecting to the assistant… The service may take up to a minute to wake up.';
  $('#results').setAttribute('aria-busy','true'); $('#welcome')?.remove();
  if (!current) { current = {id:crypto.randomUUID(),title:text.slice(0,100),messages:[]}; chats.unshift(current); chats = chats.slice(0,20); }
  current.messages.push({role:'user',text,time:new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})});
  $('#q').value = ''; showCurrent(); $('#results').scrollTop = $('#results').scrollHeight;
  try {
    const result = await ReviewMindAPI.chat(body,() => { $('#loading').textContent = 'Preparing your reply… Review predictions and Gemini conversation use separate models.'; });
    current.messages.push({role:'ai',result,time:new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})});
  } catch (error) {
    current.messages.push({role:'ai',text:error.message,retry:{text,...preferences}});
  } finally {
    current.messages = current.messages.slice(-50); busy = false; $('#send').disabled = false; $('#send').textContent = 'Send'; $('#loading').hidden = true;
    $('#results').setAttribute('aria-busy','false'); showCurrent(); persist();
    const latest = $('#chat .msg.ai:last-child'), area = $('#results');
    if (latest) area.scrollTop += latest.getBoundingClientRect().top - area.getBoundingClientRect().top - 8;
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
    (typeof m.retry.text === 'string' && m.retry.text.length <= 5000 && typeof m.retry.category === 'string' && ['en','hi','hinglish'].includes(m.retry.language)));
  const r = m.result;
  if (r.type === 'chat') return typeof r.reply === 'string' && r.reply.length <= 6000 && ['built_in','gemini'].includes(r.response_source) && typeof r.provider_status === 'string';
  if (r.type === 'analysis_only') return r.status === 'not_available';
  return r.type === 'analysis' && ['positive','neutral','negative'].includes(r.sentiment) && typeof r.request_id === 'string' && typeof r.model_version === 'string' &&
    (r.confidence === null || (Number.isFinite(r.confidence) && r.confidence >= 0 && r.confidence <= 1)) && Array.isArray(r.warnings) && r.warnings.every(w => typeof w === 'string') &&
    Array.isArray(r.aspects) && r.aspects.every(a => a && typeof a.name === 'string' && LABELS.includes(a.sentiment));
}
(function init() {
  try {
    const stored = localStorage.getItem(HISTORY_KEY);
    if (stored && stored.length < 2000000) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed.chats)) {
        chats = parsed.chats.filter(c => c && typeof c.id === 'string' && typeof c.title === 'string' && Array.isArray(c.messages)).slice(0,20);
        chats.forEach(c => { c.title = c.title.slice(0,100); c.messages = c.messages.slice(-50).filter(validStoredMessage); });
        current = chats.find(c => c.id === parsed.current) || null; $('#remember').checked = true;
      }
    }
  } catch { chats = []; current = null; }
  showCurrent();
  $('#analysisForm').onsubmit = e => { e.preventDefault(); send(); };
  $('#q').onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } };
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
  document.addEventListener('click',e => {
    const chat = e.target.closest('[data-chat]'); if (chat && !busy) { current = chats.find(c => c.id === chat.dataset.chat); showCurrent(); persist(); closeHistory(); }
    const button = e.target.closest('[data-request]'); if (button) openFeedback(button.dataset.request);
  });
  document.addEventListener('keydown',e => { if (e.key === 'Escape' && !$('#side').hidden) { closeHistory(); $('#historyBtn').focus(); } });
  $('#remember').onchange = persist;
  $('#clearHist').onclick = () => {
    if (busy) return toast('Wait for the current analysis before clearing history.');
    chats = []; current = null;
    try { localStorage.removeItem(HISTORY_KEY); toast('Analysis history cleared. Submitted feedback is kept separately.'); }
    catch { toast('Session cleared, but device storage could not be accessed.'); }
    showCurrent();
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
