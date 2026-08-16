import './index.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useInstallStore } from './stores/install'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// beforeinstallprompt sayfa yüklenir yüklenmez ateşlenebileceği için
// listener'ı mount'tan önce, en erken noktada kaydediyoruz.
useInstallStore().listen()

app.mount('#app')
