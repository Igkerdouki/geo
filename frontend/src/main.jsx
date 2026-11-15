import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { lazy, Suspense } from 'react'
import Investigator from './Investigator.jsx'
const Explorer = lazy(() => import('./App.jsx'))
const EarthTour = lazy(() => import('./EarthTour.jsx'))

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Suspense fallback={<p>Loading data explorer…</p>}>{window.location.pathname === "/explorer" ? <Explorer /> : window.location.pathname === "/earth" ? <EarthTour /> : <Investigator />}</Suspense>
  </StrictMode>,
)
