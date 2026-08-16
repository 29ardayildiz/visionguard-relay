# VisionGuard PWA — Eksiksiz SVG İkon & Varlık Seti Rehberi

Bu paket, **VisionGuard** PWA uygulaması için harici CDN (Material Symbols, FontAwesome vb.) bağımlılığını tamamen ortadan kaldıran, hafif ve tutarlı **18 adet SVG** varlığı içerir.

Tema: **Emerald Guard (Siber Koruma Çemberi & HUD)**

---

## 1. PWA & Sistem İkonları

| Dosya Adı | Boyut / Tip | Kullanım Yeri |
|---|---|---|
| `app-icon.svg` | 512x512 | Standalone PWA simgesi, masaüstü/mobil ana ekran ve Apple Touch Icon. |
| `maskable-icon.svg` | 512x512 | Android Adaptive Launcher kırpmaları için %20 güvenli alan (safe-zone) paylı ikon. |
| `favicon.svg` | 32x32 | Tarayıcı sekmesi için optimize edilmiş minimal HUD ikonu. |

---

## 2. Sistem & Canlı Bağlantı Durumu

| Dosya Adı | Durum | Açıklama |
|---|---|---|
| `status-live.svg` | 🟢 Canlı / Online | ESP32 aktif yayın yaparken rozet veya başlıkta gösterilecek canlı sinyal/radar ikonu. |
| `loader-waking.svg` | 🟡 Sunucu Uyanıyor | Render cold-start veya WS yeniden bağlanma aşamasında dönen HUD yükleme animasyonu. |
| `camera-offline.svg` | 🔴 Cihaz Kapalı | ESP32 offline olduğunda stream alanında gösterilecek sinyal yok ikonu. |

---

## 3. Admin Paneli Ayar Kartı Başlıkları (Tam Eşleşme)

| Dosya Adı | Karşılık Gelen Kart | Açıklama |
|---|---|---|
| `card-imaging.svg` | **Imaging Controls** | Kamera gövdesi, vizör ve sensör odaklı lens ikonu (`photo_camera` yerine). |
| `card-white-balance.svg` | **White Balance** | Işık ve renk sıcaklığı sembolü (`wb_sunny` yerine). |
| `card-exposure-gain.svg` | **Exposure & Gain** | Kamera deklanşör (shutter) ve diyafram bıçakları ikonu (`shutter_speed` yerine). |
| `card-advanced.svg` | **Advanced** | Ekolayzır / hassas donanım ayar kaydırıcıları ikonu (`tune` yerine). |

---

## 4. Kamera Hızlı Ayar Profilleri (Quick Presets)

| Dosya Adı | Profil | Açıklama |
|---|---|---|
| `preset-high-quality.svg` | 🎯 High Quality | Yüksek çözünürlük ve keskinlik hedefleme ikonu. |
| `preset-high-fps.svg` | ⚡ High FPS (~20fps) | Yüksek kare hızı ve hız ikonu. |
| `preset-night-mode.svg` | 🌙 Night Mode | Gece görüşü ve düşük ışık kazancı ikonu. |
| `preset-fixed-light.svg` | 💡 Fixed Light | Sabit ışıklı ortamlar (garaj vb.) için kilitli ışık ampul ikonu. |

---

## 5. Aksiyon & Kontrol Butonları

| Dosya Adı | Buton | Açıklama |
|---|---|---|
| `action-sync.svg` | **Sync from Camera** | ESP32'den güncel donanım parametrelerini çekme ikonu. |
| `action-apply.svg` | **Apply All** | Tüm ayarları ESP32'ye toplu gönderme (onay/check) ikonu. |
| `action-reset.svg` | **Reset Defaults** | Ayarları fabrika varsayılanına döndürme (geri sarma) ikonu. |
| `action-settings.svg` | **Admin / Ayarlar** | Viewer ekranından admin paneline geçiş dişli çarkı. |
| `action-logout.svg` | **Çıkış Yap** | Oturumu güvenli kapatma ikonu. |

---

## Tailwind & Framework Entegrasyonu

Aksiyon, kart ve preset ikonlarının tamamında `stroke="currentColor"` kullanılmıştır. Bu sayede Svelte/Vue/React veya düz HTML içinde:

```html
<!-- Emerald renkli Imaging kart başlığı -->
<div class="flex items-center gap-2 text-emerald-400">
  <img src="/icons/card-imaging.svg" class="w-5 h-5" alt="Imaging" />
  <span class="font-semibold text-gray-100">Imaging Controls</span>
</div>
```
şeklinde veya doğrudan inline SVG olarak dinamik Tailwind sınıflarıyla (`text-emerald-500`, `text-amber-400`, `text-gray-400` vb.) kullanılabilir.
