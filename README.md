# 多人访谈视频剪辑 Skill

把真实多人录制围绕一个问题，整理成保留原声与互动的主题切片，并完成对应的自媒体发布材料。

默认交付包括：

- 完整主题视频：真实前三秒钩子、自然口条精剪、清楚的发言者身份、有依据的镜头与语义图解、同步字幕关键词放大。
- 中央漫画分格封面：3:4、4:3、16:9分别构图；主问题、必要副文、真实产品Logo依次分组，字体与图标保持自然比例。
- 中文、英文、中英双语三份同时间线SRT。
- 抖音、小红书、视频号、B站各自可复制的标题、正文／简介、话题及适用制作说明。
- 当前成片章节、文件用途说明与逐文件核验的发布ZIP。

每条视频重新确定主题、受众、人物、产品与文案。示例中的人数、标题、推荐产品和时码不是下一条的固定模板。局部返修遵守当次范围；上传、投稿和联系他人由当次明确授权决定。

## 安装与使用

将本仓库克隆到支持Skill的助手所使用的skills目录。以Codex默认目录为例：

```sh
git clone https://github.com/xupengli406-del/edit-multi-person-interview-video.git ~/.codex/skills/edit-multi-person-interview-video
```

在助手中提供本期真实视频或已有工程，并说：

> 使用多人访谈视频剪辑 Skill，把这段录制按一个主题剪成完整切片，并交付中央漫画封面和完整发布包。

主入口为 [SKILL.md](SKILL.md)。完整封面要求见 [中央漫画分格封面](references/comic-panel-cover.md)，交付与检查见 [交付规范](references/qa-delivery-cleanup.md)。

## 工具与输入

- 提供可用的真实录音／视频、准确人物资料及必要身份参考。实际人物照片、录音、字体、官方Logo和成片留在各自项目，不随本仓库分发。
- 视频编辑与渲染使用当次可用的工具，由执行助手读取对应工具流程。原声时间轴检查脚本适用于同帧率、原速CFR工程，具体边界见 [时钟规范](references/audio-and-timeline.md)。
- `scripts/cover_overlay.py`需要Python 3与Pillow，接受本期原生画幅底图、获授权字体、真实PNG标识和实际人物保护区；按需先将官方SVG转换成透明PNG。它负责自然字形与标识图层、实测边界及布局保护。
- `scripts/inline-emphasis.mjs`和`two-line-header.mjs`为可集成的字幕及标题组件，集成方法见对应参考；实际视频仍需导出后检查。

此工作流可配合以下已发布Skill使用：

- [真人口播制作](https://github.com/xupengli406-del/edit-talking-head-social-video)
- [社媒封面制作](https://github.com/xupengli406-del/produce-social-media-cover)
- [画面节奏增强](https://github.com/xupengli406-del/enhance-voiceover-video-rhythm)

本Skill已选的中央漫画封面优先于泛用封面流程中的其他默认方向；用户当前明确要求始终优先。

## 检查与留档

原图和手机尺寸实际查看，核对身份、脸与手、文字自然比例、Logo来源、阅读顺序、留白和三比例适配；视频另检查原声、开头、剪口、字幕强调与收尾。代码检查、哈希、解码、实际观看、用户接受和平台发布分别记录。

本仓库提供流程、可复用参数与辅助组件，不携带任何具体访谈成片、照片、音频、品牌媒体或机器专属配置。
