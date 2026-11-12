/* One transport boundary. No mock or fabricated fallback responses. */
(() => {
  const base = (window.REVIEWMIND_CONFIG?.apiBaseUrl || '').replace(/\/$/, '');
  let readyAt = 0, warming = null;
  async function request(path, body, method = 'POST', headers = {}, timeoutMs = 45000) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(base + path, {method, signal: controller.signal,
        headers: {'Content-Type': 'application/json', ...headers},
        ...(body === undefined ? {} : {body: JSON.stringify(body)})});
      let data;
      try { data = await response.json(); } catch { throw new Error('The API returned an invalid response.'); }
      if (!response.ok) {
        const messages = {429:'Too many requests. Wait one minute, then retry.',503:'Analysis or feedback is temporarily unavailable. The service may be waking up. Please retry shortly.',404:'This analysis or feedback has expired or could not be found.',409:'Feedback has already been saved for this analysis.',422:'Check the required fields and input length, then try again.'};
        const providerMessages = {
          not_configured:'Gemini is not configured on the backend. The owner needs to set its API key.',
          authentication_failed:'Gemini rejected the backend key or access. The owner needs to check the key and model permissions.',
          rate_limited:'The assistant reached its request limit. Wait one minute, then retry.',
          provider_rate_limited:'Google reported a Gemini quota or rate limit. Retry later or check the free-tier quota.',
          busy:'The assistant is handling other messages. Retry shortly.',
          timeout:'Gemini took too long to respond. Your message is preserved; you can retry.',
          network_error:'The backend could not reach Gemini. Your message is preserved; retry shortly.',
          blocked:'Gemini could not answer this message. Rephrase it and try again.',
          request_rejected:'Gemini rejected this request. The owner should check model access and configuration.',
          ungrounded_response:'The response included unsupported information and was not shown. Try rephrasing your question.',
          invalid_response:'Gemini returned an unusable response. Your message is preserved; retry shortly.',
          unavailable:'Gemini is temporarily unavailable. Your message is preserved; retry shortly.'};
        const code = data?.error?.code;
        const error = new Error(providerMessages[code] || messages[response.status] || 'The service could not complete this request. Please try again later.');
        error.code = code;
        if (response.status === 404 && path.startsWith('/api/chat')) error.message = 'Chat is not available on this backend yet. Both Render services need the latest phase-3.5/web-integration code.';
        error.status = response.status; throw error;
      }
      if (!data || typeof data !== 'object') throw new Error('The API returned an invalid response.');
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('The service took too long to respond. It may still be waking up. Please retry shortly.');
      if (error instanceof TypeError) throw new Error('Cannot reach the service. Check your connection and try again.');
      throw error;
    } finally { clearTimeout(timeout); }
  }
  function validateAnalysis(data) {
    if (data.type !== 'analysis' || !['negative','neutral','positive'].includes(data.sentiment) ||
        typeof data.model_version !== 'string' || typeof data.request_id !== 'string' ||
        !Array.isArray(data.aspects) || !Array.isArray(data.warnings) || !data.warnings.every(w => typeof w === 'string') ||
        (data.confidence !== null && (!Number.isFinite(data.confidence) || data.confidence < 0 || data.confidence > 1))) {
      throw new Error('The API returned an unsupported analysis format.');
    }
    if (data.aspects.some(a => !a || typeof a.name !== 'string' || !['negative','neutral','positive','unknown','mixed'].includes(a.sentiment))) {
      throw new Error('The API returned an unsupported aspect format.');
    }
    return data;
  }
  window.ReviewMindAPI = {
    chat: async (body, onReady) => {
      // Warm a sleeping service with GET, never automatically retry a billable POST.
      if (Date.now() - readyAt > 60000) {
        if (!warming) warming = request('/api/chat/status', undefined, 'GET', {}, 60000).then(data => {
          if (typeof data.configured !== 'boolean') throw new Error('The chat service returned an invalid status.');
          readyAt = Date.now(); return data;
        }).finally(() => { warming = null; });
        await warming;
      }
      onReady?.();
      const payload = {...body, history:[...body.history]};
      while (payload.history.length && new TextEncoder().encode(JSON.stringify(payload)).length > 15000) {
        const index = payload.history.length > 1 && payload.history[0]?.text.startsWith('Previously stated preferences') ? 1 : 0;
        payload.history.splice(index,1);
      }
      if (new TextEncoder().encode(JSON.stringify(payload)).length > 16000) throw new Error('This message is too large. Please shorten it and retry.');
      const data = await request('/api/chat', payload, 'POST', {}, 30000);
      if (data.type === 'analysis') return validateAnalysis(data);
      if (data.type !== 'chat' || typeof data.reply !== 'string' || !data.reply.trim() || data.reply.length > 6000 ||
          !['built_in','gemini'].includes(data.response_source) || typeof data.provider_status !== 'string') {
        throw new Error('The chat service returned an unsupported response format.');
      }
      return data;
    },
    analyze: async (text, preferences) => validateAnalysis(await request('/api/analyze', {
      text, category: preferences.category || null, language: preferences.language})),
    recommend: async (query, preferences) => {
      const data = await request('/api/recommend', {query, preferences});
      if (data.status !== 'not_available' || data.type !== 'analysis_only' || !Array.isArray(data.products) || data.products.length) {
        throw new Error('Unsupported recommendation response. No product results can be shown.');
      }
      return data;
    },
    feedback: async body => {
      const data = await request('/api/feedback', body);
      if (data.status !== 'stored' || typeof data.feedback_id !== 'string' || typeof data.delete_token !== 'string') {
        throw new Error('The server did not confirm feedback storage.');
      }
      return data;
    },
    deleteFeedback: (id, token) => request('/api/feedback/' + encodeURIComponent(id), undefined, 'DELETE', {'X-Delete-Token': token}),
    health: () => request('/api/health', undefined, 'GET')
  };
})();
