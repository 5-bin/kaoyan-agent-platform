<template>
  <div class="wrap">
    <!-- 整页共用的像素方格与柔光，左右两侧连成一体；均对读屏隐藏 -->
    <PixelField class="page-pixels" :focus-x="0.56" :focus-y="0.45" :text-end="0.36" />
    <span class="page-glow" aria-hidden="true" />

    <section class="stage" aria-label="平台介绍">
      <!-- 3D 球体：经纬线自转；外圈倾斜轨道上科目标签公转，转到背面时被球体遮住 -->
      <div class="orbit" aria-hidden="true">
        <div class="tilt">
          <span class="ring r1" />
          <span class="ring r2" />
          <span class="ring r3" />
          <div class="globe">
            <span class="globe-body" />
            <div class="globe-spin">
              <span v-for="m in 6" :key="m" class="meridian" :style="{ '--m': `${m * 30}deg` }" />
            </div>
            <span class="lat lat-mid" />
            <span class="lat lat-up" />
            <span class="lat lat-down" />
            <span class="globe-label">408</span>
          </div>
          <div class="spin">
            <span v-for="(s, i) in orbitSubjects" :key="s.name" class="planet" :style="{ '--a': `${i * 90 + 20}deg`, '--r': `${s.r}px` }">
              <span class="counter"><span class="face">{{ s.name }}</span></span>
            </span>
          </div>
        </div>
      </div>
      <div class="float-card" aria-hidden="true">
        <div class="fc-head"><span class="fc-tag">单选</span><span class="fc-sub">数据结构</span></div>
        <span class="fc-line w90" />
        <span class="fc-line w60" />
        <div class="fc-opt"><i>A</i><span class="fc-bar w50" /></div>
        <div class="fc-opt on"><i>B</i><span class="fc-bar w70" /><el-icon class="fc-check"><Check /></el-icon></div>
        <div class="fc-opt"><i>C</i><span class="fc-bar w40" /></div>
      </div>

      <div class="intro">
        <div class="brand reveal" style="--d: 0ms">
          <span class="mark">考</span>
          <span class="name">考研 Agent 平台</span>
        </div>
        <h1 class="display reveal" data-text="考研 Agent" style="--d: 100ms">考研 Agent</h1>
        <p class="typer reveal" style="--d: 220ms">
          <span class="sr-only">{{ phrases.join('、') }}</span>
          <span aria-hidden="true">{{ typed }}<span class="caret" /></span>
        </p>
        <p class="slogan reveal" style="--d: 320ms">{{ slogan }}</p>
        <p class="desc reveal" style="--d: 420ms">{{ desc }}</p>
        <ul v-if="features.length" class="dots">
          <li v-for="(f, i) in features" :key="f" class="reveal" :style="{ '--d': `${520 + i * 90}ms` }">
            <el-icon aria-hidden="true"><Check /></el-icon>{{ f }}
          </li>
        </ul>
      </div>
    </section>

    <main class="right">
      <div class="panel">
        <slot />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
/**
 * 登录 / 注册共用布局：左侧浅色品牌区（像素方格、渐变大标题、打字机、答题卡示意），右侧表单卡片。
 * 页面只通过默认插槽提供表单；左侧不放任何输入控件。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import PixelField from '@/components/PixelField.vue'
import { Check } from '@element-plus/icons-vue'

withDefaults(defineProps<{ slogan: string; desc: string; features?: string[] }>(), { features: () => [] })

const orbitSubjects = [
  { name: '数据结构', r: 205 },
  { name: '操作系统', r: 155 },
  { name: '计算机网络', r: 205 },
  { name: '计算机组成原理', r: 155 }
]

// 打字机：逐字打出、停留、逐字删除后切换下一条；减少动态效果时直接显示完整内容
const phrases = ['来源可查的课程习题', '错题自动归集', '实时解析', '按科目和难度抽题']
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
const typed = ref(reduceMotion ? phrases.join(' · ') : '')
let typerTimer = 0
function typeLoop(index = 0, length = 0, deleting = false) {
  const phrase = phrases[index]
  typed.value = phrase.slice(0, length)
  let next: () => void
  let delay: number
  if (!deleting && length < phrase.length) { next = () => typeLoop(index, length + 1); delay = 110 }
  else if (!deleting) { next = () => typeLoop(index, length, true); delay = 1600 }
  else if (length > 0) { next = () => typeLoop(index, length - 1, true); delay = 45 }
  else { next = () => typeLoop((index + 1) % phrases.length, 0); delay = 300 }
  typerTimer = window.setTimeout(next, delay)
}
onMounted(() => { if (!reduceMotion) typerTimer = window.setTimeout(() => typeLoop(), 600) })
onBeforeUnmount(() => window.clearTimeout(typerTimer))
</script>

<style scoped lang="scss">
.wrap {
  position: relative; overflow: hidden; isolation: isolate;
  min-height: 100vh; display: flex;
  background: linear-gradient(180deg, #ffffff 0%, #f5f8ff 100%);
}
/* 整页背景层：像素方格在最底，柔光在其上 */
.page-pixels { z-index: -2; }
.page-glow {
  position: absolute; z-index: -1; left: 38%; top: -200px; width: 760px; height: 600px; pointer-events: none;
  background: radial-gradient(closest-side, rgba(59, 130, 246, .13), transparent);
}

/* ---------- 左侧品牌区（背景透明，共用整页方格） ---------- */
.stage {
  position: relative; overflow: hidden; isolation: isolate; container-type: inline-size;
  flex: 1; min-width: 0; padding: 56px 64px; color: #111827;
  display: flex; flex-direction: column; justify-content: center;
}

/* 3D 球体与倾斜轨道：.tilt 把轨道平面放倒，标签用反向旋转抵消，始终正对屏幕 */
.orbit {
  position: absolute; right: 10px; bottom: -110px; width: 460px; height: 460px; z-index: -1;
  perspective: 1100px;
}
.tilt {
  position: absolute; inset: 0; transform-style: preserve-3d;
  transform: rotateX(64deg) rotateZ(-12deg);
}
.ring {
  position: absolute; left: 50%; top: 50%; border-radius: 50%;
  border: 1px solid rgba(43, 90, 230, .22); transform: translate(-50%, -50%);
}
.r1 { width: 250px; height: 250px; }
.r2 { width: 310px; height: 310px; border-style: dashed; border-color: rgba(43, 90, 230, .18); }
.r3 { width: 410px; height: 410px; }
.spin { position: absolute; inset: 0; transform-style: preserve-3d; animation: spin-z 40s linear infinite; }
.planet {
  position: absolute; left: 50%; top: 50%; transform-style: preserve-3d;
  transform: rotateZ(var(--a)) translateX(var(--r)) rotateZ(calc(-1 * var(--a)));
}
.counter { position: absolute; transform-style: preserve-3d; animation: spin-z 40s linear infinite reverse; }
.face {
  position: absolute; display: block; white-space: nowrap;
  translate: -50% -50%; transform: rotateZ(12deg) rotateX(-64deg);
  padding: 5px 12px; border-radius: 999px; font-size: 12px; font-weight: 600;
  color: var(--c-primary-deep); background: rgba(255, 255, 255, .92); border: 1px solid #dbe3f5;
  box-shadow: 0 8px 18px -10px rgba(30, 64, 175, .45);
}
@keyframes spin-z { to { transform: rotateZ(360deg); } }

/* 球体本身也放进 3D 平面，并用反向倾斜立起来，这样前后遮挡由浏览器按深度处理 */
.globe {
  position: absolute; left: 50%; top: 50%; width: 170px; height: 170px; margin: -85px 0 0 -85px;
  transform-style: preserve-3d; transform: rotateZ(12deg) rotateX(-64deg);
}
.globe-body {
  position: absolute; inset: 0; border-radius: 50%;
  background: radial-gradient(circle at 34% 28%, #ffffff 0%, #d6e3ff 22%, #6f98f5 58%, #2b5ae6 82%, #1f47c2 100%);
  box-shadow: 0 0 0 10px rgba(43, 90, 230, .06), 0 20px 60px -10px rgba(43, 90, 230, .55);
  animation: glow 4s ease-in-out infinite;
}
@keyframes glow { 50% { box-shadow: 0 0 0 16px rgba(43, 90, 230, .04), 0 20px 80px -6px rgba(43, 90, 230, .7); } }
.globe-spin { position: absolute; inset: 0; transform-style: preserve-3d; animation: spin-y 14s linear infinite; }
.meridian {
  position: absolute; inset: 0; border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, .55); transform: rotateY(var(--m));
}
@keyframes spin-y { to { transform: rotateY(360deg); } }
.lat { position: absolute; left: 50%; top: 50%; border-radius: 50%; border: 1px solid rgba(255, 255, 255, .45); }
.lat-mid { width: 170px; height: 170px; transform: translate(-50%, -50%) rotateX(90deg); }
.lat-up { width: 140px; height: 140px; transform: translate(-50%, -50%) translateY(-48px) rotateX(90deg); }
.lat-down { width: 140px; height: 140px; transform: translate(-50%, -50%) translateY(48px) rotateX(90deg); }
.globe-label {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%) translateZ(86px);
  font-size: 26px; font-weight: 800; letter-spacing: 1px; color: #fff;
  text-shadow: 0 2px 10px rgba(17, 39, 120, .45);
}

/* 答题卡示意：只用色条，不展示任何数据 */
.float-card {
  position: absolute; right: 56px; top: 14%; width: 220px; z-index: 0;
  padding: 16px; border-radius: 16px;
  background: #fff; border: 1px solid #e5e7eb;
  box-shadow: 0 1px 2px rgba(17, 24, 39, .04), 0 24px 48px -28px rgba(30, 64, 175, .45);
  animation: bob 6s ease-in-out infinite;
}
@keyframes bob { 50% { transform: translateY(-10px); } }
.fc-head { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; font-size: 12px; }
.fc-tag { padding: 2px 8px; border-radius: 999px; background: var(--c-primary-strong); color: #fff; font-weight: 700; }
.fc-sub { color: #6b7280; }
.fc-line, .fc-bar { display: block; height: 8px; border-radius: 6px; background: #e5e7eb; }
.fc-line { margin-bottom: 8px; }
.fc-opt {
  display: flex; align-items: center; gap: 8px; margin-top: 8px; padding: 6px 8px;
  border-radius: 10px; border: 1px solid #e5e7eb;
}
.fc-opt i {
  width: 18px; height: 18px; border-radius: 6px; display: grid; place-items: center;
  font-style: normal; font-size: 11px; font-weight: 700; background: #f3f4f6; color: #374151;
}
.fc-opt .fc-bar { height: 6px; }
.fc-opt.on { background: var(--c-primary-light); border-color: var(--c-primary-strong); }
.fc-opt.on i { background: var(--c-primary-strong); color: #fff; }
.fc-opt.on .fc-bar { background: #bfcef8; }
.fc-check { margin-left: auto; color: var(--c-primary-strong); }
.w90 { width: 90%; } .w70 { width: 70%; } .w60 { width: 60%; } .w50 { width: 50%; } .w40 { width: 40%; }

.intro { position: relative; z-index: 1; max-width: 500px; }
.brand { display: flex; align-items: center; gap: 10px; margin-bottom: 40px; }
.mark {
  width: 40px; height: 40px; border-radius: 11px; flex-shrink: 0; color: #fff;
  display: grid; place-items: center; font-weight: 700;
  background: linear-gradient(140deg, #4d7bff 0%, #2b5ae6 55%, #1f47c2 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .35), 0 8px 18px -8px rgba(43, 90, 230, .7);
}
.name { font-weight: 600; color: #374151; }

/* 超大标题：深色到主色的渐变字，悬停时轻微错位 */
.display {
  position: relative; display: inline-block; margin: 0 0 14px;
  font-size: 60px; line-height: 1.1; font-weight: 800; letter-spacing: 1px;
  background: linear-gradient(90deg, #111827 0%, #1f47c2 55%, #2b5ae6 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.display::before, .display::after {
  content: attr(data-text); position: absolute; inset: 0; pointer-events: none; opacity: 0;
  background: none; -webkit-text-fill-color: currentColor;
}
.display::before { color: #1f47c2; }
.display::after { color: #38bdf8; }
@media (hover: hover) {
  .display:hover::before { animation: glitch-a .32s steps(2) both; }
  .display:hover::after { animation: glitch-b .32s steps(2) both; }
}
@keyframes glitch-a {
  0% { opacity: .9; clip-path: inset(10% 0 55% 0); transform: translate(-3px, -1px); }
  50% { opacity: .9; clip-path: inset(60% 0 8% 0); transform: translate(3px, 1px); }
  100% { opacity: 0; clip-path: inset(0); transform: none; }
}
@keyframes glitch-b {
  0% { opacity: .8; clip-path: inset(55% 0 15% 0); transform: translate(3px, 1px); }
  50% { opacity: .8; clip-path: inset(15% 0 60% 0); transform: translate(-3px, -1px); }
  100% { opacity: 0; clip-path: inset(0); transform: none; }
}

.typer {
  min-height: 28px; margin: 0 0 18px;
  font-size: 18px; font-weight: 600; color: var(--c-primary-strong);
  font-family: ui-monospace, SFMono-Regular, Menlo, 'PingFang SC', monospace;
}
.caret {
  display: inline-block; width: 2px; height: 1.1em; margin-left: 3px; vertical-align: -3px;
  background: var(--c-primary-strong); animation: blink 1s steps(1) infinite;
}
@keyframes blink { 50% { opacity: 0; } }
.slogan { margin: 0 0 12px; font-size: 20px; font-weight: 700; letter-spacing: .3em; color: #111827; }
.desc { margin: 0 0 24px; font-size: 14px; line-height: 1.7; color: #4b5563; }
.dots { display: flex; flex-wrap: wrap; gap: 10px; margin: 0; padding: 0; list-style: none; font-size: 13px; }
.dots li {
  display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 999px;
  background: #fff; border: 1px solid #e5e7eb; color: #1f2937;
  box-shadow: 0 1px 2px rgba(17, 24, 39, .04);
}
.dots li .el-icon { color: var(--c-primary-strong); }

/* 入场：依次淡入上移 */
.reveal { opacity: 0; animation: rise .7s cubic-bezier(.2, .7, .2, 1) forwards; animation-delay: var(--d, 0ms); }
@keyframes rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }

/* ---------- 右侧表单区（表单内容来自页面插槽） ---------- */
.right {
  position: relative;
  width: 500px; flex-shrink: 0;
  display: grid; place-items: center; padding: 40px;
}
.panel {
  position: relative; width: 100%; max-width: 380px; padding: 36px 32px 28px;
  background: #fff; border: 1px solid #e5e7eb; border-radius: 24px;
  box-shadow: 0 1px 2px rgba(17, 24, 39, .04), 0 30px 60px -36px rgba(30, 64, 175, .4);
  animation: rise .7s cubic-bezier(.2, .7, .2, 1) .15s both;
}
.panel :slotted(.title) { font-size: 26px; margin: 0 0 6px; color: #111827; }
.panel :slotted(.sub) { color: var(--c-ink-2); margin: 0 0 28px; }
/* 按钮是 Element 组件根元素，:slotted 匹配不到，用 :deep */
.panel :deep(.btn) { width: 100%; margin-top: 4px; letter-spacing: 2px; }
.panel :slotted(.foot) { text-align: center; margin-top: 18px; color: var(--c-ink-2); font-size: 13px; }
.panel :deep(.el-input__wrapper) {
  border-radius: 12px; transition: box-shadow .15s ease;
}
.panel :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--c-primary-strong) inset, 0 0 0 4px rgba(43, 90, 230, .14);
}

/* 按左侧区域自身宽度决定装饰：太窄时不显示，避免压住文案 */
@container (max-width: 760px) {
  .float-card { display: none; }
}
@container (max-width: 600px) {
  .orbit { display: none; }
}
/* 矮屏（常见笔记本浏览器）：球体缩小下沉，避免碰到垂直居中的文案；再矮则不显示 */
@media (max-height: 780px) {
  .orbit { scale: .72; transform-origin: 100% 100%; bottom: -90px; }
}
@media (max-height: 620px) {
  .orbit { display: none; }
}
@media (max-width: 900px) {
  .wrap { flex-direction: column; }
  .stage { flex: none; padding: 36px 24px 48px; }
  .brand { margin-bottom: 24px; }
  .display { font-size: 44px; }
  .right { width: 100%; padding: 8px 16px 40px; }
  .panel { max-width: 440px; }
}
@media (max-width: 480px) {
  .stage { padding: 28px 20px 44px; }
  .display { font-size: 38px; }
  .typer { font-size: 16px; }
  .slogan { font-size: 17px; letter-spacing: .2em; }
  .panel { padding: 28px 20px 24px; }
}
@media (prefers-reduced-motion: reduce) {
  .float-card, .caret, .panel, .reveal, .display::before, .display::after,
  .spin, .counter, .globe-spin, .globe-body { animation: none !important; }
  .reveal { opacity: 1; }
  .caret { display: none; }
  .panel :deep(.el-input__wrapper) { transition: none; }
}
</style>
