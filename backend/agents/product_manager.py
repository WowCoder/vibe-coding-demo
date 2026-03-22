# -*- coding: utf-8 -*-
"""
产品经理智能体
职责：拆解需求，生成功能清单
"""

from agents.base_agent import BaseAgent, AgentContext
from llm.client import get_client
from prompts import PRODUCT_MANAGER_SYSTEM_PROMPT, PRODUCT_MANAGER_USER_PROMPT, FALLBACK_RESPONSES


class ProductManagerAgent(BaseAgent):
    """产品经理智能体"""

    name = "产品经理"
    agent_type = "product_manager"

    def __init__(self):
        super().__init__()
        self._client = None

    def initialize(self):
        super().initialize()
        self._client = get_client()

    def system_prompt(self) -> str:
        return PRODUCT_MANAGER_SYSTEM_PROMPT

    def build_user_prompt(self, context: AgentContext) -> str:
        return PRODUCT_MANAGER_USER_PROMPT.format(requirement=context.requirement_content)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat(
            prompt=user_prompt,
            system_prompt=system_prompt,
            use_memory=False,
            max_tokens=2000,
            timeout=45
        )
        return response.content

    def postprocess(self, result: str, context: AgentContext) -> str:
        return f"【产品功能规划】\n\n{result}"

    def get_fallback_response(self, context: AgentContext) -> str:
        return f"【产品功能规划】\n\n{FALLBACK_RESPONSES['product_manager'].format(requirement=context.requirement_content[:50])}"
