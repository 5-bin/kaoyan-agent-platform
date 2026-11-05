<template>
  <canvas ref="canvasRef" class="pixel-field" aria-hidden="true" :data-running="running ? 'true' : 'false'" />
</template>

<script setup lang="ts">
/**
 * 像素方格背景（纯装饰）。
 * 静态底图只画一次；动画帧只重绘被点亮的方格：闲置时随机闪烁，鼠标附近逐渐亮起后慢慢褪色。
 * 页面隐藏时暂停；系统开启“减少动态效果”时只画静态图；只在可悬停的精确指针设备上响应鼠标。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

// focusX / focusY：方格最密处的相对位置（0–1），textEnd：左侧文案区大致结束的相对横坐标
const props = withDefaults(defineProps<{ cell?: number; gap?: number; radius?: number; focusX?: number; focusY?: number; textEnd?: number }>(), {
  cell: 10, gap: 4, radius: 120, focusX: 0.78, focusY: 0.4, textEnd: 0.6
})

interface Cell { x: number; y: number; tint: boolean; alpha: number }

const canvasRef = ref<HTMLCanvasElement>()
const running = ref(false)
let ctx: CanvasRenderingContext2D | null = null
let base: HTMLCanvasElement | null = null
let cells: Cell[] = []
let level = new Float32Array(0)
let target = new Float32Array(0)
let width = 0
let height = 0
let frame = 0
let pointer: { x: number; y: number } | null = null
let observer: ResizeObserver | undefined
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches

const smoothstep = (a: number, b: number, v: number) => {
  const t = Math.min(1, Math.max(0, (v - a) / (b - a)))
  return t * t * (3 - 2 * t)
}

// 方格分布：右上方最密，向四周渐隐；左侧文案区域进一步稀疏
function weightAt(x: number, y: number) {
  const dx = x / width - props.focusX
  const dy = y / height - props.focusY
  const radial = 1 - smoothstep(0.15, 0.8, Math.hypot(dx, dy * 1.2))
  const textZone = 0.25 + 0.75 * smoothstep(props.textEnd * 0.35, props.textEnd, x / width)
  // 窄屏时文案铺满宽度，整体再稀疏一些
  const narrow = width < 600 ? 0.55 : 1
  return radial * textZone * narrow
}

function build() {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  width = Math.max(1, Math.round(rect.width))
  height = Math.max(1, Math.round(rect.height))
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = width * dpr
  canvas.height = height * dpr
  ctx = canvas.getContext('2d')
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0)

  const pitch = props.cell + props.gap
  cells = []
  for (let y = props.gap; y < height; y += pitch) {
    for (let x = props.gap; x < width; x += pitch) {
      const w = weightAt(x, y)
      if (Math.random() < w * 0.9) cells.push({ x, y, tint: Math.random() < 0.08 * w + 0.02, alpha: 0.35 + Math.random() * 0.55 * w })
    }
  }
  level = new Float32Array(cells.length)
  target = new Float32Array(cells.length)

  // 静态底图：灰色方格 + 少量淡蓝方格
  base = document.createElement('canvas')
  base.width = canvas.width
  base.height = canvas.height
  const b = base.getContext('2d')
  if (!b) return
  b.setTransform(dpr, 0, 0, dpr, 0, 0)
  for (const c of cells) {
    b.fillStyle = c.tint ? `rgba(147, 180, 255, ${c.alpha})` : `rgba(229, 231, 235, ${c.alpha})`
    b.fillRect(c.x, c.y, props.cell, props.cell)
  }
  draw()
}

function draw() {
  if (!ctx || !base) return
  ctx.clearRect(0, 0, width, height)
  ctx.drawImage(base, 0, 0, width, height)
  for (let i = 0; i < cells.length; i++) {
    const v = level[i]
    if (v < 0.02) continue
    // 亮起时从浅蓝过渡到主色
    const r = Math.round(147 + (43 - 147) * v)
    const g = Math.round(180 + (90 - 180) * v)
    const bl = Math.round(255 + (230 - 255) * v)
    ctx.fillStyle = `rgba(${r}, ${g}, ${bl}, ${0.25 + 0.65 * v})`
    ctx.fillRect(cells[i].x, cells[i].y, props.cell, props.cell)
  }
}

function step() {
  frame = 0
  if (document.hidden) { running.value = false; return }
  // 闲置闪烁：每帧随机点亮极少数方格
  for (let k = 0; k < 2; k++) {
    if (cells.length && Math.random() < 0.35) target[Math.floor(Math.random() * cells.length)] = 0.35 + Math.random() * 0.35
  }
  const r2 = props.radius * props.radius
  for (let i = 0; i < cells.length; i++) {
    if (pointer) {
      const dx = cells[i].x - pointer.x
      const dy = cells[i].y - pointer.y
      const d2 = dx * dx + dy * dy
      if (d2 < r2) target[i] = Math.max(target[i], 1 - Math.sqrt(d2) / props.radius)
    }
    level[i] += (target[i] - level[i]) * 0.14
    target[i] *= 0.94
  }
  draw()
  frame = requestAnimationFrame(step)
}

function start() {
  if (reduceMotion || frame || document.hidden) return
  running.value = true
  frame = requestAnimationFrame(step)
}

function stop() {
  if (frame) cancelAnimationFrame(frame)
  frame = 0
  running.value = false
}

const onPointer = (event: PointerEvent) => {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  pointer = x >= 0 && y >= 0 && x <= rect.width && y <= rect.height ? { x, y } : null
}
const onLeave = () => { pointer = null }
const onVisibility = () => { if (document.hidden) stop(); else start() }

onMounted(() => {
  build()
  if (reduceMotion) return
  observer = new ResizeObserver(() => build())
  if (canvasRef.value) observer.observe(canvasRef.value)
  document.addEventListener('visibilitychange', onVisibility)
  if (finePointer) {
    window.addEventListener('pointermove', onPointer, { passive: true })
    document.documentElement.addEventListener('pointerleave', onLeave)
  }
  start()
})

onBeforeUnmount(() => {
  stop()
  observer?.disconnect()
  document.removeEventListener('visibilitychange', onVisibility)
  window.removeEventListener('pointermove', onPointer)
  document.documentElement.removeEventListener('pointerleave', onLeave)
})
</script>

<style scoped>
.pixel-field { position: absolute; inset: 0; width: 100%; height: 100%; display: block; pointer-events: none; }
</style>
