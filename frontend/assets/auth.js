/* Identity tokens stay in memory; every protected request is verified by the API. */
(() => {
  let token='',user=null,required=true,timer;
  const el=id => document.getElementById(id);
  function render() {
    const ready=!required || !!user;
    el('authPanel').hidden=ready;el('chatApp').hidden=false;
    el('account').hidden=!user;el('accountEmail').textContent=user?.email || '';
    document.querySelector('header nav').hidden=false;
  }
  function reset(message='Sign in with Google to continue.') {
    token='';user=null;clearTimeout(timer);render();
    el('authStatus').textContent=message;
    window.dispatchEvent(new CustomEvent('reviewmind-auth',{detail:null}));
  }
  async function credential(response) {
    token=response.credential;el('authStatus').textContent='Signing in…';
    try {
      const result=await ReviewMindAPI.me();
      if (!result.user?.id || !result.user.email || !Number.isFinite(result.user.expires_at)) throw new Error('Sign-in could not be verified.');
      user=result.user;render();
      timer=setTimeout(() => reset('Your sign-in expired. Sign in again.'),Math.max(0,user.expires_at*1000-Date.now()));
      window.dispatchEvent(new CustomEvent('reviewmind-auth',{detail:user}));
    } catch(error) { reset(error.message); }
  }
  async function init() {
    el('retryAuth').hidden=true;
    try {
      const config=await ReviewMindAPI.authConfig();
      if (typeof config.required!=='boolean' || typeof config.client_id!=='string') throw new Error('Sign-in configuration is unavailable. Please retry.');
      required=config.required;
      if (!required) {render();window.dispatchEvent(new CustomEvent('reviewmind-auth',{detail:null}));return;}
      if (!config.client_id) throw new Error('Google sign-in is being set up. Please come back shortly.');
      await new Promise((resolve,reject) => {
        if (window.google?.accounts?.id) return resolve();
        const old=document.getElementById('googleIdentityScript');old?.remove();
        const script=document.createElement('script');script.id='googleIdentityScript';
        script.src='https://accounts.google.com/gsi/client';script.async=true;
        script.onload=resolve;script.onerror=() => reject(new Error('Google sign-in could not load. Check your connection and retry.'));
        document.head.appendChild(script);
      });
      google.accounts.id.initialize({client_id:config.client_id,callback:credential,auto_select:false});
      el('googleSignIn').replaceChildren();
      google.accounts.id.renderButton(el('googleSignIn'),{theme:'outline',size:'large',text:'signin_with'});
      el('authStatus').textContent='Sign-in uses your Google identity. We do not access your Gmail messages.';
    } catch(error) {el('authStatus').textContent=error.message;el('retryAuth').hidden=false;}
    render();
  }
  el('signOut').onclick=() => {window.google?.accounts?.id.disableAutoSelect();reset('You are signed out.');};
  el('retryAuth').onclick=init;
  window.ReviewMindAuth={init,ready:() => true,required:() => required,
    headers:() => token ? {Authorization:'Bearer '+token} : {},expired:() => reset('Your sign-in expired. Sign in again.')};
})();
