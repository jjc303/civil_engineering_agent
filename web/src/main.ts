import { createApp, defineAsyncComponent } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'

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

app.component('v-chart', AsyncECharts)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

app.mount('#app')
