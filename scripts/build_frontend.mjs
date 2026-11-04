/* Static-host build step: public API origin only; never embed credentials. */
import {writeFileSync} from 'node:fs';
const value = (process.env.FRONTEND_API_URL || '').replace(/\/$/, '');
if (value) {
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('FRONTEND_API_URL must be a public HTTPS API origin without credentials or query parameters');
  }
}
writeFileSync(new URL('../frontend/assets/config.js', import.meta.url), 'window.REVIEWMIND_CONFIG = ' + JSON.stringify({apiBaseUrl:value}) + ';\n');
