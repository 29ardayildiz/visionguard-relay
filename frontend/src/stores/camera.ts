import { reactive, ref } from 'vue'
import { defineStore } from 'pinia'

import { apiFetch } from '../lib/api'

// CURRENT_APP_FEATURES.md §5 — backend'deki camera_settings ile birebir aynı
// 26 alan. Anahtar isimleri backend'in JSON şemasıyla (routers/camera.py,
// ESP32 JSON komutları) birebir eşleşmeli — burada değiştirilemez.
export interface CameraSettings {
  framesize: number
  quality: number
  brightness: number
  contrast: number
  saturation: number
  sharpness: number
  denoise: number
  special_effect: number
  whitebal: number
  awb_gain: number
  wb_mode: number
  exposure_ctrl: number
  aec2: number
  ae_level: number
  aec_value: number
  gain_ctrl: number
  agc_gain: number
  gainceiling: number
  bpc: number
  wpc: number
  raw_gma: number
  lenc: number
  hmirror: number
  vflip: number
  dcw: number
  colorbar: number
}

export const CAMERA_DEFAULTS: CameraSettings = {
  framesize: 5,
  quality: 12,
  brightness: 0,
  contrast: 0,
  saturation: 0,
  sharpness: 0,
  denoise: 0,
  special_effect: 0,
  whitebal: 1,
  awb_gain: 1,
  wb_mode: 0,
  exposure_ctrl: 1,
  aec2: 0,
  ae_level: 0,
  aec_value: 300,
  gain_ctrl: 1,
  agc_gain: 0,
  gainceiling: 0,
  bpc: 0,
  wpc: 1,
  raw_gma: 1,
  lenc: 1,
  hmirror: 1,
  vflip: 1,
  dcw: 1,
  colorbar: 0,
}

// Quick Presets — CURRENT_APP_FEATURES.md §3.2'deki dört profilin birebir
// aynı değer setleri (eski admin.html'deki DEFAULTS/hq/hfps/night/fixed_light).
// Not: kasıtlı olarak Record<string, ...> ile açıkça tiplenmiyor — literal
// key'lerin (hq/hfps/night/fixed_light) korunması, applyPreset'teki indeksleme
// için `noUncheckedIndexedAccess` altında undefined riskini ortadan kaldırıyor.
export const CAMERA_PRESETS = {
  hq: {
    framesize: 9,
    quality: 10,
    brightness: 0,
    contrast: 1,
    saturation: 1,
    sharpness: 1,
    denoise: 10,
    whitebal: 1,
    awb_gain: 1,
    wb_mode: 0,
    exposure_ctrl: 1,
    aec2: 1,
    ae_level: 0,
    gain_ctrl: 1,
    agc_gain: 0,
    gainceiling: 2,
    bpc: 1,
    wpc: 1,
    raw_gma: 1,
    lenc: 1,
    hmirror: 1,
    vflip: 1,
    dcw: 1,
  },
  hfps: {
    framesize: 5,
    quality: 30,
    brightness: 0,
    contrast: 0,
    saturation: 0,
    sharpness: 0,
    denoise: 0,
    exposure_ctrl: 1,
    aec2: 0,
    gain_ctrl: 1,
    agc_gain: 0,
    hmirror: 1,
    vflip: 1,
  },
  night: {
    framesize: 5,
    quality: 20,
    brightness: 2,
    contrast: 1,
    saturation: -1,
    sharpness: 0,
    denoise: 128,
    exposure_ctrl: 1,
    aec2: 1,
    ae_level: 2,
    gain_ctrl: 1,
    agc_gain: 20,
    gainceiling: 4,
    hmirror: 1,
    vflip: 1,
  },
  fixed_light: {
    framesize: 10,
    quality: 12,
    brightness: 0,
    contrast: 1,
    saturation: 1,
    sharpness: 1,
    denoise: 10,
    whitebal: 1,
    awb_gain: 0,
    wb_mode: 1,
    exposure_ctrl: 0,
    aec2: 0,
    ae_level: 0,
    aec_value: 300,
    gain_ctrl: 0,
    agc_gain: 5,
    gainceiling: 0,
    bpc: 1,
    wpc: 1,
    raw_gma: 1,
    lenc: 1,
    hmirror: 1,
    vflip: 1,
    dcw: 1,
    colorbar: 0,
  },
}

export const useCameraStore = defineStore('camera', () => {
  const settings = reactive<CameraSettings>({ ...CAMERA_DEFAULTS })
  const loaded = ref(false)

  function applyLocal(values: Partial<CameraSettings>): void {
    Object.assign(settings, values)
  }

  async function fetchSettings(): Promise<boolean> {
    const response = await apiFetch('/api/camera/settings')
    if (!response || !response.ok) return false
    const data = (await response.json()) as CameraSettings & { esp32_connected: boolean }
    const { esp32_connected: _esp32Connected, ...rest } = data
    applyLocal(rest)
    loaded.value = true
    return true
  }

  async function setSetting<K extends keyof CameraSettings>(key: K, value: CameraSettings[K]): Promise<boolean> {
    settings[key] = value
    const response = await apiFetch('/api/camera/set', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value }),
    })
    return !!response && response.ok
  }

  async function applyValues(values: Partial<CameraSettings>): Promise<void> {
    for (const [key, value] of Object.entries(values)) {
      await setSetting(key as keyof CameraSettings, value as number)
    }
  }

  async function applyAll(): Promise<number | null> {
    const response = await apiFetch('/api/camera/apply_all', { method: 'POST' })
    if (!response || !response.ok) return null
    const data = (await response.json()) as { applied: number }
    return data.applied
  }

  async function resetDefaults(): Promise<void> {
    await applyValues(CAMERA_DEFAULTS)
  }

  async function applyPreset(name: keyof typeof CAMERA_PRESETS): Promise<void> {
    await applyValues(CAMERA_PRESETS[name])
    await applyAll()
  }

  async function syncFromCamera(): Promise<boolean> {
    const response = await apiFetch('/api/camera/get_from_esp', { method: 'POST' })
    if (!response || !response.ok) return false
    const data = (await response.json()) as CameraSettings & { esp32_connected: boolean }
    const { esp32_connected: _esp32Connected, ...rest } = data
    applyLocal(rest)
    return true
  }

  return {
    settings,
    loaded,
    fetchSettings,
    setSetting,
    applyAll,
    resetDefaults,
    applyPreset,
    syncFromCamera,
  }
})
