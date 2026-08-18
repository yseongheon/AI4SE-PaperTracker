import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// Professional 设计系统字体（@fontsource，npm 镜像本地打包，不依赖 Google Fonts CDN）
import '@fontsource/poppins/400.css'
import '@fontsource/poppins/500.css'
import '@fontsource/poppins/600.css'
import '@fontsource/poppins/700.css'
import '@fontsource/poppins/800.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import './style.css'
import App from './App.vue'
import router from './router'

createApp(App).use(createPinia()).use(router).use(ElementPlus).mount('#app')
