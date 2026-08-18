<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

import AppIcon from '../components/AppIcon.vue'
import SettingsCard from '../components/settings/SettingsCard.vue'
import SelectControl from '../components/settings/SelectControl.vue'
import SliderControl from '../components/settings/SliderControl.vue'
import ToggleControl from '../components/settings/ToggleControl.vue'

import cardAdvancedSvg from '../icons/cards/card-advanced.svg?raw'
import cardExposureGainSvg from '../icons/cards/card-exposure-gain.svg?raw'
import cardImagingSvg from '../icons/cards/card-imaging.svg?raw'
import cardWhiteBalanceSvg from '../icons/cards/card-white-balance.svg?raw'
import actionApplySvg from '../icons/actions/action-apply.svg?raw'
import actionResetSvg from '../icons/actions/action-reset.svg?raw'
import actionSyncSvg from '../icons/actions/action-sync.svg?raw'
import presetFixedLightSvg from '../icons/presets/preset-fixed-light.svg?raw'
import presetHighFpsSvg from '../icons/presets/preset-high-fps.svg?raw'
import presetHighQualitySvg from '../icons/presets/preset-high-quality.svg?raw'
import presetNightModeSvg from '../icons/presets/preset-night-mode.svg?raw'

import { usePwaUpdate } from '../composables/usePwaUpdate'
import { APP_VERSION } from '../lib/version'
import {
  FRAMESIZE_OPTIONS,
  GAINCEILING_OPTIONS,
  SPECIAL_EFFECT_OPTIONS,
  WB_MODE_OPTIONS,
} from '../lib/cameraOptions'
import { useConnectionStore } from '../stores/connection'
import { useCameraStore, type CameraSettings } from '../stores/camera'
import { useToastStore } from '../stores/toast'

const router = useRouter()
const connection = useConnectionStore()
const camera = useCameraStore()
const toast = useToastStore()
// Destructure şart: usePwaUpdate düz obje döndürür (Pinia store değil) —
// ref'ler ancak top-level değişken olarak template'te unwrap edilir.
const { updateAvailable, updating, applyUpdate } = usePwaUpdate()

function onApplyUpdate(): void {
  if ('vibrate' in navigator) navigator.vibrate(10)
  void applyUpdate()
}

const PRESETS = [
  { key: 'hq', label: 'High Quality', icon: presetHighQualitySvg },
  { key: 'hfps', label: 'High FPS', icon: presetHighFpsSvg },
  { key: 'night', label: 'Night Mode', icon: presetNightModeSvg },
  { key: 'fixed_light', label: 'Fixed Light', icon: presetFixedLightSvg },
] as const

function onKeyDown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    goViewer()
  }
}

onMounted(async () => {
  // Auth kontrolü router guard'ında (render'dan önce) yapılıyor.
  connection.start()
  window.addEventListener('keydown', onKeyDown)
  const ok = await camera.fetchSettings()
  if (!ok && !camera.loaded) {
      // Gerçek değerler alınamadı — paneli sonsuza dek soluk bırakmak yerine
      // varsayılanlarla etkileşime izin ver, ama kullanıcıyı uyar.
    toast.show('Ayarlar yüklenemedi, varsayılanlar gösteriliyor', 'err')
    camera.loaded = true
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
})

function vibrate(): void {
  if ('vibrate' in navigator) navigator.vibrate(10)
}

function goViewer(): void {
  // Bkz. ViewerView.vue goAdmin() — aynı sekme çifti, aynı gerekçe: replace.
  router.replace({ name: 'viewer' })
}

async function commitSetting<K extends keyof CameraSettings>(key: K, value: CameraSettings[K]): Promise<void> {
  const ok = await camera.setSetting(key, value)
  // Native ayar panelleri (iOS Ayarlar gibi) başarıyı sessiz kabul eder —
  // her slider/toggle değişiminde onay toast'ı görsel gürültü yaratıyordu.
  // Yalnızca hata bildirilir; Preset/Sync/Reset/Apply All gibi açık buton
  // aksiyonları kendi onay toast'larını korur.
  if (!ok) toast.show(`${key} güncellenemedi`, 'err')
}

function toggleValue<K extends keyof CameraSettings>(key: K, checked: boolean): void {
  void commitSetting(key, (checked ? 1 : 0) as CameraSettings[K])
}

async function onPreset(name: (typeof PRESETS)[number]['key']): Promise<void> {
  vibrate()
  await camera.applyPreset(name)
  toast.show('Preset uygulandı', 'ok')
}

async function onSync(): Promise<void> {
  vibrate()
  const ok = await camera.syncFromCamera()
  toast.show(ok ? "ESP32'den senkronize edildi" : 'ESP32 WebSocket bağlı değil (push modu)', ok ? 'ok' : 'err')
}

async function onReset(): Promise<void> {
  vibrate()
  await camera.resetDefaults()
  toast.show('Varsayılanlara sıfırlandı', 'ok')
}

async function onApplyAll(): Promise<void> {
  vibrate()
  const applied = await camera.applyAll()
  if (applied === null) {
    toast.show('Uygulanamadı', 'err')
  } else {
    toast.show(applied > 0 ? `${applied} ayar uygulandı` : 'Kaydedildi (push modu)', 'ok')
  }
}
</script>

<template>
  <div class="flex h-full flex-col bg-guard-bg">
    <!-- Üst bar -->
    <header
      class="z-20 flex shrink-0 items-center justify-between border-b border-guard-border bg-guard-bg/90 px-4 py-3 backdrop-blur-md"
      :style="{
        paddingTop: 'calc(var(--sat) + 0.75rem)',
        paddingLeft: 'calc(var(--sal) + 1rem)',
        paddingRight: 'calc(var(--sar) + 1rem)',
      }"
    >
      <button
        type="button"
        aria-label="Canlı Yayına Geri Dön"
        class="-ml-2 min-h-11 rounded-lg px-3 text-sm text-guard-secondary transition-all active:scale-95 hover:text-guard-primary"
        @click="goViewer"
      >
        ‹ Canlı
      </button>
      <h1 class="text-sm font-semibold text-guard-primary">Kamera Ayarları</h1>
      <div
        class="flex items-center gap-1.5 rounded-full border border-guard-border bg-guard-surface px-3 py-1 text-xs text-guard-secondary"
      >
        <span
          class="h-1.5 w-1.5 rounded-full"
          :class="connection.esp32Connected ? 'bg-status-live' : 'bg-guard-border'"
        />
        ESP32: {{ connection.esp32Connected ? 'Online' : 'Offline' }}
      </div>
    </header>

    <!-- İç kaydırılabilir içerik — body artık kaydırılamaz (anti-web: kenar
    kaydırma jesti), bu yüzden scroll burada, kendi konteynerinde. -->
    <div
      class="flex-1 overflow-y-auto overscroll-contain"
      :style="{
        paddingLeft: 'var(--sal)',
        paddingRight: 'var(--sar)',
        scrollPaddingBottom: 'calc(var(--sab) + 6.5rem)',
      }"
    >
      <!-- Gerçek değerler backend'den gelene kadar panel soluk + etkileşimsiz:
      varsayılan -> gerçek değer "sıçraması" görünmez, yanlış değere dokunulamaz. -->
      <div
        class="mx-auto max-w-2xl space-y-4 p-4 pb-44 transition-opacity duration-200 sm:pb-28"
        :class="!camera.loaded && 'pointer-events-none opacity-40'"
      >
        <!-- Quick Presets -->
      <div class="grid grid-cols-2 gap-2 rounded-xl border border-guard-border bg-guard-surface p-1.5 sm:grid-cols-4">
        <button
          v-for="preset in PRESETS"
          :key="preset.key"
          type="button"
          class="flex min-h-16 flex-col items-center justify-center gap-1.5 rounded-lg px-2 py-2.5 text-xs font-semibold text-guard-secondary transition-colors hover:bg-guard-elevated hover:text-guard-primary active:scale-95"
          @click="onPreset(preset.key)"
        >
          <AppIcon :svg="preset.icon" class="h-6 w-6 text-brand-accent" />
          {{ preset.label }}
        </button>
      </div>

      <!-- Imaging Controls -->
      <SettingsCard title="Imaging Controls" :icon="cardImagingSvg">
        <SelectControl
          label="Resolution"
          :model-value="camera.settings.framesize"
          :options="FRAMESIZE_OPTIONS"
          @update:model-value="commitSetting('framesize', $event)"
        />
        <SliderControl
          label="JPEG Quality"
          :model-value="camera.settings.quality"
          :min="4"
          :max="63"
          @update:model-value="camera.settings.quality = $event"
          @commit="commitSetting('quality', $event)"
        />
        <SliderControl
          label="Brightness"
          :model-value="camera.settings.brightness"
          :min="-2"
          :max="2"
          @update:model-value="camera.settings.brightness = $event"
          @commit="commitSetting('brightness', $event)"
        />
        <SliderControl
          label="Contrast"
          :model-value="camera.settings.contrast"
          :min="-2"
          :max="2"
          @update:model-value="camera.settings.contrast = $event"
          @commit="commitSetting('contrast', $event)"
        />
        <SliderControl
          label="Saturation"
          :model-value="camera.settings.saturation"
          :min="-2"
          :max="2"
          @update:model-value="camera.settings.saturation = $event"
          @commit="commitSetting('saturation', $event)"
        />
        <SliderControl
          label="Sharpness"
          :model-value="camera.settings.sharpness"
          :min="-2"
          :max="2"
          @update:model-value="camera.settings.sharpness = $event"
          @commit="commitSetting('sharpness', $event)"
        />
        <SliderControl
          label="Denoise"
          :model-value="camera.settings.denoise"
          :min="0"
          :max="255"
          @update:model-value="camera.settings.denoise = $event"
          @commit="commitSetting('denoise', $event)"
        />
        <SelectControl
          label="Special Effect"
          :model-value="camera.settings.special_effect"
          :options="SPECIAL_EFFECT_OPTIONS"
          @update:model-value="commitSetting('special_effect', $event)"
        />
      </SettingsCard>

      <!-- White Balance -->
      <SettingsCard title="White Balance" :icon="cardWhiteBalanceSvg">
        <ToggleControl
          label="White Balance"
          :model-value="Boolean(camera.settings.whitebal)"
          @update:model-value="toggleValue('whitebal', $event)"
        />
        <ToggleControl
          label="AWB Gain"
          :model-value="Boolean(camera.settings.awb_gain)"
          @update:model-value="toggleValue('awb_gain', $event)"
        />
        <SelectControl
          label="WB Mode"
          :model-value="camera.settings.wb_mode"
          :options="WB_MODE_OPTIONS"
          @update:model-value="commitSetting('wb_mode', $event)"
        />
      </SettingsCard>

      <!-- Exposure & Gain -->
      <SettingsCard title="Exposure &amp; Gain" :icon="cardExposureGainSvg">
        <ToggleControl
          label="Exposure Control"
          :model-value="Boolean(camera.settings.exposure_ctrl)"
          @update:model-value="toggleValue('exposure_ctrl', $event)"
        />
        <ToggleControl
          label="AEC2"
          :model-value="Boolean(camera.settings.aec2)"
          @update:model-value="toggleValue('aec2', $event)"
        />
        <SliderControl
          label="AE Level"
          :model-value="camera.settings.ae_level"
          :min="-2"
          :max="2"
          @update:model-value="camera.settings.ae_level = $event"
          @commit="commitSetting('ae_level', $event)"
        />
        <SliderControl
          label="AEC Value"
          :model-value="camera.settings.aec_value"
          :min="0"
          :max="1200"
          @update:model-value="camera.settings.aec_value = $event"
          @commit="commitSetting('aec_value', $event)"
        />
        <ToggleControl
          label="Gain Control"
          :model-value="Boolean(camera.settings.gain_ctrl)"
          @update:model-value="toggleValue('gain_ctrl', $event)"
        />
        <SliderControl
          label="AGC Gain"
          :model-value="camera.settings.agc_gain"
          :min="0"
          :max="30"
          @update:model-value="camera.settings.agc_gain = $event"
          @commit="commitSetting('agc_gain', $event)"
        />
        <SelectControl
          label="Gain Ceiling"
          :model-value="camera.settings.gainceiling"
          :options="GAINCEILING_OPTIONS"
          @update:model-value="commitSetting('gainceiling', $event)"
        />
      </SettingsCard>

      <!-- Advanced -->
      <SettingsCard title="Advanced" :icon="cardAdvancedSvg">
        <div class="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
          <ToggleControl
            label="BPC"
            :model-value="Boolean(camera.settings.bpc)"
            @update:model-value="toggleValue('bpc', $event)"
          />
          <ToggleControl
            label="WPC"
            :model-value="Boolean(camera.settings.wpc)"
            @update:model-value="toggleValue('wpc', $event)"
          />
          <ToggleControl
            label="Raw GMA"
            :model-value="Boolean(camera.settings.raw_gma)"
            @update:model-value="toggleValue('raw_gma', $event)"
          />
          <ToggleControl
            label="LENC"
            :model-value="Boolean(camera.settings.lenc)"
            @update:model-value="toggleValue('lenc', $event)"
          />
          <ToggleControl
            label="H-Mirror"
            :model-value="Boolean(camera.settings.hmirror)"
            @update:model-value="toggleValue('hmirror', $event)"
          />
          <ToggleControl
            label="V-Flip"
            :model-value="Boolean(camera.settings.vflip)"
            @update:model-value="toggleValue('vflip', $event)"
          />
          <ToggleControl
            label="DCW"
            :model-value="Boolean(camera.settings.dcw)"
            @update:model-value="toggleValue('dcw', $event)"
          />
          <ToggleControl
            label="Colorbar"
            :model-value="Boolean(camera.settings.colorbar)"
            @update:model-value="toggleValue('colorbar', $event)"
          />
        </div>
      </SettingsCard>

      <!-- Sürüm bölümü: güncelleme buradan ELLE yapılır (pop-up yok, oto
      güncelleme yok) — yeni sürüm işareti viewer'daki gear badge'i. -->
      <div
        v-if="updateAvailable"
        class="flex items-center justify-between gap-3 rounded-2xl border border-brand/30 bg-brand/10 p-4"
      >
        <div class="min-w-0">
          <p class="text-sm font-semibold text-brand-accent">Yeni sürüm mevcut</p>
          <p class="mt-0.5 text-xs text-guard-secondary">
            Güncelleme uygulanırken sayfa bir kez yenilenir
          </p>
        </div>
        <button
          type="button"
          :disabled="updating"
          aria-label="Uygulamayı Güncelle"
          class="min-h-11 shrink-0 rounded-lg bg-brand px-4 text-sm font-bold text-guard-bg transition-all hover:bg-brand-hover active:scale-95 disabled:opacity-60"
          @click="onApplyUpdate"
        >
          {{ updating ? 'Güncelleniyor...' : 'Güncelle' }}
        </button>
      </div>

      <p class="selectable pt-1 text-center text-xs text-guard-muted">
        VisionGuard · v{{ APP_VERSION }}{{ updateAvailable ? '' : ' · Sürüm güncel' }}
      </p>
      </div>
    </div>

    <!-- Alt sabit aksiyon barı -->
    <footer
      class="fixed inset-x-0 bottom-0 z-20 flex flex-col gap-2 border-t border-guard-border bg-guard-bg/90 px-4 py-3 backdrop-blur-md sm:flex-row sm:items-center sm:justify-between"
      :style="{
        paddingBottom: 'calc(var(--sab) + 0.75rem)',
        paddingLeft: 'calc(var(--sal) + 1rem)',
        paddingRight: 'calc(var(--sar) + 1rem)',
      }"
    >
      <div class="flex gap-2">
        <button
          type="button"
          class="flex min-h-11 flex-1 items-center justify-center gap-2 rounded-lg bg-guard-elevated px-4 text-sm font-semibold text-guard-primary transition-colors hover:bg-guard-border active:scale-95 sm:flex-initial"
          @click="onSync"
        >
          <AppIcon :svg="actionSyncSvg" class="h-5 w-5" />
          Sync
        </button>
        <button
          type="button"
          class="flex min-h-11 flex-1 items-center justify-center gap-2 rounded-lg border border-guard-border px-4 text-sm font-semibold text-guard-secondary transition-colors hover:bg-guard-surface active:scale-95 sm:flex-initial"
          @click="onReset"
        >
          <AppIcon :svg="actionResetSvg" class="h-5 w-5" />
          Reset
        </button>
      </div>
      <button
        type="button"
        class="flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-brand px-6 text-sm font-bold text-guard-bg shadow-lg shadow-brand/10 transition-all hover:bg-brand-hover active:scale-95 sm:min-h-11 sm:w-auto"
        @click="onApplyAll"
      >
        <AppIcon :svg="actionApplySvg" class="h-5 w-5" />
        Apply All
      </button>
    </footer>
  </div>
</template>
