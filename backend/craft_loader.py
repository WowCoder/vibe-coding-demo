# -*- coding: utf-8 -*-
"""
Craft 规则加载器
从 craft/ 目录加载设计质量规则，注入到代码生成 Prompt
"""

from pathlib import Path
from typing import List, Optional
from config import get_settings

# 可用的 Craft 规则名列表
AVAILABLE_CRAFTS = ['anti-ai-slop', 'accessibility-baseline', 'typography', 'color']

# 缓存已加载的规则内容
_cache: dict = {}


def _get_craft_dir() -> Path:
    """获取 craft 目录路径"""
    return Path(__file__).parent / 'craft'


def load_craft_rules(names: Optional[List[str]] = None) -> str:
    """
    加载指定 Craft 规则并拼接为 Prompt 片段

    Args:
        names: 规则名称列表，None 或空列表表示全部加载

    Returns:
        拼接后的规则文本，可直接注入 System Prompt
    """
    if names is None:
        names = AVAILABLE_CRAFTS

    craft_dir = _get_craft_dir()
    sections = []

    for name in names:
        if name not in AVAILABLE_CRAFTS:
            continue

        # 缓存
        if name not in _cache:
            filepath = craft_dir / f'{name}.md'
            if filepath.exists():
                _cache[name] = filepath.read_text(encoding='utf-8')
            else:
                continue

        sections.append(_cache[name])

    if not sections:
        return ''

    return '\n\n---\n\n'.join(sections)


def is_craft_enabled() -> bool:
    """检查 Craft 规则是否启用"""
    settings = get_settings()
    return getattr(settings, 'LLM_CRAFT_ENABLED', True)


def get_default_craft_names() -> List[str]:
    """获取默认启用的 Craft 规则名列表"""
    return ['anti-ai-slop', 'accessibility-baseline', 'typography']
