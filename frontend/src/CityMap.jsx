import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { Search, Wind, Pause, Play, RefreshCw } from 'lucide-react'
import './CityMap.css'
import { windVector } from './windVector.mjs'

const INITIAL = { id: 'san-diego', name: 'San Diego', admin1: 'California', country: 'United States', latitude: 32.7157, longitude: -117.1611 }
async function getJSON(url, signal) {
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error('The data service is unavailable. Please try again.')
  return response.json()
}

export default function CityMap() {
  const container = useRef(null), canvas = useRef(null), map = useRef(null)
  const windRef = useRef(null), pausedRef = useRef(false)
  const [city, setCity] = useState(INITIAL), [query, setQuery] = useState('')
  const [results, setResults] = useState([]), [searching, setSearching] = useState(false), [searchError, setSearchError] = useState('')
  const [wind, setWind] = useState(null), [weatherError, setWeatherError] = useState(''), [weatherLoading, setWeatherLoading] = useState(true)
  const [mapError, setMapError] = useState(''), [paused, setPaused] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches)
  const [refresh, setRefresh] = useState(0)
  const searchRequest = useRef(null)
  useEffect(() => { windRef.current = wind }, [wind])
  useEffect(() => { pausedRef.current = paused }, [paused])
  useEffect(() => () => searchRequest.current?.abort(), [])

  useEffect(() => {
    let m, frame, observer
    try {
      m = new maplibregl.Map({ container: container.current, style: 'https://tiles.openfreemap.org/styles/dark', center: [INITIAL.longitude, INITIAL.latitude], zoom: 17, pitch: 65, bearing: -20, maxPitch: 80, attributionControl: false })
      map.current = m
      m.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left')
      m.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right')
      m.on('error', () => setMapError('Some map tiles could not load. Check your connection or try another city.'))
      m.on('idle', () => { if (m.areTilesLoaded()) setMapError('') })
      m.on('load', () => {
        const style = m.getStyle()
        // The dark basemap's light makes extrusion walls nearly black. Give the
        // city explicit directional lighting and a quieter ground plane.
        m.setLight({ anchor: 'viewport', color: '#ffffff', intensity: 0.55, position: [1.5, 210, 45] })
        for (const layer of style.layers) {
          if (layer.type === 'background') m.setPaintProperty(layer.id, 'background-color', '#233237')
          if (layer.type === 'symbol') m.setLayoutProperty(layer.id, 'visibility', 'none')
          if (layer.type === 'fill' && layer['source-layer'] === 'water') m.setPaintProperty(layer.id, 'fill-color', '#153c47')
          if (layer.type === 'fill' && ['landcover', 'park'].includes(layer['source-layer'])) m.setPaintProperty(layer.id, 'fill-color', '#304a3d')
          if (layer.type === 'line' && layer['source-layer'] === 'transportation') m.setPaintProperty(layer.id, 'line-color', '#506368')
        }
        // Keep one opaque building layer so facades read as solid volumes.
        for (const layer of style.layers) if (layer.type === 'fill-extrusion') m.removeLayer(layer.id)
        const source = style.layers.find(layer => layer['source-layer'] === 'building')?.source || Object.keys(style.sources).find(key => key === 'openmaptiles')
        if (!source) { setMapError('3D building data is unavailable in this basemap.'); return }
        const label = style.layers.find(layer => layer.type === 'symbol' && layer.layout?.['text-field'])?.id
        m.addLayer({ id: 'askgaia-buildings', type: 'fill-extrusion', source, 'source-layer': 'building', minzoom: 13,
          paint: { 'fill-extrusion-color': '#d0dcd9', 'fill-extrusion-height': ['case', ['>', ['coalesce', ['get', 'render_height'], 0], 0], ['get', 'render_height'], 8], 'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0], 'fill-extrusion-opacity': 1, 'fill-extrusion-vertical-gradient': true } }, label)
      })
      const ctx = canvas.current.getContext('2d')
      if (!ctx) throw new Error('Canvas unavailable')
      let width = 1, height = 1, previous = 0, particles = []
      function seed() {
        const point = m.unproject([Math.random() * width, Math.random() * height])
        return { lng: point.lng, lat: point.lat, age: Math.random() * 160 }
      }
      function resize() {
        m.resize(); width = container.current.clientWidth; height = container.current.clientHeight
        const ratio = Math.min(devicePixelRatio || 1, 2)
        canvas.current.width = width * ratio; canvas.current.height = height * ratio
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
        particles = Array.from({ length: width < 650 ? 140 : 320 }, seed)
      }
      observer = new ResizeObserver(resize); observer.observe(container.current); resize()
      function reset() { ctx.clearRect(0, 0, width, height); particles = particles.map(seed) }
      m.on('movestart', reset)
      function animate(time) {
        frame = requestAnimationFrame(animate)
        const dt = previous ? Math.min((time - previous) / 1000, 0.05) : 0; previous = time
        ctx.clearRect(0, 0, width, height)
        const w = windRef.current
        if (!w || document.hidden || w.speed < 0.1) return
        // Meteorological direction is where wind comes FROM; transport is opposite.
        const { east, north } = windVector(w.direction, w.speed)
        const step = pausedRef.current ? 0 : dt
        ctx.strokeStyle = '#a6ffe0'; ctx.lineWidth = 1.15
        particles.forEach((p, i) => {
          const metresPerDegreeLng = 111320 * Math.max(0.02, Math.cos(p.lat * Math.PI / 180))
          p.lng += east * step * 12 / metresPerDegreeLng; p.lat += north * step * 12 / 111320; p.age += step * 25
          const a = m.project([p.lng, p.lat])
          if (p.age > 180 || a.x < -30 || a.y < -30 || a.x > width + 30 || a.y > height + 30) { particles[i] = { ...seed(), age: 0 }; return }
          const b = m.project([p.lng - east * 5 / metresPerDegreeLng, p.lat - north * 5 / 111320])
          ctx.globalAlpha = Math.min(0.7, p.age / 25, (180 - p.age) / 25)
          ctx.beginPath(); ctx.moveTo(b.x, b.y); ctx.lineTo(a.x, a.y); ctx.stroke()
        })
        ctx.globalAlpha = 1
      }
      frame = requestAnimationFrame(animate)
    } catch { setMapError('This browser could not initialize the 3D map. Try a browser with WebGL enabled.') }
    return () => { cancelAnimationFrame(frame); observer?.disconnect(); m?.remove(); map.current = null }
  }, [])

  useEffect(() => {
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches
    map.current?.flyTo({ center: [city.longitude, city.latitude], zoom: 17, pitch: 65, duration: reduced ? 0 : 1600 })
  }, [city])
  useEffect(() => {
    const controller = new AbortController()
    setWind(null); windRef.current = null; setWeatherError(''); setWeatherLoading(true)
    const params = new URLSearchParams({ latitude: city.latitude, longitude: city.longitude, current: 'wind_speed_10m,wind_direction_10m', wind_speed_unit: 'ms', timezone: 'UTC' })
    getJSON('https://api.open-meteo.com/v1/forecast?' + params, controller.signal).then(data => {
      const current = data.current
      if (!Number.isFinite(current?.wind_speed_10m) || !Number.isFinite(current?.wind_direction_10m)) throw new Error('Wind data is unavailable for this location.')
      setWind({ speed: current.wind_speed_10m, direction: current.wind_direction_10m, time: current.time })
    }).catch(e => { if (e.name !== 'AbortError') setWeatherError(e.message) }).finally(() => { if (!controller.signal.aborted) setWeatherLoading(false) })
    return () => controller.abort()
  }, [city, refresh])

  async function search(e) {
    e.preventDefault(); searchRequest.current?.abort()
    const controller = new AbortController(); searchRequest.current = controller
    setSearching(true); setSearchError(''); setResults([])
    try {
      const data = await getJSON('https://geocoding-api.open-meteo.com/v1/search?' + new URLSearchParams({ name: query.trim(), count: 6, language: 'en', format: 'json' }), controller.signal)
      if (controller.signal.aborted) return
      const found = (data.results || []).filter(c => Number.isFinite(c.latitude) && Number.isFinite(c.longitude))
      setResults(found); if (!found.length) setSearchError('No matching cities. Try a nearby city or another spelling.')
    } catch (e) { if (e.name !== 'AbortError') setSearchError(e.message) }
    finally { if (!controller.signal.aborted) setSearching(false) }
  }
  return <div className="gaia-city-map">
    <div ref={container} className="gaia-city-canvas" aria-label={`Interactive 3D map of ${city.name}`} />
    <canvas ref={canvas} className="gaia-wind-canvas" aria-hidden="true" />
    <section className="gaia-city-search" aria-label="Find a city">
      <form onSubmit={search}><Search size={18}/><input aria-label="City name" placeholder="Enter a city…" value={query} onChange={e => setQuery(e.target.value)} minLength={2} maxLength={100} required/><button disabled={searching}>{searching ? 'Searching…' : 'Explore'}</button></form>
      {searchError && <p role="alert">{searchError}</p>}
      {results.length > 0 && <div className="gaia-city-results">{results.map(c => <button key={c.id} onClick={() => { setCity(c); setResults([]); setQuery(c.name) }}><strong>{c.name}</strong><small>{[c.admin1, c.country].filter(Boolean).join(', ')}</small></button>)}</div>}
    </section>
    <details className="geo-wind-panel gaia-city-wind">
      <summary><Wind size={16}/><span>{city.name}</span><strong>{weatherLoading ? 'Loading…' : weatherError ? 'Wind unavailable' : wind ? `${wind.speed.toFixed(1)} m/s · ${Math.round(wind.direction)}°` : 'No wind data'}</strong><span className="gaia-disclosure">⌄</span></summary><div className="gaia-wind-details">
      <h2>Wind conditions</h2><p className="gaia-city-region">{[city.admin1, city.country].filter(Boolean).join(', ')}</p>
      {weatherLoading ? <p role="status">Loading wind…</p> : weatherError ? <p role="alert">{weatherError}</p> : wind && <><div className="gaia-wind-values"><strong>{wind.speed.toFixed(1)}<small> m/s</small></strong><span>from {Math.round(wind.direction)}°</span></div><p className="gaia-wind-time">Weather model · {wind.time.replace('T', ' ')} UTC</p></>}
      <button className="gaia-reset-camera" onClick={() => map.current?.flyTo({ center: [city.longitude, city.latitude], zoom: 17, pitch: 65, bearing: -20, duration: matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 900 })}>Reset 3D view</button>
      <div className="geo-scene-actions"><button onClick={() => setPaused(!paused)}>{paused ? <Play size={12}/> : <Pause size={12}/>} {paused ? 'Play wind' : 'Pause wind'}</button><button disabled={weatherLoading} onClick={() => setRefresh(x => x + 1)}><RefreshCw size={12}/> Refresh</button></div>
      <p className="geo-scene-disclaimer">10 m wind from <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a>. Trails animate at 12× speed using one city-level wind sample. No building-level airflow or exposure calculation.</p>
    </div></details>
    {mapError && <p className="gaia-map-error" role="alert">{mapError}</p>}
    <details className="gaia-city-note"><summary>Map info</summary><p>Drag to pan · right-drag to orbit · scroll to zoom</p><p>Mapped building footprints; heights and coverage vary. Missing or zero heights use an 8 m fallback. Wind is a city-level model, not a street-level measurement.</p></details>
  </div>
}
