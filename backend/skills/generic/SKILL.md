---
name: generic-app
description: 通用应用模板，当用户需求无法匹配到特定 Skill 时使用
triggers: []
craft_requires: [anti-ai-slop, accessibility-baseline, typography, color]
---

## 核心功能

根据用户需求自主设计功能，以下为通用约束：

1. **纯前端应用** — 不需要后端服务器
2. **LocalStorage 持久化** — 所有数据本地存储
3. **三个文件** — index.html、style.css、script.js
4. **原生技术** — HTML/CSS/JS，Tailwind CSS CDN

## 设计要点

- 根据需求内容自主决定布局和交互
- 保持设计简洁实用
- 所有交互元素必须可访问
