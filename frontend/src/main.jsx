import '../public/gaia-widget.mjs'
import { Component, StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { lazy, Suspense } from 'react'
const Investigator = lazy(() => import('./Investigator.jsx'))
const Explorer = lazy(() => import('./App.jsx'))
const EarthTour = lazy(() => import('./EarthTour.jsx'))

class AppBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(error) { return { error } }
  render() {
    if (this.state.error) return <div role="alert" style={{padding:32,color:'#fff',background:'#122522',minHeight:'100vh'}}><h1>AskGaia could not load</h1><p>{this.state.error.message}</p><button onClick={()=>window.location.reload()}>Reload workspace</button></div>
    return this.props.children
  }
}

if (window.location.pathname === '/') window.location.replace('/home.html' + window.location.search + window.location.hash)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AppBoundary><Suspense fallback={<p>Loading workspace…</p>}>{window.location.pathname === "/explorer" ? <Explorer /> : window.location.pathname === "/investigate" ? <Investigator /> : <EarthTour />}</Suspense></AppBoundary>
  </StrictMode>,
)
