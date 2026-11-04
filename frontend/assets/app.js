/* Existing HTML/CSS design; only API-backed analysis is rendered as an AI result. */
const $ = s => document.querySelector(s);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const inr = value => '₹' + Number(value).toLocaleString('en-IN');
const SENT = {positive:'var(--pos)', neutral:'var(--neu)', negative:'var(--neg)', mixed:'var(--neu)', unknown:'var(--muted)'};
const PRIORITIES = ['Battery','Camera','Performance','Display','Build quality','Value for money'];
const I18N = {
  en:{tag:'Experimental review analysis · Guest beta',hello:'What are the reviews saying? 💬',new:'New chat',sub:'Paste a review for real sentiment inference. Product rankings, fake-review detection and verified multilingual accuracy are not available yet.',ph:'Paste a review… (Enter to analyze, Shift+Enter for new line)'},
  hi:{tag:'प्रायोगिक रिव्यू विश्लेषण · गेस्ट बीटा',hello:'रिव्यू क्या कह रहे हैं? 💬',new:'नई चैट',sub:'रिव्यू का विश्लेषण करें। हिन्दी सटीकता प्रमाणित नहीं है। प्रोडक्ट सुझाव और नकली रिव्यू पहचान अभी उपलब्ध नहीं हैं।',ph:'रिव्यू यहाँ लिखें…'},
  hinglish:{tag:'Experimental review analysis · Guest beta',hello:'Reviews kya keh rahe hain? 💬',new:'Nayi chat',sub:'Review paste karo. Hindi/Hinglish accuracy verified nahi hai. Product ranking aur fake-review detection abhi available nahi hain.',ph:'Apna review yahan paste karo…'}
};
const EXAMPLES = [
  {text:'The sound is clear but the battery is poor.',mode:'analyze',category:'Audio devices'},
  {text:'The keyboard is comfortable and performance is good.',mode:'analyze',category:'Laptops'},
  {text:'Best smartphone under ₹20,000?',mode:'recommend',category:'Smartphones'},
  {text:'Compare earbuds for battery and comfort',mode:'recommend',category:'Audio devices'}
];
const HISTORY_KEY = 'reviewmind_guest_history_v1';
let chats = [], current = null, busy = false, feedbackTarget = null, feedbackReceipt = null;
const profile = {name:'Guest',style:'friendly'};
const priorities = new Set();

async function getAIResponse(query, preferences) {
  const mode = $('#task').value;
  // Request routing only: this is not a product-ranking or sentiment model.
  const productQuestion = /^(?:(?:best|which)\b.*(?:\?|under\b|below\b|budget\b|buy\b)|(?:recommend|suggest|compare)\b|(?:kaunsa|konsa|kaunsi)\b|कौन|सुझाव|तुलना|बेस्ट)/i.test(query);
  return mode === 'recommend' || (mode === 'auto' && productQuestion) ? ReviewMindAPI.recommend(query, preferences) : ReviewMindAPI.analyze(query, preferences);
}
function currentPrefs() {
  return {category:$('#cat').value,budget:+$('#budget').value,priorities:[...priorities],language:$('#lang').value,style:profile.style,user_name:'Guest'};
}
function renderAnalysis(data) {
  const score = data.confidence === null ? '' : `<p class="note">Uncalibrated model score: ${Number(data.confidence).toFixed(3)} · not a reliability percentage.</p>`;
  const mentions = data.aspects.length ? data.aspects.map(a => `<div class="bar-row"><span>${esc(a.name)}</span><span class="tag" style="color:${SENT[a.sentiment]}">${esc(a.sentiment)}</span><span></span></div>`).join('') : '<p class="note">No supported aspect mentions were found for this category and text.</p>';
  return `<div class="ai-full"><div class="card"><span class="badge">Real model inference · beta</span><h4>Overall sentiment: ${esc(data.sentiment)}</h4>${score}<p class="note">Model: ${esc(data.model_version)}</p></div>
    <div class="card"><h4>Aspect mentions · rule baseline</h4>${mentions}<p class="note">Local lexical rules, not supervised ABSA. No aspect percentages, product scores or aggregate review evidence are inferred.</p></div>
    <div class="card analysis-warnings">${data.warnings.map(w => `<p>${esc(w)}</p>`).join('')}<button class="btn prediction-feedback" data-request="${esc(data.request_id)}">Give feedback on this prediction</button></div></div>`;
}
function unavailable(data) {
  return `<div class="ai-full"><div class="card"><h4>Product intelligence · upcoming</h4><p>${esc(data.message)}</p></div>
    <div class="grid2"><div class="card"><h4>Fake-review radar · unavailable</h4><p class="note">No validated detector or trust scores are available.</p></div><div class="card"><h4>Comparisons & review evidence · unavailable</h4><p class="note">No validated catalog ranking, pricing or redistributable evidence is connected.</p></div></div></div>`;
}
function skeleton() {
  return '<div class="card" aria-label="Loading"><div class="typing" role="status"><i></i><i></i><i></i><span class="sr">Running real model analysis</span></div><div class="skel" style="width:70%"></div><div class="skel"></div><div class="skel" style="width:85%"></div></div>';
}
function addMessage(message) {
  const el = document.createElement('div'); el.className = 'msg ' + (message.role === 'user' ? 'user' : 'ai');
  let html;
  if (message.role === 'user') html = `<div class="bubble">${esc(message.text)}</div>`;
  else if (message.result?.type === 'analysis') html = renderAnalysis(message.result);
  else if (message.result?.type === 'analysis_only') html = unavailable(message.result);
  else html = `<div class="bubble err" role="alert">${esc(message.text || 'Analysis unavailable.')}</div>`;
  el.innerHTML = html + `<div class="meta"><time>${esc(message.time || '')}</time>${message.role === 'ai' ? '<button class="copy" aria-label="Copy reply">Copy</button>' : ''}</div>`;
  $('#chat').appendChild(el); $('#scroll').scrollTop = $('#scroll').scrollHeight;
  return el;
}
function persist() {
  try {
    if ($('#remember').checked) localStorage.setItem(HISTORY_KEY, JSON.stringify({chats:chats.slice(0,20),current:current?.id || null}));
    else localStorage.removeItem(HISTORY_KEY);
  } catch { toast('Browser storage is unavailable; this chat stays in memory.'); }
}
function renderHistory() {
  $('#hist').innerHTML = chats.length ? chats.map(c => `<li><button data-chat="${esc(c.id)}" ${c === current ? 'aria-current="true"' : ''}>${esc(c.title)}</button></li>`).join('') : '<li class="empty">No chats yet</li>';
  $('#saved').innerHTML = '<li class="empty">Product saves & comparisons · upcoming</li>';
}
function welcomeEl() {
  const section = document.createElement('section'); section.className = 'welcome'; section.id = 'welcome';
  const language = I18N[$('#lang').value]; section.innerHTML = `<h1>${esc(language.hello)}</h1><p>${esc(language.sub)}</p><div class="examples"></div>`;
  EXAMPLES.forEach(example => { const button = document.createElement('button'); button.className = 'ex'; button.textContent = example.text;
    button.onclick = () => { $('#task').value = example.mode; $('#cat').value = example.category; updatePrefSummary(); send(example.text); }; section.lastChild.appendChild(button); });
  return section;
}
function showCurrent() {
  $('#chat').replaceChildren();
  if (!current) $('#chat').appendChild(welcomeEl()); else current.messages.forEach(addMessage);
  renderHistory();
}
function newChat() { if (busy) return toast('Please wait for the current analysis.'); current = null; showCurrent(); persist(); closeSide(); }
async function send(text) {
  text = (text ?? $('#q').value).trim(); $('#hint').textContent = '';
  if (!text || text.length > 5000) { $('#hint').textContent = 'Enter a review or question between 1 and 5,000 characters.'; return; }
  if (busy) return;
  busy = true; $('#send').disabled = true; $('#welcome')?.remove();
  if (!current) { current = {id:crypto.randomUUID(),title:text.slice(0,100),messages:[]}; chats.unshift(current); chats = chats.slice(0,20); }
  const message = {role:'user',text,time:new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})};
  current.messages.push(message); addMessage(message); renderHistory(); $('#q').value = ''; autosize();
  const loader = document.createElement('div'); loader.className = 'msg ai'; loader.innerHTML = skeleton(); $('#chat').appendChild(loader);
  try {
    const result = await getAIResponse(text,currentPrefs()); loader.remove();
    const reply = {role:'ai',result,time:new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})};
    current.messages.push(reply); addMessage(reply);
    if (result.type === 'analysis') feedbackTarget = result.request_id;
  } catch (error) {
    loader.remove(); const reply = {role:'ai',text:error.message}; current.messages.push(reply); addMessage(reply);
  } finally {
    current.messages = current.messages.slice(-50); busy = false; $('#send').disabled = false; $('#q').focus(); persist();
  }
}
const mobile = () => matchMedia('(max-width:820px)').matches;
const sideOpen = () => mobile() ? $('#side').classList.contains('open') : !$('.app').classList.contains('collapsed');
function setSide(open) { if (mobile()) { $('#side').classList.toggle('open',open); $('#backdrop').classList.toggle('show',open); } else $('.app').classList.toggle('collapsed',!open); $('#menuBtn').setAttribute('aria-expanded',String(open)); if (!open) $('#pmenu').hidden = true; }
function closeSide() { if (mobile()) setSide(false); }
function toast(message) { $('#toast').textContent = message; $('#toast').classList.add('show'); setTimeout(() => $('#toast').classList.remove('show'),3000); }
function openModal(tab) {
  document.querySelectorAll('.mtabs button').forEach(b => b.setAttribute('aria-selected',String(b.dataset.tab === tab)));
  document.querySelectorAll('.mpanel').forEach(p => p.hidden = p.id !== 'tab-' + tab);
  $('#pmenu').hidden = true; $('#pbtn').setAttribute('aria-expanded','false');
  $('#feedbackTarget').textContent = feedbackTarget ? 'Feedback applies to the selected model prediction.' : 'Select a real analysis reply first.';
  if (!$('#modal').open) $('#modal').showModal();
}
function autosize() { $('#q').style.height = 'auto'; $('#q').style.height = Math.min($('#q').scrollHeight,140) + 'px'; }
function updatePrefSummary() { const p = currentPrefs(); $('#budVal').textContent = inr(p.budget); $('#prefSum').textContent = '· ' + [p.category || 'Any category','≤ ' + inr(p.budget),...p.priorities].join(', '); }
function applyLang() { const l = I18N[$('#lang').value]; document.querySelectorAll('[data-i]').forEach(n => { if (l[n.dataset.i]) n.textContent = l[n.dataset.i]; }); $('#q').placeholder = l.ph; document.documentElement.lang = $('#lang').value === 'hi' ? 'hi' : 'en'; }

(function init() {
  PRIORITIES.forEach(name => { const b = document.createElement('button'); b.type = 'button'; b.className = 'chip'; b.textContent = name; b.setAttribute('aria-pressed','false'); b.onclick = () => { priorities.has(name) ? priorities.delete(name) : priorities.add(name); b.setAttribute('aria-pressed',String(priorities.has(name))); updatePrefSummary(); }; $('#chips').appendChild(b); });
  try {
    const stored = localStorage.getItem(HISTORY_KEY);
    if (stored && stored.length < 2000000) {
      const parsed = JSON.parse(stored); if (Array.isArray(parsed.chats)) {
        chats = parsed.chats.filter(c => typeof c.id === 'string' && typeof c.title === 'string' && Array.isArray(c.messages)).slice(0,20);
        chats.forEach(c => { c.title = c.title.slice(0,100); c.messages = c.messages.slice(-50).filter(m => {
          if (m.role === 'user') return typeof m.text === 'string' && m.text.length <= 5000;
          if (m.role !== 'ai') return false;
          if (!m.result) return typeof m.text === 'string' && m.text.length <= 2000;
          const r = m.result;
          if (r.type === 'analysis_only') return r.status === 'not_available' && typeof r.message === 'string';
          return r.type === 'analysis' && ['positive','neutral','negative'].includes(r.sentiment) && typeof r.model_version === 'string' &&
            Array.isArray(r.warnings) && r.warnings.every(w => typeof w === 'string') && Array.isArray(r.aspects) &&
            r.aspects.every(a => typeof a.name === 'string' && Object.hasOwn(SENT,a.sentiment));
        }); });
        current = chats.find(c => c.id === parsed.current) || null; $('#remember').checked = true;
      }
    }
  } catch { chats = []; current = null; }
  showCurrent(); if (mobile()) $('#prefs').open = false;
  $('#budget').oninput = updatePrefSummary; $('#cat').onchange = updatePrefSummary;
  $('#lang').onchange = () => { applyLang(); if (!current) showCurrent(); };
  $('#send').onclick = () => send(); $('#q').oninput = autosize;
  $('#q').addEventListener('keydown',e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
  $('#newChat').onclick = newChat; $('#menuBtn').onclick = () => setSide(!sideOpen()); $('#closeSide').onclick = () => setSide(false); $('#backdrop').onclick = () => setSide(false);
  $('#menuBtn').setAttribute('aria-expanded',String(!mobile()));
  $('#pbtn').onclick = () => { const hidden = $('#pmenu').hidden; $('#pmenu').hidden = !hidden; $('#pbtn').setAttribute('aria-expanded',String(hidden)); };
  document.addEventListener('click',e => {
    if (!e.target.closest('.profile')) { $('#pmenu').hidden = true; $('#pbtn').setAttribute('aria-expanded','false'); }
    const open = e.target.closest('[data-open]'); if (open) openModal(open.dataset.open);
    const chat = e.target.closest('[data-chat]'); if (chat && !busy) { current = chats.find(c => c.id === chat.dataset.chat); showCurrent(); persist(); closeSide(); }
    const feedback = e.target.closest('[data-request]'); if (feedback) { feedbackTarget = feedback.dataset.request; openModal('help'); }
    if (e.target.classList.contains('copy')) navigator.clipboard?.writeText(e.target.closest('.msg').innerText).then(() => toast('Reply copied.'),() => toast('Select the reply and copy it manually.'));
  });
  document.addEventListener('keydown',e => { if (e.key === 'Escape') { $('#pmenu').hidden = true; closeSide(); } });
  document.querySelectorAll('.mtabs button').forEach(b => b.onclick = () => openModal(b.dataset.tab));
  $('#mclose').onclick = () => $('#modal').close(); $('#modal').onclick = e => { if (e.target === $('#modal')) $('#modal').close(); };
  $('#logout').onclick = () => toast('Guest mode: there is no authenticated account to log out of.');
  $('#clearHist').onclick = () => { if (busy) return toast('Wait for the current analysis before clearing history.'); chats = []; current = null; feedbackTarget = null;
    try { localStorage.removeItem(HISTORY_KEY); toast('Local chat history cleared. Server feedback has separate retention.'); }
    catch { toast('Memory history cleared; browser storage access is blocked.'); } showCurrent(); };
  $('#remember').onchange = persist;
  $('#nameIn').oninput = e => { profile.name = e.target.value.trim() || 'Guest'; $('#pname').textContent = profile.name; $('#avatar').textContent = profile.name[0].toUpperCase(); };
  $('#themeBtn').onclick = () => { const dark = document.documentElement.dataset.theme === 'dark'; document.documentElement.dataset.theme = dark ? 'light' : 'dark'; $('#themeBtn').textContent = dark ? '🌙' : '☀️'; };
  $('#feedbackForm').onsubmit = async e => {
    e.preventDefault(); $('#feedbackStatus').textContent = '';
    if (!feedbackTarget) { $('#feedbackStatus').textContent = 'Select a real analysis reply first.'; return; }
    $('#sendFb').disabled = true;
    try {
      feedbackReceipt = await ReviewMindAPI.feedback({request_id:feedbackTarget,rating:Number($('#feedbackRating').value),
        correction:$('#feedbackCorrection').value || null,message:$('#feedbackMessage').value.trim() || null,consent:$('#feedbackConsent').checked});
      $('#feedbackStatus').textContent = 'Feedback stored successfully. The original review text was not submitted with it.';
      $('#deleteFeedback').hidden = false;
    } catch (error) { $('#feedbackStatus').textContent = error.message; }
    finally { $('#sendFb').disabled = false; }
  };
  $('#deleteFeedback').onclick = async () => {
    if (!feedbackReceipt) return;
    try { await ReviewMindAPI.deleteFeedback(feedbackReceipt.feedback_id,feedbackReceipt.delete_token); $('#feedbackStatus').textContent = 'Feedback deleted.'; $('#deleteFeedback').hidden = true; feedbackReceipt = null; }
    catch (error) { $('#feedbackStatus').textContent = error.message; }
  };
  applyLang(); updatePrefSummary();
})();
