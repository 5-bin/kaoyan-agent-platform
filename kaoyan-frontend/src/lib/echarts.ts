import * as echarts from 'echarts/core'
import { BarChart, HeatmapChart, LineChart, ScatterChart } from 'echarts/charts'
import {
  AriaComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  HeatmapChart,
  LineChart,
  ScatterChart,
  AriaComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
])

export type { EChartsOption } from 'echarts'
export type EChartsInstance = ReturnType<typeof echarts.init>
export default echarts
