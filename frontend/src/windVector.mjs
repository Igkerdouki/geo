// Meteorological bearing names the direction wind comes FROM.
export function windVector(direction, speed) {
  const radians = direction * Math.PI / 180
  return { east: -Math.sin(radians) * speed, north: -Math.cos(radians) * speed }
}
