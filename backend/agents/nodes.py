# -*- coding: utf-8 -*-
"""
LangGraph 智能体节点函数
每个节点接收 AgentState，返回部分状态更新
"""

import json
import re
from typing import Dict, Any, List, Union, Tuple

from agents.state import AgentState
from llm.client import get_client
from prompts import PLANNER_PROMPT, ENGINEER_PROMPT, generate_fallback_code
from craft_loader import load_craft_rules, is_craft_enabled, get_default_craft_names
from skill_loader import match_skill, get_skill_fallback
from utils.logger import get_logger

logger = get_logger(__name__)


# ==================== 辅助函数 ====================

def extract_json_from_response(content: str) -> Tuple[bool, Union[list, str]]:
    """从响应中提取 JSON，兼容 Artifact 新格式和旧格式"""
    try:
        parsed = json.loads(content)
        # 新 Artifact 格式: {"artifact": {...}, "files": [...]}
        if isinstance(parsed, dict) and 'files' in parsed:
            return True, parsed['files']
        # 旧格式: [{"filename": ...}, ...]
        return True, parsed
    except json.JSONDecodeError:
        # 尝试提取 JSON 块
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            try:
                return True, json.loads(match.group())
            except:
                pass
        return False, "JSON 解析失败"


# ==================== 智能体节点 ====================

def _is_vague_requirement(text: str) -> bool:
    """检测需求是否过于模糊"""
    text = text.strip()
    # 已经过一轮澄清的跳过
    if '[用户补充说明]' in text:
        return False
    if len(text) < 30:
        return True
    # 检测是否包含功能关键词
    action_keywords = ['做', '开发', '实现', '创建', '设计', '添加', '支持', '显示', '生成']
    feature_keywords = ['功能', '页面', '按钮', '列表', '表单', '输入', '点击', '显示', '保存', '数据']
    has_action = any(k in text for k in action_keywords)
    has_feature = any(k in text for k in feature_keywords)
    return not (has_action and has_feature)


def _generate_clarify_questions(client, requirement: str) -> list:
    """生成澄清问题表单"""
    prompt = f"""用户提出需求："{requirement}"
这个需求比较模糊。请生成 2-3 个关键澄清问题。

以 JSON 数组格式返回，每个问题包含：
- id: 问题ID
- type: "radio" 或 "text"
- label: 问题文本
- options: ["选项1", "选项2"] (仅 radio 类型需要)

例如：
[{{"id": "q1", "type": "radio", "label": "你想做什么类型的应用？", "options": ["工具类", "展示类", "数据管理类"]}}]

只返回 JSON 数组，不要其他文字。"""

    response = client.chat(
        prompt=prompt,
        system_prompt="你是一位产品经理，帮助澄清模糊的用户需求。",
        use_memory=False,
        max_tokens=500,
        timeout=20
    )
    if response.is_error or not response.content:
        return []
    try:
        return json.loads(response.content)
    except json.JSONDecodeError:
        # 尝试提取 JSON 数组
        match = re.search(r'\[.*\]', response.content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
    return []


def planner_node(state: AgentState) -> Dict[str, Any]:
    """
    Planner 节点：合并研究员、产品经理、架构师职责，产出结构化 Plan
    """
    logger.info(f"[Planner] 开始分析需求：{state['requirement_id']}")

    # 3.1 需求评估：模糊需求触发澄清
    requirement = state['requirement_content']
    clarify_round = state.get('metadata', {}).get('clarify_round', 0)

    if _is_vague_requirement(requirement) and clarify_round < 1:
        try:
            client = get_client()
            questions = _generate_clarify_questions(client, requirement)
            if questions:
                logger.info(f"[Planner] 需求模糊，生成 {len(questions)} 个澄清问题")
                return {
                    'plan': {},
                    'current_step': 'needs_clarification',
                    'dialogue_history': [{
                        'role': 'system',
                        'name': 'Planner',
                        'content': '需求不够明确，需要你补充一些信息',
                        'status': 'needs_clarification'
                    }],
                    'metadata': {
                        'planner_success': True,
                        'question_form': {'questions': questions},
                        'clarify_round': clarify_round
                    }
                }
        except Exception as e:
            logger.warning(f"[Planner] 澄清问题生成失败：{e}，继续正常流程")

    try:
        client = get_client()
        messages = PLANNER_PROMPT.format_messages(requirement=state['requirement_content'])
        system_prompt = next((m.content for m in messages if m.type == 'system'), None)
        user_prompt = next((m.content for m in messages if m.type == 'human'), None)

        response = client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            use_memory=False,
            max_tokens=2000,
            timeout=45
        )

        if response.is_error:
            raise Exception(response.error)

        # 解析 JSON
        plan = extract_json_from_response(response.content)
        if not plan[0]:  # 解析失败
            plan_result = {'features': [], 'tech_stack': {}, 'data_model': [], 'file_structure': [], 'implementation_notes': []}
        else:
            plan_result = plan[1] if plan[0] else {}

        # 匹配 Skill
        skill = match_skill(state['requirement_content'])
        if skill and skill.name != 'generic-app':
            plan_result['matched_skill'] = skill.name

        return {
            'plan': plan_result,
            'current_step': 'planner_done',
            'dialogue_history': [{
                'role': 'agent',
                'name': 'Planner',
                'content': '已完成需求分析和架构设计',
                'status': 'completed'
            }],
            'metadata': {'planner_success': True}
        }

    except Exception as e:
        logger.error(f"[Planner] 执行失败：{e}")
        return {
            'plan': {},
            'current_step': 'planner_failed',
            'error': f"Planner 失败：{e}",
            'dialogue_history': [{
                'role': 'agent',
                'name': 'Planner',
                'content': f"分析失败，使用简化版：{state['requirement_content'][:50]}...",
                'status': 'failed'
            }],
            'metadata': {'planner_success': False}
        }


def engineer_node(state: AgentState) -> Dict[str, Any]:
    """
    工程师节点：根据 Planner 的 Plan 生成代码
    """
    logger.info(f"[工程师] 开始生成代码：{state['requirement_id']}")

    try:
        client = get_client()

        # 使用 Planner 输出的 plan 作为上下文
        plan = state.get('plan', {})
        plan_context = json.dumps(plan, ensure_ascii=False, indent=2) if plan else '请根据需求生成代码'

        # 加载 Craft 设计质量规则
        craft_rules = ''
        if is_craft_enabled():
            matched_skill = state.get('plan', {}).get('matched_skill', '')
            rules = load_craft_rules(get_default_craft_names())
            if rules:
                craft_rules = f"\n\n## 设计质量规范（必须遵守）\n\n{rules}"

        messages = ENGINEER_PROMPT.format_messages(
            requirement=state['requirement_content'],
            context=plan_context,
            craft_rules=craft_rules
        )
        system_prompt = next((m.content for m in messages if m.type == 'system'), None)
        user_prompt = next((m.content for m in messages if m.type == 'human'), None)

        response = client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            use_memory=False,
            max_tokens=4000,
            timeout=60
        )

        if not response.content or response.is_error:
            raise Exception(response.error or "无响应")

        # 解析 JSON
        success, result = extract_json_from_response(response.content)

        if success:
            code_files = result if isinstance(result, list) else []
            return {
                'code_files': code_files,
                'current_step': 'engineer_done',
                'dialogue_history': [{
                    'role': 'agent',
                    'name': 'Coder',
                    'content': '代码生成完成',
                    'status': 'completed'
                }],
                'metadata': {'engineer_success': True}
            }
        else:
            # JSON 解析失败，使用 fallback
            code_files = generate_fallback_code(state['requirement_content'])
            return {
                'code_files': code_files,
                'current_step': 'engineer_fallback',
                'error': f"代码解析失败：{result}",
                'dialogue_history': [{
                    'role': 'agent',
                    'name': 'Coder',
                    'content': '代码生成完成（使用模板）',
                    'status': 'completed'
                }],
                'metadata': {'engineer_success': False}
            }

    except Exception as e:
        logger.error(f"[工程师] 执行失败：{e}")
        # 优先使用 Skill 的 Fallback 模板，否则回退到旧硬编码模板
        skill_fallback = get_skill_fallback(state['requirement_content'])
        code_files = skill_fallback if skill_fallback else generate_fallback_code(state['requirement_content'])

        return {
            'code_files': code_files,
            'current_step': 'engineer_failed',
            'error': f"工程师失败：{e}",
            'dialogue_history': [{
                'role': 'agent',
                'name': 'Coder',
                'content': '代码生成完成（使用模板）',
                'status': 'fallback'
            }],
            'metadata': {'engineer_success': False}
        }
