# T01／T02 原型交付

最终交付为墨刀项目 `408agent` 中的 `T01_T02_交互原型` 可点击版。[演示入口与使用方法](原型设计展示链接.md)、[五项课程要求与验收记录](原型验收报告_v2.md)。

2026-11-05，用户确认已删除墨刀中的 `T01_T02_原生分层版`。本目录已移除对应原生底稿、生成脚本、过期转换说明及旧版 ZIP，只保留当前可点击版交付；不将原生分层初稿列为成果。

## 打开与目录

- 直接打开 [总演示入口](html/00_交互演示入口.html)，或将 [v2 导入文件](release/00_交互验收版_v2.html) 导入墨刀；两份内容一致。
- `html/`：20 个自包含入口；每份可独立运行，在同一份内部导航可连续演示。独立打开其他入口会新建演示状态。
- `source/`：交互脚本、附加样式、构建／打包脚本、浏览器检查脚本，以及 [仓库内静态底稿](source/snapshots/README.md)。
- `screenshots/` 与 JSON 报告：真实执行产生的本地／墨刀验收证据。报告环境与日期以各文件为准；历史截图可能仍显示清理前的原生分层画布条目，不表示当前仍保留该画布。
- [v2 交付包](T01_T02_墨刀交互原型_v2.zip)：包含本文档、源文件、底稿、成品、页面映射及验收证据，不包含 ZIP 本身、原生分层初稿或旧版 ZIP。

成品 HTML 不需要安装依赖，也不请求业务 API 或模型。所有业务状态均为模拟并保存在当前组件内存中，刷新后恢复初始状态。

## 重建与打包

在仓库根目录运行，只需 Python 3 标准库，无需安装 Python 第三方依赖：

```powershell
python -X utf8 docs/coursework-02/prototype/source/build.py
python -X utf8 docs/coursework-02/prototype/source/package.py
```

构建读取仓库内 `source/snapshots/templates.json`、`source/snapshots/styles.css` 和当前交互脚本／附加样式，生成 20 个 HTML、页面映射及 `release/` 导入文件。无需仓库外 `原型设计/prototype-export/`；完整交付包解压后也能运行 `python -X utf8 source/build.py` 与 `python -X utf8 source/package.py`。

本地重建不会更新墨刀线上组件。更改交互或样式后需重新验收并导入；本次文件整理已核对生成内容与先前验收版一致，无需重新导入。

本次本地整理检查见 [delivery-validation.json](delivery-validation.json)，记录内容一致性、交付包独立重建及链接检查；不替代前述业务原型验收。

## 可选浏览器复验

浏览器检查脚本另需仓库现有 `kaoyan-frontend/node_modules/playwright` 与 Microsoft Edge；这些是测试依赖，不是成品或构建依赖。仅有交付 ZIP 时不包含该前端依赖目录。

```powershell
node docs/coursework-02/prototype/source/acceptance.cjs
node docs/coursework-02/prototype/source/verify.cjs
node docs/coursework-02/prototype/source/verify-public-v2.cjs
```

前两项检查本地成品，最后一项访问墨刀分享链接。`public-validation.json` 和 `source/verify-public.cjs` 为早期分享检查历史；当前 v2 分享验收以 `public-acceptance-validation.json` 为准。
