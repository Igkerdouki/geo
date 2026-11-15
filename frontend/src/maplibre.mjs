import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

// MapLibre 6 ships a separate module worker. Let Vite resolve and bundle it
// instead of resolving the relative worker path against its dependency cache.
maplibregl.setWorkerUrl(workerUrl)
export default maplibregl
