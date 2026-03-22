# -*- coding: utf-8 -*-
"""
工程师智能体
职责：生成代码
"""

import json
from typing import List, Dict

from agents.base_agent import BaseAgent, AgentContext
from llm.client import get_client
from prompts import (
    ENGINEER_SYSTEM_PROMPT,
    ENGINEER_USER_PROMPT,
    ENGINEER_CONTEXT_PROMPT,
    generate_fallback_code
)


class EngineerAgent(BaseAgent):
    """工程师智能体"""

    name = "工程师"
    agent_type = "engineer"

    def __init__(self):
        super().__init__()
        self._client = None

    def initialize(self):
        super().initialize()
        self._client = get_client()

    def system_prompt(self) -> str:
        return ENGINEER_SYSTEM_PROMPT

    def preprocess(self, context: AgentContext) -> AgentContext:
        # 压缩上下文，提取关键信息
        context = self._compress_context(context)
        return context

    def build_user_prompt(self, context: AgentContext) -> str:
        context_text = self._build_context(context)
        return ENGINEER_USER_PROMPT.format(
            requirement=context.requirement_content,
            context=context_text
        )

    def _build_context(self, context: AgentContext) -> str:
        """构建上下文"""
        if not context.previous_outputs:
            return "请根据需求生成代码。"

        compressed = self._compress_agent_outputs(context.previous_outputs)
        return compressed

    def _compress_agent_outputs(self, agent_outputs: List[Dict[str, str]]) -> str:
        """压缩智能体输出，提取关键信息"""
        compressed = []
        keywords = ['功能清单', '核心功能', '技术栈', '数据结构', '组件设计', '页面结构', '交互逻辑']

        for output in agent_outputs:
            name = output.get('agent_name', 'Unknown')
            content = output.get('output', '')

            extracted_lines = []
            for line in content.split('\n'):
                line = line.strip()
                if line and any(kw in line for kw in keywords):
                    extracted_lines.append(line)
                elif line.startswith('-') or (line and line[0].isdigit()):
                    extracted_lines.append(line)

            if len('\n'.join(extracted_lines)) < 200:
                extracted = content[:500] + '...' if len(content) > 500 else content
            else:
                extracted = '\n'.join(extracted_lines[:30])

            compressed.append(f"{name}: {extracted}")

        return '\n\n'.join(compressed)

    def _compress_context(self, context: AgentContext) -> AgentContext:
        """压缩上下文"""
        if context.previous_outputs:
            context.previous_outputs = [
                {'agent_name': o.get('agent_name'), 'output': o.get('output', '')[:1000]}
                for o in context.previous_outputs
            ]
        return context

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        # 第一次尝试
        response = self._client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            use_memory=False,
            max_tokens=4000,
            timeout=30
        )

        # 如果失败，使用简化 prompt 重试
        if response.is_error or not response.content:
            self.logger.warning("第一次尝试失败，使用简化 prompt 重试...")
            simple_prompt = f"""请为以下需求生成完整的 Web 应用代码：

用户需求：{context.requirement_content}

要求：
1. 生成 index.html、style.css、script.js 三个文件
2. 代码完整可运行，实现核心功能
3. 使用原生 HTML/CSS/JavaScript
4. 数据使用 LocalStorage 持久化

请以 JSON 数组格式返回：[{{"filename": "index.html", "content": "..."}}, ...]
只返回 JSON，不要其他解释文字。"""

            response = self._client.chat(
                prompt=simple_prompt,
                system_prompt=None,
                use_memory=False,
                max_tokens=4000,
                timeout=30
            )

        # 如果还是失败，返回错误
        if response.is_error or not response.content:
            return json.dumps(generate_fallback_code(context.requirement_content), ensure_ascii=False)

        return response.content

    def postprocess(self, result: str, context: AgentContext) -> str:
        # 验证 JSON 格式
        try:
            code_files = json.loads(result)
            if isinstance(code_files, list):
                # 验证每个文件的结构
                for f in code_files:
                    if 'filename' not in f or 'content' not in f:
                        raise ValueError("代码文件格式不正确")
        except json.JSONDecodeError:
            # 尝试提取 JSON
            import re
            match = re.search(r'\[.*\]', result, re.DOTALL)
            if match:
                try:
                    code_files = json.loads(match.group())
                    return json.dumps(code_files, ensure_ascii=False)
                except:
                    pass
            return json.dumps(generate_fallback_code(context.requirement_content), ensure_ascii=False)

        return result

    def get_fallback_response(self, context: AgentContext) -> str:
        fallback_code = generate_fallback_code(context.requirement_content)
        return json.dumps(fallback_code, ensure_ascii=False)
