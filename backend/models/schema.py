# -*- coding: utf-8 -*-
"""
Schema 验证模块
使用 Pydantic 验证代码生成输出
"""

from typing import List, Optional, Literal, Tuple, Union, Any
from pydantic import BaseModel, Field, field_validator


class CodeFile(BaseModel):
    """代码文件 Schema"""

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="文件名",
        examples=["index.html", "style.css", "script.js"]
    )

    content: str = Field(
        ...,
        min_length=0,
        description="文件内容"
    )

    status: Literal['pending', 'generating', 'completed', 'modified', 'error'] = Field(
        default='pending',
        description="文件状态"
    )

    total_lines: int = Field(
        default=0,
        ge=0,
        description="总行数"
    )

    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """验证文件名"""
        # 检查文件扩展名
        allowed_extensions = ['html', 'css', 'js', 'json', 'md', 'txt']
        if '.' not in v:
            raise ValueError("文件名必须包含扩展名")
        ext = v.split('.')[-1].lower()
        if ext not in allowed_extensions:
            raise ValueError(f"不支持的文件扩展名：{ext}，允许的扩展名：{allowed_extensions}")
        return v

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str, info) -> str:
        """验证内容"""
        # 如果状态是 completed，内容不能为空
        if info.data.get('status') == 'completed' and not v.strip():
            raise ValueError("完成的文件内容不能为空")
        return v

    def model_post_init(self, __context) -> None:
        """初始化后处理"""
        # 自动计算行数
        if self.total_lines == 0 and self.content:
            self.total_lines = len(self.content.splitlines())


class CodeGenerationResponse(BaseModel):
    """代码生成响应 Schema"""

    files: List[CodeFile] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="生成的代码文件列表"
    )

    requirement_id: Optional[int] = Field(
        default=None,
        description="关联的需求 ID"
    )

    success: bool = Field(
        default=True,
        description="是否成功生成"
    )

    error_message: Optional[str] = Field(
        default=None,
        description="错误消息"
    )

    @field_validator('files')
    @classmethod
    def validate_files(cls, v: List[CodeFile]) -> List[CodeFile]:
        """验证文件列表"""
        # 检查是否有重复的文件名
        filenames = [f.filename for f in v]
        if len(filenames) != len(set(filenames)):
            raise ValueError("文件名不能重复")

        # 必须包含至少一个代码文件
        code_files = [f for f in v if f.filename.endswith(('.html', '.css', '.js'))]
        if not code_files:
            raise ValueError("必须包含至少一个代码文件（.html/.css/.js）")

        return v


class AgentOutput(BaseModel):
    """智能体输出 Schema"""

    agent_name: str = Field(..., description="智能体名称")
    agent_type: Literal['researcher', 'product_manager', 'architect', 'engineer'] = Field(
        ..., description="智能体类型"
    )
    success: bool = Field(default=True, description="是否成功")
    output: str = Field(..., description="输出内容")
    error: Optional[str] = Field(default=None, description="错误消息")
    elapsed_seconds: float = Field(default=0, ge=0, description="执行耗时（秒）")


# ==================== 验证函数 ====================

def validate_code_files(files: list) -> Tuple[bool, Union[list, str]]:
    """
    验证代码文件列表

    Args:
        files: 代码文件列表

    Returns:
        (是否成功，验证后的文件列表或错误消息)
    """
    try:
        response = CodeGenerationResponse(files=files)
        return True, [f.model_dump() for f in response.files]
    except Exception as e:
        return False, str(e)


def parse_code_generation_response(content: str) -> Tuple[bool, Union[list, str]]:
    """
    解析并验证代码生成响应

    Args:
        content: LLM 返回的原始内容（可能是 JSON 字符串）

    Returns:
        (是否成功，解析后的文件列表或错误消息)
    """
    import json

    try:
        # 尝试提取 JSON
        content = content.strip()

        # 处理 markdown 代码块
        if content.startswith('```json'):
            content = content[7:]
        if content.endswith('```'):
            content = content[:-3]
        content = content.strip()

        # 解析 JSON
        data = json.loads(content)

        # 如果是列表，包装成响应
        if isinstance(data, list):
            response = CodeGenerationResponse(files=data)
            return True, [f.model_dump() for f in response.files]
        elif isinstance(data, dict):
            if 'files' in data:
                response = CodeGenerationResponse(**data)
                return True, [f.model_dump() for f in response.files]
            else:
                return False, "响应必须包含 'files' 字段"
        else:
            return False, f"无效的响应格式：{type(data)}"

    except json.JSONDecodeError as e:
        return False, f"JSON 解析失败：{str(e)}"
    except Exception as e:
        return False, f"验证失败：{str(e)}"
