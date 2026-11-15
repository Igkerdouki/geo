import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js'
import { TilesRenderer, GlobeControls } from '3d-tiles-renderer'
import {
  GoogleCloudAuthPlugin, TileCompressionPlugin, UpdateOnChangePlugin,
  UnloadTilesPlugin, TilesFadePlugin, GLTFExtensionsPlugin,
} from '3d-tiles-renderer/plugins'
import './EarthTour.css'

const KEY = import.meta.env.VITE_GOOGLE_MAPS_KEY
const D2R = Math.PI / 180

// Stops chosen from our own PUR data (2020-2024): highest totals and fumigant hotspots.
const STOPS = [
  { id: 'earth', label: 'Earth', lat: 25, lon: -120, height: 14_000_000, tilt: 0 },
  { id: 'ca', label: 'California', lat: 36.8, lon: -119.4, height: 1_300_000, tilt: 0,
    note: '11 years of recorded pesticide use, every county' },
  { id: 'fresno', label: 'Fresno County', lat: 36.62, lon: -119.75, height: 90_000, tilt: 35,
    note: '#1 in California: 123 M lbs applied 2020–2024' },
  { id: 'arvin', label: 'Arvin · Lamont', lat: 35.205, lon: -118.83, height: 2_600, tilt: 55,
    note: 'Kern County fumigant hotspot; 2002 Arvin drift sickened 252 people' },
  { id: 'salinas', label: 'Salinas · Alisal High', lat: 36.6835, lon: -121.6004, height: 1_400, tilt: 58,
    note: '1.55 M lbs within 1.25 km (2020–2024), led by chloropicrin' },
  { id: 'oxnard', label: 'Oxnard Plain', lat: 34.22, lon: -119.242, height: 2_200, tilt: 55,
    note: 'The single most fumigated square mile in the state' },
]

export default function EarthTour() {
  const mount = useRef(null)
  const api = useRef({})
  const [active, setActive] = useState('earth')
  const [credits, setCredits] = useState('')
  const [moving, setMoving] = useState(false)

  useEffect(() => {
    if (!KEY) return
    const host = mount.current
    const renderer = new THREE.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true })
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
    renderer.setClearColor(0x02040a)
    host.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(50, 1, 1, 1.6e8)

    // Stars far behind the planet
    const starGeo = new THREE.BufferGeometry()
    const pts = new Float32Array(6000 * 3)
    for (let i = 0; i < pts.length; i += 3) {
      const v = new THREE.Vector3().randomDirection().multiplyScalar(9e7)
      pts.set([v.x, v.y, v.z], i)
    }
    starGeo.setAttribute('position', new THREE.BufferAttribute(pts, 3))
    scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 1.4, sizeAttenuation: false })))

    const tiles = new TilesRenderer()
    tiles.registerPlugin(new GoogleCloudAuthPlugin({ apiToken: KEY, autoRefreshToken: true }))
    tiles.registerPlugin(new TileCompressionPlugin())
    tiles.registerPlugin(new UpdateOnChangePlugin())
    tiles.registerPlugin(new UnloadTilesPlugin())
    tiles.registerPlugin(new TilesFadePlugin())
    tiles.registerPlugin(new GLTFExtensionsPlugin({
      dracoLoader: new DRACOLoader().setDecoderPath('https://unpkg.com/three@0.170.0/examples/jsm/libs/draco/gltf/'),
    }))
    tiles.group.rotation.x = -Math.PI / 2 // tiles are Z-up, three.js is Y-up
    scene.add(tiles.group)

    const controls = new GlobeControls(scene, camera, renderer.domElement)
    controls.setEllipsoid(tiles.ellipsoid, tiles.group)
    controls.enableDamping = true

    const ell = tiles.ellipsoid
    const toWorld = (lat, lon, h) => ell.getCartographicToPosition(lat * D2R, lon * D2R, h, new THREE.Vector3())
      .applyMatrix4(tiles.group.matrixWorld)

    // Camera pose for a stop: above and south of the target, looking at it
    function pose(s) {
      tiles.group.updateMatrixWorld()
      const back = s.tilt ? (s.height / Math.tan((90 - s.tilt) * D2R)) / 111_000 : 0
      const camPos = toWorld(s.lat - back, s.lon, s.height)
      const target = toWorld(s.lat, s.lon, 0)
      return { camPos, target }
    }
    function place(s) {
      const { camPos, target } = pose(s)
      camera.position.copy(camPos)
      camera.up.copy(camPos).normalize()
      camera.lookAt(target)
    }

    let flight = null
    let idle = true
    let orbitLon = STOPS[0].lon
    renderer.domElement.addEventListener('pointerdown', () => { idle = false })

    api.current.fly = (id) => {
      const to = STOPS.find(s => s.id === id)
      const cart = ell.getPositionToCartographic(
        camera.position.clone().applyMatrix4(new THREE.Matrix4().copy(tiles.group.matrixWorld).invert()), {})
      const from = { lat: cart.lat / D2R, lon: cart.lon / D2R, height: cart.height, tilt: 0 }
      flight = { from, to, t0: performance.now(), dur: id === 'earth' || from.height > 2e6 ? 5200 : 3800 }
      idle = id === 'earth'
      controls.enabled = false
      setMoving(true)
      setActive(id)
    }

    const ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
    function stepFlight(now) {
      const { from, to, t0, dur } = flight
      const t = Math.min(1, (now - t0) / dur), e = ease(t)
      const arc = Math.sin(Math.PI * t) * Math.min(Math.max(from.height, to.height) * 0.6, 4e6)
      const s = {
        lat: from.lat + (to.lat - from.lat) * e,
        lon: from.lon + (to.lon - from.lon) * e,
        height: Math.exp(Math.log(Math.max(from.height, 300)) * (1 - e) + Math.log(to.height) * e) + arc,
        tilt: (to.tilt || 0) * e,
      }
      place(s)
      if (t >= 1) { flight = null; controls.enabled = true; setMoving(false); orbitLon = to.lon }
    }

    function resize() {
      const w = host.clientWidth, h = host.clientHeight
      renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix()
    }
    addEventListener('resize', resize); resize()
    tiles.group.updateMatrixWorld()
    place(STOPS[0])

    let raf, lastCredits = ''
    const loop = (now) => {
      raf = requestAnimationFrame(loop)
      if (flight) stepFlight(now)
      else if (idle && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
        orbitLon += 0.02; place({ ...STOPS[0], lon: orbitLon })
      } else controls.update()
      camera.updateMatrixWorld()
      tiles.setCamera(camera)
      tiles.setResolutionFromRenderer(camera, renderer)
      tiles.update()
      renderer.render(scene, camera)
      const c = tiles.getAttributions().map(a => a.value).filter(v => typeof v === 'string').join(' · ')
      if (c !== lastCredits) { lastCredits = c; setCredits(c) }
    }
    raf = requestAnimationFrame(loop)

    return () => {
      cancelAnimationFrame(raf); removeEventListener('resize', resize)
      controls.dispose?.(); tiles.dispose(); renderer.dispose(); host.removeChild(renderer.domElement)
    }
  }, [])

  const stop = STOPS.find(s => s.id === active)
  return (
    <div className="earth">
      <div className="earth-canvas" ref={mount} />
      {!KEY && (
        <div className="earth-missing">
          <h2>Add a Google Maps key to see photorealistic 3D</h2>
          <p>Put <code>VITE_GOOGLE_MAPS_KEY=…</code> in <code>frontend/.env.local</code> (Map Tiles API enabled), then restart <code>npm run dev</code>.</p>
        </div>
      )}
      <header className="earth-head">
        <span className="earth-brand">askgaia</span>
        <span className="earth-tag">Earth, understood.</span>
      </header>
      <nav className="earth-stops" aria-label="Fly to">
        {STOPS.map(s => (
          <button key={s.id} aria-pressed={active === s.id} disabled={moving || !KEY}
            onClick={() => api.current.fly?.(s.id)}>{s.label}</button>
        ))}
      </nav>
      {stop?.note && <p className="earth-note">{stop.note}</p>}
      <footer className="earth-credits">
        <img src="https://www.gstatic.com/images/branding/googlelogo/svg/googlelogo_clr_74x24px.svg" alt="Google" height="16" />
        <span>{credits}</span>
      </footer>
    </div>
  )
}
