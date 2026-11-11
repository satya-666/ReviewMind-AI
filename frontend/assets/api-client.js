/* One transport boundary. No mock or fabricated fallback responses. */
(() => {
  const base = (window.REVIEWMIND_CONFIG?.apiBaseUrl || '').replace(/\/$/, '');
  async function request(path, body, method = 'POST', headers = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 45000);
    try {
      const response = await fetch(base + path, {method, signal: controller.signal,
        headers: {'Content-Type': 'application/json', ...headers},
        ...(body === undefined ? {} : {body: JSON.stringify(body)})});
      let data;
      try { data = await response.json(); } catch { throw new Error('The API returned an invalid response.'); }
      if (!response.ok) {
        const messages = {429:'Too many requests. Wait one minute, then retry.',503:'Analysis or feedback is temporarily unavailable. The service may be waking up. Please retry shortly.',404:'This analysis or feedback has expired or could not be found.',409:'Feedback has already been saved for this analysis.',422:'Check the required fields and input length, then try again.'};
        const error = new Error(messages[response.status] || 'The service could not complete this request. Please try again later.');
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
