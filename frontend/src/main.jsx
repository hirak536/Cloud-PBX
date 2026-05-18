import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import ReduxProvider from '@/providers/ReduxProvider'
import QueryProvider from '@/providers/QueryProvider'
import ThemeSync from '@/components/ThemeSync'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ReduxProvider>
      <QueryProvider>
        <ThemeSync />
        <App />
      </QueryProvider>
    </ReduxProvider>
  </React.StrictMode>
)
