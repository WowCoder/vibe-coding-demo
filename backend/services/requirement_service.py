# -*- coding: utf-8 -*-
"""
需求管理服务
封装 AI 智能体协同处理需求的业务逻辑
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from models import SessionLocal, Requirement
from utils.logger import get_logger
from utils import get_current_timestamp, SSEMessage
from services.sse_manager import sse_manager
from agents.base_agent import AgentContext, AgentResult
from agents.researcher import ResearcherAgent
from agents.product_manager import ProductManagerAgent
from agents.architect import ArchitectAgent
from agents.engineer import EngineerAgent

logger = get_logger(__name__)


class RequirementService:
    """需求管理服务"""

    def __init__(self):
        # 智能体实例
        self.researcher = ResearcherAgent()
        self.product_manager = ProductManagerAgent()
        self.architect = ArchitectAgent()
        self.engineer = EngineerAgent()

    def process_requirement(self, requirement_id: int) -> bool:
        """
        处理需求：执行 AI 多智能体协同流程

        Args:
            requirement_id: 需求 ID

        Returns:
            是否成功完成
        """
        db = SessionLocal()
        try:
            requirement = db.query(Requirement).filter(Requirement.id == requirement_id).first()
            if not requirement:
                logger.error(f"需求不存在：{requirement_id}")
                return False

            # 如果需求已经完成或正在处理中，跳过
            if requirement.status in ['finished', 'processing']:
                logger.info(f"需求 {requirement_id} 状态为 {requirement.status}，跳过处理")
                return False

            # 更新状态为处理中
            requirement.status = 'processing'
            db.commit()
            logger.info(f"需求 {requirement_id} 开始处理")

            # 智能体协同执行
            agent_outputs: List[Dict[str, str]] = []

            # 构建上下文
            context = AgentContext(
                requirement_id=requirement_id,
                requirement_content=requirement.content,
                dialogue_history=requirement.dialogue_history or [],
                code_files=requirement.code_files or []
            )

            # 1. 研究员智能体
            logger.info("研究员智能体开始工作...")
            self._send_progress(requirement_id, '研究员', 25)
            result = self.researcher.execute(context)
            agent_outputs.append(result.to_dict())
            self._save_agent_result(db, requirement, '研究员', result)
            self._send_dialogue(requirement_id, '研究员', result.output)

            # 更新上下文
            context.previous_outputs.append(result.to_dict())

            # 2. 产品经理智能体
            logger.info("产品经理智能体开始工作...")
            self._send_progress(requirement_id, '产品经理', 50)
            result = self.product_manager.execute(context)
            agent_outputs.append(result.to_dict())
            self._save_agent_result(db, requirement, '产品经理', result)
            self._send_dialogue(requirement_id, '产品经理', result.output)

            # 更新上下文
            context.previous_outputs.append(result.to_dict())

            # 3. 架构师智能体
            logger.info("架构师智能体开始工作...")
            self._send_progress(requirement_id, '架构师', 75)
            result = self.architect.execute(context)
            agent_outputs.append(result.to_dict())
            self._save_agent_result(db, requirement, '架构师', result)
            self._send_dialogue(requirement_id, '架构师', result.output)

            # 更新上下文
            context.previous_outputs.append(result.to_dict())

            # 4. 工程师智能体
            logger.info("工程师智能体开始工作...")
            self._send_progress(requirement_id, '工程师', 90)
            result = self.engineer.execute(context)
            agent_outputs.append(result.to_dict())
            self._send_dialogue(requirement_id, '工程师', result.output)

            # 解析并保存代码文件
            self._send_progress(requirement_id, '完成', 100)
            try:
                code_files = json.loads(result.output)
                if isinstance(code_files, list):
                    requirement.code_files = code_files
                    logger.info(f"保存了 {len(code_files)} 个代码文件")
                    # 发送代码 SSE 消息
                    for file_data in code_files:
                        filename = file_data.get('filename', 'unknown.txt')
                        content = file_data.get('content', '')
                        self._send_code(requirement_id, filename, content)
            except Exception as e:
                logger.error(f"解析代码文件失败：{e}")
                requirement.code_files = []

            # 更新状态为完成
            requirement.status = 'finished'
            db.commit()
            logger.info(f"需求 {requirement_id} 处理完成")

            # 发送完成通知
            self._send_complete(requirement_id)

            return True

        except Exception as e:
            logger.error(f"处理需求时发生异常：{e}", exc_info=True)
            try:
                requirement.status = 'failed'
                db.commit()
            except:
                pass
            return False

        finally:
            db.close()

    def _save_agent_result(self, db, requirement: Requirement, agent_name: str, result: AgentResult):
        """保存智能体输出到对话历史"""
        dialogue = requirement.dialogue_history or []
        dialogue.append({
            'role': 'agent',
            'name': agent_name,
            'content': result.output,
            'timestamp': get_current_timestamp(),
            'status': 'completed' if result.success else 'failed',
            'error': result.error
        })
        requirement.dialogue_history = dialogue

        # 标记修改
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(requirement, 'dialogue_history')
        db.commit()

    def _send_progress(self, requirement_id: int, agent_name: str, progress: int):
        """发送进度更新消息"""
        message = SSEMessage.progress_message(agent_name, progress, 'processing')
        sse_manager.broadcast(str(requirement_id), message)

    def _send_dialogue(self, requirement_id: int, name: str, content: str):
        """发送对话消息"""
        message = SSEMessage.dialogue_message('agent', name, content, get_current_timestamp())
        sse_manager.broadcast(str(requirement_id), message)

    def _send_code(self, requirement_id: int, filename: str, content: str):
        """发送代码消息"""
        message = SSEMessage.code_message(filename, content, 0, True)
        sse_manager.broadcast(str(requirement_id), message)

    def _send_complete(self, requirement_id: int):
        """发送完成通知"""
        message = SSEMessage.complete_message(requirement_id)
        sse_manager.broadcast(str(requirement_id), message)


# 全局服务实例
requirement_service = RequirementService()


def process_requirement_async(requirement_id: int):
    """
    异步处理需求（在线程中执行）

    Args:
        requirement_id: 需求 ID
    """
    service = RequirementService()
    return service.process_requirement(requirement_id)
