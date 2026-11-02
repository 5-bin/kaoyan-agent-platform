# 学情画像可视化验证（2026-10-31）

本文 `.cache/` 下的日志与截图仅供本机追溯，不随公开仓库分发。

本轮把 `/stat` 的学情画像从“文字摘要 + 表格”扩展为图表展示。范围为**前端展示层**：未修改 Java、Python Agent、数据库、画像算法或 `/learning/profile` 接口。

## 实现内容

- [LearningProfilePanel](../kaoyan-frontend/src/components/LearningProfilePanel.vue)：组合 KPI、热力图、证据散点、优先补强、科目证据、画像历史，并保留完整数据表作为回退。
- [ProfileKpi](../kaoyan-frontend/src/components/learning-profile/ProfileKpi.vue)：参考分、蓝图覆盖、独立证据、画像状态和证据构成。
- [MasteryHeatmap](../kaoyan-frontend/src/components/learning-profile/MasteryHeatmap.vue)：知识点×难度热力图；样本少于 5 条使用灰色虚框和“样本不足”，不显示掌握结论。
- [EvidenceScatter](../kaoyan-frontend/src/components/learning-profile/EvidenceScatter.vue)：独立样本数×掌握指数；点大小表示蓝图权重，异常点红色描边，标出样本阈值和 60% 参考线。
- [WeakPointRanking](../kaoyan-frontend/src/components/learning-profile/WeakPointRanking.vue)：优先补强前 6 项；样本不足单列“待验证”，不以“薄弱”表述。
- [SubjectCards](../kaoyan-frontend/src/components/learning-profile/SubjectCards.vue)：科目级独立正确/错误/辅助/未知分段和蓝图覆盖。
- [ProfileHistory](../kaoyan-frontend/src/components/learning-profile/ProfileHistory.vue)：按画像版本的参考分/覆盖变化；版本稀疏时不宣称连续趋势。
- [profile-data.ts](../kaoyan-frontend/src/components/learning-profile/profile-data.ts)：纯派生函数（分档、Top N、科目汇总、历史点、HTML 转义）。
- [ChartFrame](../kaoyan-frontend/src/components/learning-profile/ChartFrame.vue)：ECharts 生命周期、`ResizeObserver`、空状态和文字摘要。
- [lib/echarts.ts](../kaoyan-frontend/src/lib/echarts.ts)：ECharts 按需注册；[Statistics.vue](../kaoyan-frontend/src/views/Statistics.vue) 同时改用该共享入口。

## 初次可视化实际验证（2026-10-31）

环境：本机 macOS，前端依赖已安装；Playwright 使用本机 Chrome（`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`），生产构建预览，不连接日常 MySQL/Redis/Agent。

| 检查 | 实际结果 |
| --- | --- |
| `npm run build` | 通过（Vue/TS + Vite 生产构建）；仍有既有大 chunk 提示，Statistics 约 649 kB、index 约 1.13 MB |
| `npx playwright test tests/learning-profile-visual.spec.ts` | 8 项通过（desktop 4 + mobile 4） |
| `npx playwright test` 全量 | 222 项通过，约 3.0 分钟 |
| 图表/数据夹具 | 5 个知识点，独立样本 0/3/6/8/10，含异常点、`referenceScore=112`、`coverage=68%`、辅助/未知样本 |
| 失败场景 | `/learning/profile/history` 返回 500 时，当前画像和图表仍可用，历史图隐藏 |
| 样本不足场景 | 参考分为空显示“证据不足”；补强区提示“暂无独立样本达到 5 条”；不生成虚构分数 |
| 移动端 | 390 宽度无横向溢出；KPI 两列、图表单列；桌面 1280 正常 |
| 回退 | 展开“查看完整数据表”可读取科目、知识点、难度、样本、掌握指数和建议；图表有文字摘要 |

测试使用合成画像夹具，不读取真实用户画像；未调用模型、Java 或 MySQL。已人工查看桌面/手机截图，确认热力图顺序、散点图例、空状态和移动端 KPI 布局。

## 未运行与限制

- **未运行**：真实 Java `/learning/profile` 数据联调、真实用户画像屏幕阅读器审计、视觉回归基线、性能 profiling；未运行 Java `mvnw verify` 与 Python pytest（本轮未改后端/Agent，不需要）。
- 图表为 ECharts canvas，已提供文字摘要和数据表，但这不等于完整 WCAG 审计；颜色不是唯一编码，样本不足有文字/虚框。
- 派生科目汇总和优先排序只用于展示，不写回画像；`referenceScore` 仍是实验性、未经整卷校准。
- 未新增 API、数据库迁移、模型调用或第三方图表服务；后端如需“按科目/难度的蓝图覆盖格”或服务端聚合，需另行更新 DTO 与契约。

## 布局修复与最终复验（2026-11-01）

以上保留初次可视化记录；本节是后续布局修复的实际结果，不沿用此前的测试数量。

### 实现与职责

本轮实际调用本机安装的 DeepSeek Harness 0.2.1-rc.5 配套 CLI，以独立 headless 任务使用桌面已有的 `deepseek-account / deepseek-flash` 配置。在不含 `.env`、后端或业务数据的隔离源码副本中生成改动，随后由 Codex 检查差异、合入并完成浏览器复验。Harness 阶段完成类型检查和使用 Vite `runner` 配置加载器的隔离生产构建；合入后标准 `npm run build` 也已通过。认证由 Harness 管理，未输出凭据。

- [ChartFrame](../kaoyan-frontend/src/components/learning-profile/ChartFrame.vue)：统一“标题/操作 → 绘图区 → 卡片内图例 → 摘要”，新增可选 `legend` 插槽；监听配置、高度和空状态变化，在 DOM 更新后同步 ECharts 尺寸；观察器通知按动画帧合并，卸载和空状态时释放图表与监听。
- [MasteryHeatmap](../kaoyan-frontend/src/components/learning-profile/MasteryHeatmap.vue)：补齐匹配系列的隐藏分段 `visualMap`，保持原有分档、颜色与样本阈值；图例移入卡片，最多12行且高度随行数变化；灰色格区分“未诊断”和“样本不足”，缺少对应难度证据时不生成数据格。长标签使用 ECharts 原生轴提示显示完整名称，提示可换行并限制宽度；审查后移除了 Harness 初稿的自定义浮层和事件绑定。
- [EvidenceScatter](../kaoyan-frontend/src/components/learning-profile/EvidenceScatter.vue)：横轴名称底部居中并留出64px，科目图例移至卡片内；保留科目色、权重大小、异常描边及参考线，并以可聚焦按钮保留科目隐藏/显示交互。
- [LearningProfilePanel](../kaoyan-frontend/src/components/LearningProfilePanel.vue)：移除强制百分比高度；网格按内容布局并允许子项收缩，统一内边距和间距，窄屏操作换行。接口、画像算法、排序与统计口径保持原样。
- [回归测试](../kaoyan-frontend/tests/learning-profile-visual.spec.ts)：新增卡片内布局、图例与摘要不重叠、画布尺寸、真实像素颜色、数据格提示、长轴标签提示、12行与科目筛选、空状态切换及图例开关的检查。测试悬浮使用稳定的画布局部坐标，取色在悬浮高亮之前进行；Element Plus 选择器按实际可点击外框操作。

### 最终实际验证

环境：本机 macOS、Node 22.23.3、本机 Chrome；Playwright 使用独立浏览器上下文，业务 API 均以合成夹具拦截。未读取或修改日常账号、MySQL、Redis 或 Agent 数据。

| 检查 | 最终结果与范围 |
| --- | --- |
| `npm run build` | 通过，退出码0；Vue/TS及Vite标准生产构建成功，2480个模块；仍有既有大chunk提示（Statistics约651.96 kB、index约1.13 MB） |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npx playwright test tests/learning-profile-visual.spec.ts` | **14项通过**，desktop 7 + mobile 7，约10.9秒 |
| 独立开发/生产显示检查 | 生产预览与开发模式分别检查1280、1440、390宽度，**6组通过**；页面及控制台错误均为0，未出现热力图缺少visualMap的开发模式错误 |
| 真实绘制与提示 | Canvas像素检查覆盖掌握颜色与样本不足灰色；数据格样本/异常提示、长标签完整名称可见；开发模式通过ECharts公开API核对visualMap及实际颜色 |
| 筛选与尺寸 | 12行切换到单科6行，六组环境均从494px降至278px；canvas与容器尺寸一致，均位于卡片内部，无页面横向溢出 |
| 空数据与失败 | 无分组、全未诊断、全样本不足、空↔非空刷新、历史接口500均通过；缺少证据不编造参考分，历史失败不影响当前画像 |
| 人工视觉检查 | 已查看1440桌面双图、390手机热力图/散点图截图；图例和摘要处于绘图区下方，横轴标题位于图内，完整表格回退与助手入口保留 |

本机临时验证脚本、尺寸/颜色记录及截图位于 `.cache/profile-display-20261101-harness/`，未纳入版本控制。截图使用合成画像，不能作为真实用户学情或学习效果证明：

- 桌面双图截图（本机 `.cache/profile-display-20261101-harness/production-1440-charts.png`）
- 手机热力图截图（本机 `.cache/profile-display-20261101-harness/production-390-heatmap.png`）
- 手机散点图截图（本机 `.cache/profile-display-20261101-harness/production-390-scatter.png`）
- 六组开发/生产检查数据（本机 `.cache/profile-display-20261101-harness/checks.json`）

### 未运行与生效边界

- **未运行**：真实 Java `/learning/profile` 联调、真实用户画像、全量前端回归、屏幕阅读器与性能专项；Java `mvnw verify`、Python pytest未运行（本轮未改后端/Agent）。
- 未发起业务模型请求、数据库迁移、提交、推送或部署；本轮 Harness 编码调用与业务 Agent 模型调用分别记录，不混为领域效果验证。
- 未重启或停止日常服务；本次独立前端预览、开发实例及浏览器已在检查结束后关闭。日常5173如仍返回旧模块，应在另行允许重启前端服务后复查，不把隔离预览当作日常环境已经生效。

## ECharts 6 升级后续（2026-11-02）

为关闭 `npm audit` 中危项，前端升级 echarts 5.6→6.1、vue-tsc 2→3.3、unplugin-auto-import 0.18→21.1、unplugin-vue-components 0.27→32.1（后两者要求 Node≥20.19），并在锁文件内升级 follow-redirects 1.16.2、vite 6.4.5。业务组件与 `lib/echarts.ts` 未改。

- **行为变化**：ECharts 6.1 的直角坐标热力图把数据格固定画在增量图层，同一图表由1个 canvas 变为3个叠放的图层 canvas（源码 `getIncrementalId` 默认开启，无配置可关闭）；散点与历史折线仍为1个。默认主题配色也有调整，学情图表多数颜色已显式指定，学习统计页折线使用新默认色。
- **测试调整**：[learning-profile-visual.spec.ts](../kaoyan-frontend/tests/learning-profile-visual.spec.ts) 改为检查“所有 canvas 属于同一图表根节点且尺寸与容器一致”，像素取样先按绘制顺序合成全部图层。热力图悬停在升级前后均会偶发丢失首次悬停（同一用例各重复20次：ECharts 5 失败3次、6 失败2次），改为未出现提示时移开并重新悬停，限时8秒。
- **实际验证**：`npm audit` 0项；生产构建通过；Playwright 隔离回归（生产预览、模拟接口、桌面1280／移动390）264项通过；该用例文件重复5轮70项通过；另以1280和390宽度截图人工查看热力图色带、灰色虚框、散点及参考线显示正常。
- **未运行**：真实后端联调、真实手机、其他浏览器；日常5173开发服务器仍运行升级前加载的模块，重启前端后才使用新依赖，本轮未重启。
- **已知限制（与升级无关）**：热力图左侧标签区固定116px，390宽度下绘图区仅约80px，三列格子较窄，待另行优化。
