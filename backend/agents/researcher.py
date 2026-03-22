# -*- coding: utf-8 -*-
"""
研究员智能体
职责：分析市场需求和可行性
"""

from typing import List, Dict, Any
from agents.base_agent import BaseAgent, AgentContext
from llm.client import get_client
from prompts import RESEARCHER_SYSTEM_PROMPT, RESEARCHER_USER_PROMPT, FALLBACK_RESPONSES


class ResearcherAgent(BaseAgent):
    """研究员智能体"""

    name = "研究员"
    agent_type = "researcher"

    def __init__(self):
        super().__init__()
        self._client = None

    def initialize(self):
        super().initialize()
        self._client = get_client()

    def system_prompt(self) -> str:
        return RESEARCHER_SYSTEM_PROMPT

    def build_user_prompt(self, context: AgentContext) -> str:
        return RESEARCHER_USER_PROMPT.format(requirement=context.requirement_content)

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
        return f"【市场与需求分析】\n\n{result}"

    def get_fallback_response(self, context: AgentContext) -> str:
        return f"【市场与需求分析】\n\n{FALLBACK_RESPONSES['researcher'].format(requirement=context.requirement_content[:50])}"
