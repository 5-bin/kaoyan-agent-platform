# 导出字体

Noto Sans SC，SIL Open Font License 1.1，许可证见 OFL.txt。
来源：https://github.com/notofonts/noto-cjk/tree/main/Sans/Variable/TTF/Subset

原文件 NotoSansSC-VF.ttf；使用 fonttools 4.60.1 将 wght 固定为400，生成静态 TrueType 字体供 PDFBox 及 Java2D 使用。497个共享轮廓的Unicode别名分配独立字形编号，避免PDFBox反向映射把普通汉字提取为部首码点；轮廓及全部原字符映射保留。

重建入口为仓库 scripts/prepare-export-font.py，显式传入上游文件和新的输出路径；它不下载字体、不覆盖已有输出。fonttools仅是维护工具，不是服务运行依赖。

Word按ECMA-376的obfuscatedFont规范嵌入OFL字体，PDF嵌入所需子集；不依赖运行时下载或维护者机器上的字体。阅读器的字体嵌入支持可能不同，实际验证范围见导出验证记录。
