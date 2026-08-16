// CURRENT_APP_FEATURES.md §3.2 — eski admin.html'deki dropdown seçenekleriyle
// birebir aynı (framesize_t / ov3660 sensör enum değerleri).

export const FRAMESIZE_OPTIONS = [
  { value: 0, label: '96x96' },
  { value: 1, label: 'QQVGA 160x120' },
  { value: 2, label: 'QCIF 176x144' },
  { value: 3, label: 'HQVGA 240x176' },
  { value: 4, label: '240x240' },
  { value: 5, label: 'QVGA 320x240' },
  { value: 6, label: 'CIF 400x296' },
  { value: 7, label: 'HVGA 480x320' },
  { value: 8, label: 'VGA 640x480' },
  { value: 9, label: 'SVGA 800x600' },
  { value: 10, label: 'XGA 1024x768' },
  { value: 11, label: 'HD 1280x720' },
  { value: 12, label: 'SXGA 1280x1024' },
  { value: 13, label: 'UXGA 1600x1200' },
]

export const SPECIAL_EFFECT_OPTIONS = [
  { value: 0, label: 'None' },
  { value: 1, label: 'Negative' },
  { value: 2, label: 'Grayscale' },
  { value: 3, label: 'Red Tint' },
  { value: 4, label: 'Green Tint' },
  { value: 5, label: 'Blue Tint' },
  { value: 6, label: 'Sepia' },
]

export const WB_MODE_OPTIONS = [
  { value: 0, label: 'Auto' },
  { value: 1, label: 'Sunny' },
  { value: 2, label: 'Cloudy' },
  { value: 3, label: 'Office' },
  { value: 4, label: 'Home' },
]

export const GAINCEILING_OPTIONS = [
  { value: 0, label: '2x' },
  { value: 1, label: '4x' },
  { value: 2, label: '8x' },
  { value: 3, label: '16x' },
  { value: 4, label: '32x' },
  { value: 5, label: '64x' },
  { value: 6, label: '128x' },
]
