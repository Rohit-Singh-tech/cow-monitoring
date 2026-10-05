// Centralized API configuration for Cow Logger Frontend
// 1. If VITE_API_URL is explicitly set, use it.
// 2. If running locally (localhost / 127.0.0.1), use relative path '' so Vite dev proxy handles requests.
// 3. If deployed on a static hosting provider (e.g. Render static site cow-monitoring-li58.onrender.com),
//    route directly to the live Render backend service.

const getApiBase = () => {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/$/, '');
  }

  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0') {
      return '';
    }
  }

  // Production / Deployed environment fallback to live Render backend
  return 'https://cow-monitoring01.onrender.com';
};

export const API_BASE = getApiBase();
