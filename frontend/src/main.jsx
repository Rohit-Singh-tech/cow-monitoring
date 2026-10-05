import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { ConfigProvider } from './context/ConfigContext'

import { API_BASE } from './config/api'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ConfigProvider apiBase={API_BASE}>
      <App />
    </ConfigProvider>
  </StrictMode>,
)
