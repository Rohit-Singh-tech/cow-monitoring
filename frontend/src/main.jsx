import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { ConfigProvider } from './context/ConfigContext'

const API_BASE = import.meta.env.MODE === 'production' ? 'https://cow-monitoring01.onrender.com' : '';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ConfigProvider apiBase={API_BASE}>
      <App />
    </ConfigProvider>
  </StrictMode>,
)
