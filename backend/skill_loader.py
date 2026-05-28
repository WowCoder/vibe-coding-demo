# -*- coding: utf-8 -*-
"""
Skill 模板加载器
从 skills/ 目录加载应用类型模板，提供匹配和 Fallback 代码获取
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Skill:
    """Skill 定义"""
    name: str
    description: str
    triggers: List[str]
    craft_requires: List[str]
    body: str  # Markdown body below frontmatter
    fallback_templates: Optional[List[dict]] = None  # 从 template.json 加载

    def matches(self, requirement: str) -> bool:
        """关键词匹配"""
        requirement_lower = requirement.lower()
        return any(t.lower() in requirement_lower for t in self.triggers)


# 全局 Skill 缓存
_skills: Optional[Dict[str, Skill]] = None


def _get_skills_dir() -> Path:
    return Path(__file__).parent / 'skills'


def _parse_frontmatter(text: str) -> tuple:
    """解析 YAML 前导元数据 (简易解析，避免引入 pyyaml 仅用于 skill 解析)"""
    if not text.startswith('---'):
        return {}, text

    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', text, re.DOTALL)
    if not match:
        return {}, text

    frontmatter_str = match.group(1)
    body = match.group(2).strip()

    metadata = {}
    current_key = None
    for line in frontmatter_str.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip()
            if value.startswith('[') and value.endswith(']'):
                # 列表类型: [a, b, c]
                items = [v.strip().strip('"').strip("'") for v in value[1:-1].split(',') if v.strip()]
                metadata[key] = items
            else:
                metadata[key] = value.strip('"').strip("'")
            current_key = key
        elif current_key and line.startswith('- '):
            # 多行列表项
            if current_key not in metadata:
                metadata[current_key] = []
            metadata[current_key].append(line[2:].strip())

    return metadata, body


def load_all_skills() -> Dict[str, Skill]:
    """加载所有 Skill"""
    global _skills
    if _skills is not None:
        return _skills

    _skills = {}
    skills_dir = _get_skills_dir()

    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_file = skill_dir / 'SKILL.md'
        if not skill_file.exists():
            continue

        text = skill_file.read_text(encoding='utf-8')
        metadata, body = _parse_frontmatter(text)

        name = metadata.get('name', skill_dir.name)
        triggers = metadata.get('triggers', [])
        if isinstance(triggers, str):
            triggers = [triggers]

        # 加载 Fallback 模板
        fallback = None
        template_json = skill_dir / 'template.json'
        if template_json.exists():
            try:
                fallback = json.loads(template_json.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                logger.warning(f"Skill {name}: template.json 格式错误")

        skill = Skill(
            name=name,
            description=metadata.get('description', ''),
            triggers=triggers,
            craft_requires=metadata.get('craft_requires', []),
            body=body,
            fallback_templates=fallback
        )
        _skills[name] = skill

    logger.info(f"已加载 {len(_skills)} 个 Skill")
    return _skills


def match_skill(requirement: str) -> Skill:
    """
    根据用户需求匹配最合适的 Skill

    匹配策略：关键词匹配，匹配到多个时选 trigger 匹配最多的
    都匹配不到时返回 generic
    """
    skills = load_all_skills()
    requirement_lower = requirement.lower()

    best_match = None
    best_score = 0

    for name, skill in skills.items():
        if name == 'generic-app':
            continue  # 最后才考虑 generic

        score = sum(1 for t in skill.triggers if t.lower() in requirement_lower)
        if score > best_score:
            best_score = score
            best_match = skill

    if best_match is None or best_score == 0:
        return skills.get('generic-app')

    return best_match


def get_skill_fallback(requirement: str) -> Optional[List[dict]]:
    """
    获取匹配 Skill 的 Fallback 代码模板
    如果 Skill 没有 template.json，返回 None（需要 LLM 生成）
    """
    skill = match_skill(requirement)
    if skill.fallback_templates:
        return skill.fallback_templates
    return None


def get_skill_craft_names(requirement: str) -> List[str]:
    """获取匹配 Skill 需要的 Craft 规则名"""
    skill = match_skill(requirement)
    return skill.craft_requires if skill else []
