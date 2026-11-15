export function normalizeWeather(data) {
  if (!Number.isFinite(data.speed_ms) || data.speed_ms < 0 || data.speed_ms > 60 || !Number.isFinite(data.from_deg)) {
    throw new Error('Weather provider returned invalid wind');
  }
  return { speed: data.speed_ms, from: ((data.from_deg % 360) + 360) % 360,
    label: `${data.source || 'Weather'} model · ${data.valid_at_utc || 'time unavailable'} UTC`,
    supported: data.speed_ms >= 0.5 };
}

export async function currentWeather(lat, lon, signal) {
  const response = await fetch(`/api/workflows/weather?${new URLSearchParams({lat, lon})}`, {signal});
  if (!response.ok) throw new Error('Current weather unavailable');
  return normalizeWeather(await response.json());
}
