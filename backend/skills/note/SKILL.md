---
name: note-app
description: 笔记应用，支持创建、编辑、删除笔记
triggers: [笔记, 备忘录, note, memo, 记事本, 便签]
craft_requires: [anti-ai-slop, accessibility-baseline, typography]
---

## 核心功能

1. **新建笔记** — 标题输入 + 新建按钮
2. **编辑笔记** — 点击笔记卡片进入编辑模式
3. **删除笔记** — 删除按钮，确认后删除
4. **卡片网格** — 响应式卡片网格布局显示所有笔记
5. **时间戳** — 显示创建/更新时间
6. **LocalStorage 持久化** — 数据本地存储

## 设计要点

- 卡片网格布局，响应式 1-3 列
- 每张卡片显示标题、内容预览、时间戳
- 删除按钮 hover 时才显示
- 空状态时显示引导文案
