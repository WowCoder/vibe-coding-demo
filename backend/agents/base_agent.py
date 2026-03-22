# -*- coding: utf-8 -*-
"""
AI 智能体基类
定义智能体的通用接口和基础功能
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Generator

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AgentContext:
    """智能体上下文"""
    requirement_id: int
    requirement_content: str
    previous_outputs: List[Dict[str, str]] = field(default_factory=list)
    dialogue_history: List[Dict[str, Any]] = field(default_factory=list)
    code_files: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class AgentResult:
    """智能体执行结果"""
    agent_name: str
    success: bool
    output: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'agent_name': self.agent_name,
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'metadata': self.metadata
        }


class BaseAgent(ABC):
    """AI 智能体基类"""

    # 子类必须定义的属性
    name: str = ""  # 智能体名称（中文）
    agent_type: str = ""  # 智能体类型（英文）

    def __init__(self):
        self._initialized = False
        self.logger = get_logger(f"agents.{self.agent_type}")

    def initialize(self):
        """初始化智能体（子类可覆盖）"""
        self._initialized = True
        self.logger.debug(f"{self.name} 智能体已初始化")

    @abstractmethod
    def system_prompt(self) -> str:
        """返回系统提示词"""
        pass

    @abstractmethod
    def build_user_prompt(self, context: AgentContext) -> str:
        """构建用户提示词"""
        pass

    def preprocess(self, context: AgentContext) -> AgentContext:
        """预处理上下文（子类可覆盖）"""
        return context

    def postprocess(self, result: str, context: AgentContext) -> str:
        """后处理结果（子类可覆盖）"""
        return result

    def execute(self, context: AgentContext) -> AgentResult:
        """
        执行智能体任务

        Args:
            context: 上下文信息

        Returns:
            AgentResult 对象
        """
        start_time = datetime.now()
        self.logger.info(f"{self.name} 智能体开始执行：requirement_id={context.requirement_id}")

        try:
            # 初始化
            if not self._initialized:
                self.initialize()

            # 预处理
            context = self.preprocess(context)

            # 构建提示词
            system_prompt = self.system_prompt()
            user_prompt = self.build_user_prompt(context)

            # 调用 LLM（子类实现）
            output = self._call_llm(system_prompt, user_prompt)

            # 后处理
            output = self.postprocess(output, context)

            # 检查输出是否有效
            if output.startswith('[错误]'):
                raise RuntimeError(f"LLM 返回错误：{output}")

            elapsed = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"{self.name} 智能体执行完成：elapsed={elapsed:.2f}s")

            return AgentResult(
                agent_name=self.name,
                success=True,
                output=output,
                metadata={'elapsed_seconds': elapsed}
            )

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            self.logger.error(f"{self.name} 智能体执行失败：error={error_msg}, elapsed={elapsed:.2f}秒")

            # 使用 fallback 响应
            fallback_output = self.get_fallback_response(context)

            return AgentResult(
                agent_name=self.name,
                success=False,
                output=fallback_output,
                error=error_msg,
                metadata={'elapsed_seconds': elapsed}
            )

    @abstractmethod
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM 获取响应（子类必须实现）"""
        pass

    @abstractmethod
    def get_fallback_response(self, context: AgentContext) -> str:
        """返回 fallback 响应（当 LLM 失败时）"""
        pass

    def stream_execute(self, context: AgentContext) -> Generator[str, None, None]:
        """
        流式执行（可选实现）

        Args:
            context: 上下文信息

        Yields:
            文本片段
        """
        # 默认实现：非流式
        result = self.execute(context)
        yield result.output
