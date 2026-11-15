import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { lazy, Suspense } from 'react'
import Investigator from './Investigator.jsx'
const Explorer = lazy(() => import('./App.jsx'))

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Suspense fallback={<p>Loading data explorer…</p>}>{window.location.pathname === "/explorer" ? <Explorer /> : <Investigator />}</Suspense>
  </StrictMode>,
)
