// Centralized API configuration for Cow Logger Frontend
// Uses VITE_API_URL environment variable if provided, otherwise defaults to relative path ('')
// Relative path ('') works seamlessly for:
// 1. Local Vite dev server (proxies /api to http://127.0.0.1:8000)
// 2. Render static deployment (rewrites /api/* to backend URL with zero CORS preflight delay)
export const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
