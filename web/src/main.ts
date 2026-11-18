import { createApp, defineAsyncComponent } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import { registerApiTranslator } from './api/ports'
import { registerElementApiNotifier } from './api/notifiers/elementPlus'
import { i18n, translateAppMessage } from './i18n'
import { useLocaleStore } from './stores/locale'
import router from './router'
import App from './App.vue'
import './style.css'
import './styles/operations.css'

const AsyncECharts = defineAsyncComponent(async () => {
  const [
    { default: ECharts },
    { use },
    { CanvasRenderer },
    { PieChart, BarChart, LineChart, HeatmapChart },
    { GridComponent, TooltipComponent, LegendComponent, TitleComponent, VisualMapComponent },
  ] = await Promise.all([
    import('vue-echarts'),
    import('echarts/core'),
    import('echarts/renderers'),
    import('echarts/charts'),
    import('echarts/components'),
  ])
  use([
    CanvasRenderer,
    PieChart,
    BarChart,
    LineChart,
    HeatmapChart,
    GridComponent,
    TooltipComponent,
    LegendComponent,
    TitleComponent,
    VisualMapComponent,
  ])
  return ECharts
})

const app = createApp(App)
const pinia = createPinia()

app.component('v-chart', AsyncECharts)
app.use(pinia)
useLocaleStore(pinia).init()
registerApiTranslator(translateAppMessage)
registerElementApiNotifier()
app.use(i18n)
app.use(router)
app.use(ElementPlus)

app.mount('#app')
