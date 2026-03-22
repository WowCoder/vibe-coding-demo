# 持续对话改代码功能改进 Checklist

## 问题背景

当前代码生成后的持续对话修改功能存在以下问题：

1. **LangGraph 集成断裂** - chat 接口未使用 LangGraph workflow
2. **Diff 解析可靠性差** - 上下文匹配失败时静默失败
3. **用户感知弱** - 不知道哪些文件被修改
4. **会话记忆缺失** - AI 不记住之前的修改历史

---

## 修改清单

### 阶段一：Diff 可靠性修复（优先级：高）

| # | 任务 | 涉及文件 | 修改内容 | 预期效果 |
|---|------|----------|----------|----------|
| 1.1 | 增加 Diff 应用结果验证 | `diff_utils.py` | `apply_diff()` 返回 `(new_content, success, error_msg)` 三元组 | 调用方能知道是否成功 |
| 1.2 | 增加 Diff 应用失败回滚 | `app.py:chat_with_requirement` | 如果 diff 应用失败，保留原代码并返回错误提示 | 避免错误修改代码 |
| 1.3 | 增加 LLM Diff 格式校验 | `app.py:chat_with_requirement` | 在应用 diff 前验证格式正确性 | 减少解析失败 |
| 1.4 | 增加失败日志和告警 | `app.py`, `diff_utils.py` | 记录 diff 应用失败的详细信息 | 便于问题排查 |

**预计工作量**: 2 小时
**风险等级**: 低
**测试要点**:
- 故意传入错误的 diff 验证不会破坏原代码
- 验证错误消息能正确返回前端

---

### 阶段二：会话记忆增强（优先级：高）

| # | 任务 | 涉及文件 | 修改内容 | 预期效果 |
|---|------|----------|----------|----------|
| 2.1 | 传递对话历史给 LLM | `app.py:chat_with_requirement` | `use_memory=False` → 传入 `dialogue_history[-10:]` 到 prompt | AI 能记住上下文 |
| 2.2 | 优化 prompt 模板 | `prompts.py` | `CODE_EDIT_USER_PROMPT` 增加 `recent_changes` 字段 | 更清晰的修改请求 |
| 2.3 | 支持代码版本感知 | `app.py:chat_with_requirement` | 在 prompt 中说明"这是第 N 次修改" | AI 理解修改迭代 |
| 2.4 | 保存修改摘要 | `models.py` | Requirement 模型增加 `modification_summary` 字段 | 追踪修改历史 |

**预计工作量**: 2 小时
**风险等级**: 低
**测试要点**:
- 连续多次对话，AI 能引用之前的修改
- 验证 prompt 包含完整上下文

---

### 阶段三：用户感知提升（优先级：中）

| # | 任务 | 涉及文件 | 修改内容 | 预期效果 |
|---|------|----------|----------|----------|
| 3.1 | API 返回修改文件列表 | `app.py:chat_with_requirement` | 返回 `{updated_files: [...]}` | 前端知道哪些文件变了 |
| 3.2 | 前端显示修改提示 | `detail.html` | 收到 `updated_files` 后显示 Toast 或角标 | 用户直观感知修改 |
| 3.3 | 修改文件高亮 | `detail.html:renderFileTabs` | 被修改的文件加"modified"角标 | 快速定位修改 |
| 3.4 | 支持撤销修改 | `app.js` + `app.py` | 新增 `/api/requirements/<id>/undo` 接口 | 用户可以回滚 |

**预计工作量**: 3 小时
**风险等级**: 中
**测试要点**:
- Toast 显示正确
- 撤销功能恢复上一版本

---

### 阶段四：LangGraph 集成（优先级：中）

| # | 任务 | 涉及文件 | 修改内容 | 预期效果 |
|---|------|----------|----------|----------|
| 4.1 | 创建 Chat 模式 Workflow | `agents/chat_workflow.py` | 简化版 workflow，只调用 engineer 节点 | 统一架构 |
| 4.2 | 增加 CodeReview 节点 | `agents/nodes.py` | 新增 `code_review_node` 审查 diff 安全性 | 提高代码质量 |
| 4.3 | 修改 chat 接口集成 workflow | `app.py:chat_with_requirement` | 替换 `client.chat()` → `workflow.invoke()` | 统一技术栈 |
| 4.4 | 支持智能体路由 | `agents/chat_workflow.py` | 根据用户意图路由到不同节点（架构师/工程师） | 更智能的响应 |

**预计工作量**: 6 小时
**风险等级**: 中
**测试要点**:
- workflow 执行正常
- CodeReview 能检测简单错误

---

### 阶段五：增强功能（优先级：低）

| # | 任务 | 涉及文件 | 修改内容 | 预期效果 |
|---|------|----------|----------|----------|
| 5.1 | 版本快照 | `models.py` | 新增 `RequirementVersion` 模型 | 保存每次修改快照 |
| 5.2 | 版本历史 UI | `detail.html` | 新增"历史版本"侧边栏 | 查看和对比历史 |
| 5.3 | Diff 可视化 | `detail.html` | 使用 diff-match-patch 展示代码对比 | 直观看到改动 |
| 5.4 | 协作冲突检测 | `app.py` | 检测同时修改的冲突 | 支持多人协作 |

**预计工作量**: 8 小时
**风险等级**: 低
**测试要点**:
- 版本历史正确保存
- Diff 可视化正常渲染

---

## 实施计划

### 第一批（本次迭代）- 阶段一 + 阶段二

**目标**: 修复可靠性问题，增强会话记忆

**任务列表**:
- [ ] 1.1 Diff 应用结果验证
- [ ] 1.2 Diff 应用失败回滚
- [ ] 1.3 LLM Diff 格式校验
- [ ] 1.4 失败日志和告警
- [ ] 2.1 传递对话历史给 LLM
- [ ] 2.2 优化 prompt 模板
- [ ] 2.3 代码版本感知

**预计时间**: 4 小时
**风险**: 低

---

### 第二批（下次迭代）- 阶段三

**目标**: 提升用户体验

**任务列表**:
- [ ] 3.1 API 返回修改文件列表
- [ ] 3.2 前端显示修改提示
- [ ] 3.3 修改文件高亮
- [ ] 3.4 支持撤销修改（可选）

**预计时间**: 3 小时
**风险**: 中

---

### 第三批（未来迭代）- 阶段四 + 阶段五

**目标**: LangGraph 深度集成和增强功能

**任务列表**:
- [ ] 4.1 Chat 模式 Workflow
- [ ] 4.2 CodeReview 节点
- [ ] 4.3 chat 接口集成 workflow
- [ ] 5.1 版本快照（可选）
- [ ] 5.2 版本历史 UI（可选）
- [ ] 5.3 Diff 可视化（可选）

**预计时间**: 14 小时
**风险**: 中

---

## 技术细节

### 1.1 Diff 应用结果验证

```python
# diff_utils.py
def apply_diff(original_content: str, diff_file: DiffFile) -> tuple[str, bool, str]:
    """
    Returns:
        (new_content, success, error_message)
    """
    try:
        # ... 现有逻辑
        return new_content, True, ""
    except Exception as e:
        return original_content, False, f"Diff 应用失败：{str(e)}"
```

### 2.1 对话历史传递

```python
# app.py
# 构建对话上下文（最近 10 轮）
recent_dialogues = dialogue_history[-10:]
context = []
for msg in recent_dialogues:
    role = "用户" if msg['role'] == 'user' else "AI"
    context.append(f"{role}: {msg['content']}")

user_prompt = CODE_EDIT_USER_PROMPT.format(
    requirement=requirement.content,
    current_code=current_code,
    user_message=user_message,
    recent_changes='\n'.join(context)  # 新增
)
```

### 3.1 API 返回修改文件列表

```python
# app.py:chat_with_requirement
return jsonify({
    'message': 'success',
    'dialogue_history': dialogue_history,
    'code_files': requirement.code_files,
    'updated_files': updated_files,  # 新增
    'ai_response': ai_response
})
```

---

## 验收标准

### 阶段一验收
- [ ] 传入错误 diff 不会破坏原代码
- [ ] 前端能收到明确的错误提示
- [ ] 日志中能查到失败详情

### 阶段二验收
- [ ] 连续对话 3 轮，AI 能引用前文
- [ ] prompt 中包含完整的对话历史

### 阶段三验收
- [ ] 用户能看到"已修改：index.html"提示
- [ ] 文件 tab 有修改角标
- [ ] （可选）撤销功能正常

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Diff 解析破坏代码 | 低 | 高 | 回滚机制 + 测试用例 |
| LangGraph 集成破坏现有流程 | 中 | 中 | 保留 fallback 逻辑 |
| 前端改动引入 bug | 低 | 低 | 充分测试 |

---

## 决策点

请确认以下决策：

1. **是否本次迭代完成阶段一 + 阶段二？**
   - 建议：是（优先级高，风险低）

2. **阶段三（用户感知）是否一起完成？**
   - 建议：是（用户体验提升明显）

3. **阶段四（LangGraph 集成）是否推迟到下次迭代？**
   - 建议：是（需要更多设计和测试）

4. **阶段五（版本历史等增强）是否作为可选功能？**
   - 建议：是（锦上添花，非必需）

---

## 审核确认

请回复确认以下内容：

- [ ] 同意阶段一 + 阶段二立即实施
- [ ] 同意阶段三的实施优先级
- [ ] 同意阶段四 + 阶段五推迟
- [ ] 有其他建议或补充
