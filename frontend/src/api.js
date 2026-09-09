export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://closely-backend.onrender.com';

export async function apiFetch(path, options = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`;
  
  // Ensure credentials are sent (for cookies)
  options.credentials = 'include';
  options.headers = options.headers || {};

  // Automatically attach Content-Type for JSON bodies if not FormData
  if (options.body && !(options.body instanceof FormData)) {
    if (!options.headers['Content-Type'] && !options.headers['content-type']) {
      options.headers['Content-Type'] = 'application/json';
    }
  }

  // Attach stored token as Authorization header (fallback for cross-site cookie blocks)
  const token = localStorage.getItem('closely_token');
  if (token && token !== 'null' && token !== 'undefined' && token !== 'cookie-auth' && token !== '[object Object]') {
    if (!options.headers['Authorization'] && !options.headers['authorization']) {
      options.headers['Authorization'] = `Bearer ${token}`;
    }
  }
  
  const res = await fetch(url, options);
  
  // Broadcast session expiry if API returns 401 Unauthorized
  if (res.status === 401) {
    if (!path.includes('/api/auth/login') && !path.includes('/api/auth/signup')) {
      localStorage.removeItem('closely_token');
      window.dispatchEvent(new CustomEvent('closely_session_expired'));
    }
  }
  
  return res;
}
