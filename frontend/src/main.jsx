import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { lazy, Suspense } from 'react'
import Investigator from './Investigator.jsx'
const Explorer = lazy(() => import('./App.jsx'))
const EarthTour = lazy(() => import('./EarthTour.jsx'))

// The landing page is /home.html; the bare /earth page is only used embedded or via deep links
const qs = new URLSearchParams(location.search)
if (location.pathname === '/earth' && !qs.has('embed') && !qs.has('stop') && !qs.has('q')) location.replace('/home.html')

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Suspense fallback={<p>Loading data explorer…</p>}>{window.location.pathname === "/explorer" ? <Explorer /> : window.location.pathname === "/earth" ? <EarthTour /> : <Investigator />}</Suspense>
  </StrictMode>,
)
