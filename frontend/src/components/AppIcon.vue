<script setup lang="ts">
// currentColor kullanan SVG'ler (icons/{actions,cards,presets,status}/...) için
// ortak render bileşeni. `<img src>` currentColor'ı devralamaz (SVG izole bir
// belge olarak yüklenir); bu yüzden ?raw import + v-html ile inline ediyoruz,
// böylece SVG DOM'a gömülür ve `color`/`text-*` Tailwind sınıfları çalışır.

defineProps<{ svg: string }>()
</script>

<template>
  <span class="inline-flex" v-html="svg" />
</template>
