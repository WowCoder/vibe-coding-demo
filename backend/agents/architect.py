# -*- coding: utf-8 -*-
"""
架构师智能体
职责：设计技术方案
"""

from agents.base_agent import BaseAgent, AgentContext
from llm.client import get_client
from prompts import ARCHITECT_SYSTEM_PROMPT, ARCHITECT_USER_PROMPT, FALLBACK_RESPONSES


class ArchitectAgent(BaseAgent):
    """架构师智能体"""

    name = "架构师"
    agent_type = "architect"

    def __init__(self):
        super().__init__()
        self._client = None

    def initialize(self):
        super().initialize()
        self._client = get_client()

    def system_prompt(self) -> str:
        return ARCHITECT_SYSTEM_PROMPT

    def build_user_prompt(self, context: AgentContext) -> str:
        return ARCHITECT_USER_PROMPT.format(requirement=context.requirement_content)

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
        return f"【技术架构设计】\n\n{result}"

    def get_fallback_response(self, context: AgentContext) -> str:
        return f"【技术架构设计】\n\n{FALLBACK_RESPONSES['architect'].format(requirement=context.requirement_content[:50])}"
