---
name: todo-app
description: 待办清单应用，支持任务的增删改查、筛选和状态管理
triggers: [待办, todo, 清单, 任务, task, 计划, 日程管理]
craft_requires: [anti-ai-slop, accessibility-baseline, typography]
---

## 核心功能

1. **添加任务** — 输入框 + 添加按钮，支持回车提交
2. **标记完成/取消** — 复选框切换完成状态
3. **删除任务** — 删除按钮，确认提示
4. **筛选显示** — 全部/未完成/已完成 三个筛选状态
5. **计数统计** — 显示总任务数和已完成数
6. **LocalStorage 持久化** — 刷新不丢失数据

## 设计要点

- 功能优先，布局清晰
- 筛选按钮有 active/inactive 视觉区分
- 完成任务有删除线样式
- 空列表时显示引导提示
