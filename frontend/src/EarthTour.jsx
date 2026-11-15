import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js'
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js'
import { VectorTile, classifyRings } from '@mapbox/vector-tile'
import { PbfReader } from 'pbf'
import { TilesRenderer, GlobeControls } from '3d-tiles-renderer'
import {
  GoogleCloudAuthPlugin, TileCompressionPlugin, UpdateOnChangePlugin,
  UnloadTilesPlugin, TilesFadePlugin, GLTFExtensionsPlugin,
} from '3d-tiles-renderer/plugins'
import './EarthTour.css'

const KEY = import.meta.env.VITE_GOOGLE_MAPS_KEY
const D2R = Math.PI / 180
const M = 111_320

// Tour stops. Stops with `radius` pull real treated sections from /api/spatial/sections.
const STOPS = [
  { id: 'earth', label: 'Earth', lat: 22, lon: -118, height: 11_500_000, tilt: 0 },
  { id: 'ca', label: 'California', lat: 36.8, lon: -119.4, height: 900_000, tilt: 0,
    title: 'California', note: '11 years of recorded pesticide use, every county.' },
  { id: 'fresno', label: 'Fresno County', lat: 36.7378, lon: -119.7871, height: 520, tilt: 68, radius: 6,
    title: 'Fresno County', note: 'Downtown Fresno. The county applied the most pesticide in California: 123 M lbs, 2020–2024.' },
  { id: 'arvin', label: 'Arvin · Lamont', lat: 35.2091, lon: -118.8284, height: 560, tilt: 68, radius: 4, plume: true,
    title: 'Arvin, Kern County', target: 'Arvin town centre',
    note: 'Fumigant hotspot. A 2002 metam-sodium drift here sickened 252 people.' },
  { id: 'salinas', label: 'Salinas · Alisal High', lat: 36.6835, lon: -121.6004, height: 520, tilt: 68, radius: 4, plume: true,
    title: 'Alisal High School, Salinas', target: 'Alisal High School',
    note: 'Salinas Valley strawberry and lettuce fields, heavily fumigated.' },
  { id: 'oxnard', label: 'Oxnard Plain', lat: 34.205, lon: -119.205, height: 560, tilt: 68, radius: 5, plume: true,
    title: 'Oxnard Plain, Ventura County', target: 'Oxnard homes',
    note: 'Home to the single most fumigated square mile in California.' },
]

// Briggs rural dispersion, same model as the backend run_plume tool
const SIG = {
  A: [0.22, x => 0.20 * x], B: [0.16, x => 0.12 * x], C: [0.11, x => 0.08 * x / Math.sqrt(1 + 0.0002 * x)],
  D: [0.08, x => 0.06 * x / Math.sqrt(1 + 0.0015 * x)], E: [0.06, x => 0.03 * x / (1 + 0.0003 * x)],
  F: [0.04, x => 0.016 * x / (1 + 0.0003 * x)],
}
function conc(dx, dy, w) { // metres east/north of the source
  const to = (w.dir + 180) * D2R, ex = Math.sin(to), ny = Math.cos(to)
  const x = dx * ex + dy * ny, y = -dx * ny + dy * ex
  if (x <= 1) return 0
  const [ay, szf] = SIG[w.cls], u = Math.max(w.speed, 0.5)
  const sy = ay * x / Math.sqrt(1 + 0.0001 * x), sz = Math.max(szf(x), 0.5)
  return Math.exp(-y * y / (2 * sy * sy)) * 2 * Math.exp(-4 / (2 * sz * sz)) / (2 * Math.PI * u * sy * sz)
}
const RAMP = [[0, [46, 168, 110]], [0.35, [130, 222, 150]], [0.6, [241, 214, 120]], [0.8, [245, 150, 70]], [1, [229, 62, 62]]]
const ramp = v => { for (let i = 1; i < RAMP.length; i++) if (v <= RAMP[i][0]) { const [a, ca] = RAMP[i - 1], [b, cb] = RAMP[i], f = (v - a) / (b - a); return ca.map((c, k) => c + (cb[k] - c) * f) } return RAMP[4][1] }
// Building footprints with heights from OpenStreetMap, served as vector tiles by OpenFreeMap
const OFM = 'https://tiles.openfreemap.org/planet/20261101_080013_pt/{z}/{x}/{y}.pbf'
const tileOf = (lat, lon, z) => { const n = 2 ** z, x = (lon + 180) / 360 * n, s = Math.log(Math.tan(Math.PI / 4 + lat * D2R / 2)); return [Math.floor(x), Math.floor((1 - s / Math.PI) / 2 * n)] }
const tileToLonLat = (z, x, y, px, py, ext) => { const n = 2 ** z, lon = (x + px / ext) / n * 360 - 180, yy = Math.PI * (1 - 2 * (y + py / ext) / n); return [lon, Math.atan(Math.sinh(yy)) / D2R] }
async function fetchBuildings(lat, lon, radiusM) {
  const z = 14, [cx, cy] = tileOf(lat, lon, z), out = []
  const jobs = []
  for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) jobs.push([cx + dx, cy + dy])
  await Promise.all(jobs.map(async ([x, y]) => {
    try {
      const buf = await (await fetch(OFM.replace('{z}', z).replace('{x}', x).replace('{y}', y))).arrayBuffer()
      const layer = new VectorTile(new PbfReader(buf)).layers.building
      if (!layer) return
      for (let i = 0; i < layer.length; i++) {
        const f = layer.feature(i)
        if (f.type !== 3) continue
        const h = Math.max(3, +f.properties.render_height || 6), base = +f.properties.render_min_height || 0
        for (const poly of classifyRings(f.loadGeometry())) {
          const rings = poly.map(r => r.map(p => tileToLonLat(z, x, y, p.x, p.y, layer.extent)))
          const [clon, clat] = rings[0][0]
          if (Math.hypot((clon - lon) * M * Math.cos(lat * D2R), (clat - lat) * M) > radiusM) continue
          out.push({ rings, h, base })
        }
      }
    } catch { /* a missing tile just means fewer buildings */ }
  }))
  return out
}

const fmt = n => n >= 1e6 ? (n / 1e6).toFixed(2) + ' M' : n >= 1e3 ? Math.round(n / 1e3) + ' k' : String(n)

export default function EarthTour() {
  const mount = useRef(null), api = useRef({}), tagRef = useRef(null)
  const [active, setActive] = useState('earth')
  const [custom, setCustom] = useState(null)
  const [credits, setCredits] = useState('')
  const [moving, setMoving] = useState(false)
  const [data, setData] = useState(null)
  const [wind, setWind] = useState({ dir: 300, speed: 4, cls: 'D' })
  const [windSrc, setWindSrc] = useState('Scenario')
  const [schoolLevel, setSchoolLevel] = useState(null)
  const [query, setQuery] = useState('')
  const [searchMsg, setSearchMsg] = useState('')
  const [count, setCount] = useState(0)
  const [buildingCount, setBuildingCount] = useState(0)
  useEffect(() => { // count up to the recorded total once on load
    const TOTAL = 1_919_790_000, t0 = performance.now(), dur = 2600
    let r; const step = n => { const k = Math.min(1, (n - t0) / dur); setCount(Math.round(TOTAL * (1 - Math.pow(1 - k, 3)))); if (k < 1) r = requestAnimationFrame(step) }
    r = requestAnimationFrame(step); return () => cancelAnimationFrame(r)
  }, [])

  useEffect(() => {
    if (!KEY) return
    const host = mount.current
    const renderer = new THREE.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true })
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5))
    renderer.setClearColor(0x050807)
    host.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(50, 1, 1, 1.6e8)

    const starGeo = new THREE.BufferGeometry(), sp = new Float32Array(5000 * 3)
    for (let i = 0; i < sp.length; i += 3) { const v = new THREE.Vector3().randomDirection().multiplyScalar(9e7); sp.set([v.x, v.y, v.z], i) }
    starGeo.setAttribute('position', new THREE.BufferAttribute(sp, 3))
    scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 1.2, sizeAttenuation: false, transparent: true, opacity: 0.75 })))

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
    const DETAIL = 6, MOVING = 40
    tiles.errorTarget = DETAIL
    tiles.downloadQueue.maxJobsPerOrigin = 40
    tiles.parseQueue.maxJobs = 8
    tiles.lruCache.maxBytesSize = 600 * 1024 * 1024
    scene.add(tiles.group)

    const controls = new GlobeControls(scene, camera, renderer.domElement)
    controls.setEllipsoid(tiles.ellipsoid, tiles.group)
    controls.enableDamping = true
    controls.minDistance = 8

    const ell = tiles.ellipsoid
    const toWorld = (lat, lon, h) => ell.getCartographicToPosition(lat * D2R, lon * D2R, h, new THREE.Vector3()).applyMatrix4(tiles.group.matrixWorld)

    function place(s) {
      tiles.group.updateMatrixWorld()
      const back = s.tilt ? (s.height / Math.tan((90 - s.tilt) * D2R)) / M : 0
      camera.position.copy(toWorld(s.lat - back, s.lon, s.height))
      camera.up.set(0, 1, 0) // north is +Y after the -90° X rotation
      camera.lookAt(toWorld(s.lat, s.lon, 0))
    }

    // ---------- data overlay in a local East-North-Up frame at the stop ----------
    const overlay = new THREE.Group(); overlay.matrixAutoUpdate = false; scene.add(overlay)
    let site = null
    const NP = 1400
    const pPos = new Float32Array(NP * 6), pCol = new Float32Array(NP * 6)
    const pGeo = new THREE.BufferGeometry()
    pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3)); pGeo.setAttribute('color', new THREE.BufferAttribute(pCol, 3))
    const particles = new THREE.LineSegments(pGeo, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthTest: false, depthWrite: false }))
    particles.renderOrder = 3; particles.frustumCulled = false
    const P = []
    const SZ = 96, EXT = 7000, plumeData = new Uint8Array(SZ * SZ * 4)
    const plumeTex = new THREE.DataTexture(plumeData, SZ, SZ); plumeTex.magFilter = plumeTex.minFilter = THREE.LinearFilter
    const plume = new THREE.Mesh(new THREE.PlaneGeometry(EXT, EXT), new THREE.MeshBasicMaterial({ map: plumeTex, transparent: true, depthTest: false, depthWrite: false }))
    plume.renderOrder = 2
    let windNow = { dir: 300, speed: 4, cls: 'D' }
    let blds = null // { mesh, colors, items:[{start,count,x,y}] }
    const bldMat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85, metalness: 0, transparent: true, opacity: 0.96 })
    const hemi = new THREE.HemisphereLight(0xffffff, 0x334433, 1.6), sun = new THREE.DirectionalLight(0xffffff, 1.6)
    sun.position.set(-400, -300, 900)

    const local = (lat, lon) => [(lon - site.stop.lon) * M * Math.cos(site.stop.lat * D2R), (lat - site.stop.lat) * M]

    function groundHeight(lat, lon) {
      const from = toWorld(lat, lon, 4000), to = toWorld(lat, lon, -200)
      const ray = new THREE.Raycaster(from, to.clone().sub(from).normalize(), 0, 5000)
      const hit = ray.intersectObject(tiles.group, true)[0]
      if (!hit) return null
      const inv = new THREE.Matrix4().copy(tiles.group.matrixWorld).invert()
      return ell.getPositionToCartographic(hit.point.clone().applyMatrix4(inv), {}).height
    }

    function paintPlume() {
      if (!site?.source) return
      const [sx, sy] = local(site.source.lat, site.source.lon)
      plume.position.set(sx, sy, site.ground + 6)
      const ref = conc(150, 0, { ...windNow, dir: 270 }) || 1e-9 // 150 m straight downwind = 1.0
      for (let j = 0; j < SZ; j++) for (let i = 0; i < SZ; i++) {
        const dx = (i / (SZ - 1) - 0.5) * EXT, dy = (j / (SZ - 1) - 0.5) * EXT
        let v = conc(dx, dy, windNow) / ref
        v = v > 0 ? Math.max(0, Math.min(1, 1 + Math.log10(v) / 2.6)) : 0
        const o = (j * SZ + i) * 4, [r, g, b] = ramp(v)
        plumeData[o] = r; plumeData[o + 1] = g; plumeData[o + 2] = b; plumeData[o + 3] = v < 0.03 ? 0 : 40 + v * 170
      }
      plumeTex.needsUpdate = true
      if (blds) { // colour every modelled building by the drift reaching it
        const c = blds.colors.array
        for (const b of blds.items) {
          let v = conc(b.x - sx, b.y - sy, windNow) / ref
          v = v > 0 ? Math.max(0, Math.min(1, 1 + Math.log10(v) / 2.6)) : 0
          const [r, g, bb] = v < 0.05 ? [226, 232, 228] : ramp(v)
          for (let i = b.start; i < b.start + b.count; i++) { c[i * 3] = r / 255; c[i * 3 + 1] = g / 255; c[i * 3 + 2] = bb / 255 }
        }
        blds.colors.needsUpdate = true
      }
      const [tx, ty] = local(site.stop.lat, site.stop.lon)
      const v = conc(tx - sx, ty - sy, windNow) / ref
      setSchoolLevel(v > 0 ? Math.max(0, Math.min(1, 1 + Math.log10(v) / 2.6)) : 0)
    }

    function spawn(p, init) {
      p.x = (Math.random() - 0.5) * 900; p.y = (Math.random() - 0.5) * 900; p.z = 5 + Math.random() * 25
      p.age = init ? Math.random() * 300 : 0; p.px = p.x; p.py = p.y; p.pz = p.z; p.seed = Math.random() * 100
    }
    for (let i = 0; i < NP; i++) { const p = {}; spawn(p, true); P.push(p) }

    function stepParticles(t) {
      if (!site?.source) return
      const [sx, sy] = local(site.source.lat, site.source.lon)
      const to = (windNow.dir + 180) * D2R, ex = Math.sin(to), ny = Math.cos(to)
      const spd = 2 + windNow.speed * 1.6, spread = { A: 2, B: 1.6, C: 1.25, D: 1, E: 0.7, F: 0.5 }[windNow.cls]
      let k = 0
      for (const p of P) {
        p.px = p.x; p.py = p.y; p.pz = p.z
        const n = Math.sin(p.seed + t * 0.9 + p.x * 0.004) * spread
        p.x += ex * spd - ny * n * 1.2; p.y += ny * spd + ex * n * 1.2
        p.z += Math.sin(p.seed + t) * 0.15 * spread
        if (++p.age > 320) spawn(p, false)
        const life = Math.min(1, p.age / 25) * Math.max(0, 1 - p.age / 320)
        const [r, g, b] = ramp(Math.max(0, 0.95 - p.age / 340))
        const gz = site.ground + 8
        pPos.set([sx + p.px, sy + p.py, gz + p.pz, sx + p.x, sy + p.y, gz + p.z], k * 6)
        pCol.set([r / 255 * life * 0.25, g / 255 * life * 0.25, b / 255 * life * 0.25, r / 255 * life, g / 255 * life, b / 255 * life], k * 6)
        k++
      }
      pGeo.attributes.position.needsUpdate = pGeo.attributes.color.needsUpdate = true
    }

    function clearOverlay() { overlay.clear(); if (blds) { blds.mesh.geometry.dispose(); blds = null } site = null; setSchoolLevel(null); setBuildingCount(0) }

    async function buildOverlay(stop) {
      clearOverlay()
      if (!stop.radius) return
      let json
      try { json = await (await fetch(`/api/spatial/sections?lat=${stop.lat}&lon=${stop.lon}&radius_km=${stop.radius}&limit=80`)).json() }
      catch { json = { sections: [] } }
      const secs = json.sections || []
      const source = stop.plume ? [...secs].sort((a, b) => (b.fumigant_lbs || b.lbs * 0.01) - (a.fumigant_lbs || a.lbs * 0.01))[0] : null
      setData({ stop, secs, source, total: secs.reduce((s, x) => s + x.lbs, 0), fum: secs.reduce((s, x) => s + x.fumigant_lbs, 0) })
      await new Promise(r => setTimeout(r, 900)) // let ground tiles settle before sampling height
      const enu = new THREE.Matrix4()
      ell.getEastNorthUpFrame(stop.lat * D2R, stop.lon * D2R, 0, enu)
      overlay.matrix.copy(tiles.group.matrixWorld).multiply(enu); overlay.matrixWorldNeedsUpdate = true
      const ground = groundHeight(stop.lat, stop.lon) ?? 0
      site = { stop, ground, source }
      overlay.add(hemi); overlay.add(sun)
      fetchBuildings(stop.lat, stop.lon, 1300).then(list => {
        if (site?.stop !== stop || !list.length) return
        const geos = [], items = []
        let offset = 0
        for (const b of list) {
          const shape = new THREE.Shape(b.rings[0].map(([lo, la]) => new THREE.Vector2(...local(la, lo))))
          for (const hole of b.rings.slice(1)) shape.holes.push(new THREE.Path(hole.map(([lo, la]) => new THREE.Vector2(...local(la, lo)))))
          const g = new THREE.ExtrudeGeometry(shape, { depth: Math.max(1, b.h - b.base), bevelEnabled: false })
          g.translate(0, 0, ground + b.base + 0.5)
          const n = g.attributes.position.count
          g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(n * 3).fill(0.88), 3))
          g.deleteAttribute('uv')
          const [bx, by] = local(b.rings[0][0][1], b.rings[0][0][0])
          items.push({ start: offset, count: n, x: bx, y: by }); offset += n
          geos.push(g.index ? g.toNonIndexed() : g)
        }
        const merged = mergeGeometries(geos, false)
        const mesh = new THREE.Mesh(merged, bldMat); mesh.renderOrder = 1
        blds = { mesh, colors: merged.attributes.color, items }
        overlay.add(mesh); setBuildingCount(list.length); paintPlume()
      })
      const max = Math.max(1, ...secs.map(s => s.lbs)), big = false
      const colGeo = new THREE.CylinderGeometry(1, 1, 1, 24).rotateX(Math.PI / 2).translate(0, 0, 0.5)
      for (const s of secs) {
        const [x, y] = local(s.lat, s.lon)
        const [r, g, b] = ramp(0.45 + (s.lbs ? s.fumigant_lbs / s.lbs : 0) * 0.55)
        const col = new THREE.Mesh(colGeo, new THREE.MeshBasicMaterial({ color: new THREE.Color(r / 255, g / 255, b / 255), transparent: true, opacity: 0.8, depthWrite: false }))
        const rad = 45, h = 40 + 360 * Math.sqrt(s.lbs / max)
        col.scale.set(rad, rad, h); col.position.set(x, y, ground); overlay.add(col)
      }
      if (site.source) {
        overlay.add(plume); overlay.add(particles); paintPlume()
        const pin = new THREE.Mesh(new THREE.CylinderGeometry(6, 6, 1, 12).rotateX(Math.PI / 2).translate(0, 0, 0.5), new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false }))
        pin.scale.z = 220; pin.position.set(0, 0, ground); pin.renderOrder = 4; overlay.add(pin)
      }
    }

    api.current.setWind = w => { windNow = w; paintPlume() }

    let flight = null, idle = true, orbitLon = STOPS[0].lon
    renderer.domElement.addEventListener('pointerdown', () => { idle = false })
    api.current.fly = to => {
      const cart = ell.getPositionToCartographic(camera.position.clone().applyMatrix4(new THREE.Matrix4().copy(tiles.group.matrixWorld).invert()), {})
      const from = { lat: cart.lat / D2R, lon: cart.lon / D2R, height: cart.height, tilt: 0 }
      flight = { from, to, t0: performance.now(), dur: to.id === 'earth' || from.height > 2e6 ? 3200 : 2400 }
      idle = to.id === 'earth'; controls.enabled = false; tiles.errorTarget = MOVING
      clearOverlay(); setData(null); setMoving(true); setActive(to.id)
    }
    const ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
    function stepFlight(now) {
      const { from, to, t0, dur } = flight
      const t = Math.min(1, (now - t0) / dur), e = ease(t)
      const arc = Math.sin(Math.PI * t) * Math.min(Math.max(from.height, to.height) * 0.6, 4e6)
      place({ lat: from.lat + (to.lat - from.lat) * e, lon: from.lon + (to.lon - from.lon) * e,
        height: Math.exp(Math.log(Math.max(from.height, 300)) * (1 - e) + Math.log(to.height) * e) + arc, tilt: (to.tilt || 0) * e })
      if (t >= 1) { flight = null; controls.enabled = true; tiles.errorTarget = DETAIL; setMoving(false); orbitLon = to.lon; buildOverlay(to) }
    }

    function resize() { const w = host.clientWidth, h = host.clientHeight; renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix() }
    addEventListener('resize', resize); resize()
    tiles.group.updateMatrixWorld(); place(STOPS[0])

    let raf, lastCredits = ''
    const v3 = new THREE.Vector3(), reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    const loop = now => {
      raf = requestAnimationFrame(loop)
      if (flight) stepFlight(now)
      else if (idle && !reduce) { orbitLon += 0.02; place({ ...STOPS[0], lon: orbitLon }) }
      else controls.update()
      if (site?.source && !reduce) stepParticles(now / 1000)
      camera.updateMatrixWorld()
      tiles.setCamera(camera); tiles.setResolutionFromRenderer(camera, renderer); tiles.update()
      renderer.render(scene, camera)
      if (tagRef.current) {
        if (site?.source) {
          v3.set(0, 0, site.ground + 230).applyMatrix4(overlay.matrixWorld).project(camera)
          tagRef.current.style.display = v3.z < 1 ? 'block' : 'none'
          tagRef.current.style.left = ((v3.x + 1) / 2 * host.clientWidth) + 'px'
          tagRef.current.style.top = ((1 - v3.y) / 2 * host.clientHeight) + 'px'
        } else tagRef.current.style.display = 'none'
      }
      const c = tiles.getAttributions().map(a => a.value).filter(v => typeof v === 'string').join(' · ')
      if (c !== lastCredits) { lastCredits = c; setCredits(c) }
    }
    raf = requestAnimationFrame(loop)
    const start = STOPS.find(s => s.id === new URLSearchParams(location.search).get('stop'))
    if (start) setTimeout(() => api.current.fly(start), 1500) // deep link, e.g. /earth?stop=salinas
    return () => { cancelAnimationFrame(raf); removeEventListener('resize', resize); controls.dispose?.(); tiles.dispose(); renderer.dispose(); host.removeChild(renderer.domElement) }
  }, [])

  useEffect(() => { api.current.setWind?.(wind) }, [wind])

  const stops = custom ? [...STOPS, custom] : STOPS
  const stop = stops.find(s => s.id === active)

  function go(s) { if (!moving && KEY) api.current.fly?.(s) }

  async function search(e) {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    setSearchMsg('Searching…')
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=us&viewbox=-124.5,42.1,-114.1,32.5&bounded=1&q=${encodeURIComponent(q)}`
      const hit = (await (await fetch(url)).json())[0]
      if (!hit) { setSearchMsg('No match in California. Try a town, school or street address.'); return }
      const name = hit.display_name.split(',').slice(0, 2).join(',')
      const s = { id: 'search', label: name, title: name, target: name, lat: +hit.lat, lon: +hit.lon, height: 520, tilt: 68, radius: 4, plume: true,
        note: 'Recorded pesticide use within 4 km and a modelled drift scenario from the most heavily treated nearby section.' }
      setCustom(s); setSearchMsg(''); go(s)
    } catch { setSearchMsg('Search is unavailable right now.') }
  }

  async function liveWind() {
    try {
      const r = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${stop.lat}&longitude=${stop.lon}&current=wind_speed_10m,wind_direction_10m&wind_speed_unit=ms`)
      const c = (await r.json()).current
      setWind(w => ({ ...w, dir: Math.round(c.wind_direction_10m), speed: Math.round(c.wind_speed_10m * 10) / 10 }))
      setWindSrc(`Live wind, ${c.time.slice(11)} local`)
    } catch { setWindSrc('Live wind unavailable') }
  }

  const level = schoolLevel == null ? null : schoolLevel < 0.05 ? 'Not downwind' : schoolLevel < 0.35 ? 'Low' : schoolLevel < 0.65 ? 'Moderate' : 'High'
  const atEarth = active === 'earth'
  return (
    <div className={'earth' + (atEarth ? ' is-home' : '')}>
      <div className="earth-canvas" ref={mount} />
      <div className="earth-tag" ref={tagRef}>{stop?.target}</div>
      {!KEY && (
        <div className="earth-missing"><h2>Add a Google Maps key to see photorealistic 3D</h2>
          <p>Put <code>VITE_GOOGLE_MAPS_KEY=…</code> in <code>frontend/.env.local</code>, then restart <code>npm run dev</code>.</p></div>
      )}
      <header className="earth-head">
        <a className="earth-brand" href="/earth" onClick={e => { e.preventDefault(); go(STOPS[0]) }}><span className="earth-dot" />askgaia</a>
        <nav className="earth-nav"><a href="/">Investigate</a><a href="/explorer">Data explorer</a><span>Earth, understood.</span></nav>
      </header>

      {atEarth && (
        <section className="earth-stat" aria-live="off">
          <p className="earth-kicker">California · latest published data</p>
          <p className="earth-num">{count.toLocaleString('en-US')}<span> lbs</span></p>
          <p className="earth-sub">of pesticides recorded by the state from 2014 to 2024, the most recent year California has released. That is about 430,000 lbs a day.</p>
        </section>
      )}

      <form className="earth-search" onSubmit={search} role="search">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.5"/><path d="M3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18" fill="none" stroke="currentColor" strokeWidth="1.2"/></svg>
        <input id="place" aria-label="Search a place in California" placeholder="Search. Explore. Act." value={query} onChange={e => setQuery(e.target.value)} />
        <button type="submit" aria-label="Investigate">→</button>
      </form>
      {searchMsg && <p className="earth-searchmsg" role="status">{searchMsg}</p>}

      <nav className="earth-stops" aria-label="Places">
        {stops.map(s => (
          <button key={s.id} aria-pressed={active === s.id} disabled={moving || !KEY} onClick={() => go(s)}>{s.label}</button>
        ))}
      </nav>

      {stop?.title && (
        <section className="earth-card" aria-live="polite">
          <p className="earth-kicker">{moving ? 'Flying…' : 'Recorded 2020–2024 · latest published'}</p>
          <h1>{stop.title}</h1>
          <p className="earth-note">{stop.note}</p>
          {data?.stop?.id === stop.id && data.secs.length > 0 && (
            <dl className="earth-stats">
              <div><dt>Applied within {stop.radius} km</dt><dd>{fmt(data.total)} lbs</dd></div>
              <div><dt>Of which fumigants</dt><dd>{fmt(data.fum)} lbs</dd></div>
              <div><dt>Treated sections</dt><dd>{data.secs.length}</dd></div>
              {data.source && <div><dt>Plume source</dt><dd>{data.source.top_chemical?.toLowerCase()}</dd></div>}
            </dl>
          )}
          {data?.stop?.id === stop.id && data.secs.length === 0 && <p className="earth-note">No recorded agricultural use found nearby, or the backend isn't running.</p>}

          {stop.plume && data?.source && (
            <div className="earth-wind">
              <div className="earth-wind-head"><p className="earth-kicker">Drift · modelled</p><button type="button" onClick={liveWind}>Use live wind</button></div>
              <label htmlFor="wdir">Wind from <b>{wind.dir}°</b></label>
              <input id="wdir" type="range" min="0" max="359" value={wind.dir} onChange={e => { setWindSrc('Scenario'); setWind(w => ({ ...w, dir: +e.target.value })) }} />
              <label htmlFor="wspd">Speed <b>{wind.speed} m/s</b></label>
              <input id="wspd" type="range" min="0.5" max="12" step="0.5" value={wind.speed} onChange={e => { setWindSrc('Scenario'); setWind(w => ({ ...w, speed: +e.target.value })) }} />
              <div className="earth-cls" role="group" aria-label="Atmospheric stability">
                {'ABCDEF'.split('').map(c => <button type="button" key={c} aria-pressed={wind.cls === c} onClick={() => setWind(w => ({ ...w, cls: c }))}>{c}</button>)}
              </div>
              <p className="earth-read"><span>{stop.target}</span><b data-level={level}>{level ?? '…'}</b></p>
              {buildingCount > 0 && <p className="earth-fine">{buildingCount.toLocaleString('en-US')} buildings coloured by modelled drift. Turn the wind to see which homes sit downwind.</p>}
              <p className="earth-fine">{windSrc}. Gaussian plume, stability {wind.cls}. Relative estimate, not measured exposure.</p>
            </div>
          )}
          <p className="earth-fine">Columns are treated square-mile sections: height is pounds applied, colour is the fumigant share. Source: CDPR Pesticide Use Reports.</p>
        </section>
      )}

      {!atEarth && <p className="earth-hint">Scroll or pinch to zoom · Shift-drag or right-drag to tilt</p>}
      <footer className="earth-credits">
        <img src="https://www.gstatic.com/images/branding/googlelogo/svg/googlelogo_clr_74x24px.svg" alt="Google" height="16" />
        <span>{credits}</span>
      </footer>
    </div>
  )
}
