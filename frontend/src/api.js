export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export async function apiFetch(path, options = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE_URL}${path}`;
  
  // Ensure credentials are sent (for cookies)
  options.credentials = 'include';
  
  return fetch(url, options);
}
