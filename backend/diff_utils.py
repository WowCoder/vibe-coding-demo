# -*- coding: utf-8 -*-
"""
Diff 工具函数
实现 unified diff 的解析和应用
"""

import re
from typing import List, Dict, Optional, Tuple


class DiffHunk:
    """表示一个 diff hunk（代码块）"""
    def __init__(self, old_start: int, old_count: int, new_start: int, new_count: int):
        self.old_start = old_start      # 原文件起始行号
        self.old_count = old_count      # 原文件行数
        self.new_start = new_start      # 新文件起始行号
        self.new_count = new_count      # 新文件行数
        self.lines = []                 # hunk 内的所有行

    def __repr__(self):
        return f"DiffHunk(old={self.old_start}-{self.old_start+self.old_count}, new={self.new_start}-{self.new_start+self.new_count})"


class DiffFile:
    """表示一个文件的 diff"""
    def __init__(self, filename: str):
        self.filename = filename
        self.hunks: List[DiffHunk] = []

    def __repr__(self):
        return f"DiffFile({self.filename}, {len(self.hunks)} hunks)"


def parse_diff(diff_text: str) -> List[DiffFile]:
    """
    解析 unified diff 文本

    支持解析格式：
    ```diff
    --- a/index.html
    +++ b/index.html
    @@ -1,5 +1,6 @@
     line1
    -old line
    +new line
    +added line
     line4
     line5
    ```
    """
    diff_files = []
    lines = diff_text.strip().split('\n')

    i = 0
    while i < len(lines):
        line = lines[i]

        # 跳过 markdown 代码块标记
        if line.startswith('```diff') or line.startswith('```'):
            i += 1
            continue
        if line == '```':
            i += 1
            continue

        # 查找文件头 --- a/filename
        if line.startswith('--- '):
            # 提取文件名
            old_file = line[4:].strip()
            if old_file.startswith('a/'):
                old_file = old_file[2:]

            # 读取 +++ b/filename
            i += 1
            if i < len(lines) and lines[i].startswith('+++ '):
                new_file = lines[i][4:].strip()
                if new_file.startswith('b/'):
                    new_file = new_file[2:]

                filename = new_file or old_file
                diff_file = DiffFile(filename)

                # 读取 hunks
                i += 1
                while i < len(lines):
                    hunk_line = lines[i]

                    # 遇到新的文件头或结束
                    if hunk_line.startswith('--- ') or hunk_line.startswith('```'):
                        break

                    # 解析 hunk 头 @@ -old_start,old_count +new_start,new_count @@
                    if hunk_line.startswith('@@'):
                        match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', hunk_line)
                        if match:
                            old_start = int(match.group(1))
                            old_count = int(match.group(2)) if match.group(2) else 1
                            new_start = int(match.group(3))
                            new_count = int(match.group(4)) if match.group(4) else 1

                            hunk = DiffHunk(old_start, old_count, new_start, new_count)

                            # 读取 hunk 内容
                            i += 1
                            while i < len(lines):
                                content_line = lines[i]
                                # 遇到新的 hunk 或文件头或结束
                                if (content_line.startswith('@@') or
                                    content_line.startswith('--- ') or
                                    content_line.startswith('```') or
                                    content_line.strip() == ''):
                                    break
                                hunk.lines.append(content_line)
                                i += 1

                            diff_file.hunks.append(hunk)
                        else:
                            i += 1
                    else:
                        i += 1

                diff_files.append(diff_file)
            else:
                i += 1
        else:
            i += 1

    return diff_files


def apply_diff(original_content: str, diff_file: DiffFile) -> Tuple[str, bool, str]:
    """
    将 diff 应用到原始内容，返回新内容

    Args:
        original_content: 原始代码内容
        diff_file: DiffFile 对象

    Returns:
        (new_content, success, error_message)
        - new_content: 修改后的内容（成功时）或原始内容（失败时）
        - success: 是否成功应用
        - error_message: 错误信息（成功时为空字符串）

    算法：
    1. 将原始内容按行分割
    2. 对每个 hunk，通过上下文匹配找到位置
    3. 从后往前应用变更，避免行号偏移
    """
    original_lines = original_content.split('\n')

    # 收集所有需要删除/添加的行
    all_changes = []
    has_changes = False

    for hunk in diff_file.hunks:
        # 解析 hunk 内容
        delete_lines = []  # (索引，内容)
        add_lines = []     # (索引，内容)
        context_lines = [] # (索引，内容)
        hunk_lines = []    # 原始 hunk 行，用于按顺序重建

        old_line_idx = 0  # 在 old 文件中的行索引（从 0 开始）
        new_line_idx = 0  # 在 new 文件中的行索引

        for line in hunk.lines:
            hunk_lines.append(line)
            if line.startswith('-'):
                delete_lines.append((old_line_idx, line[1:]))
                old_line_idx += 1
            elif line.startswith('+'):
                add_lines.append((new_line_idx, line[1:]))
                new_line_idx += 1
            elif line.startswith(' '):
                # 上下文行
                context_lines.append((old_line_idx, line[1:]))
                old_line_idx += 1
                new_line_idx += 1
            elif line == '':
                # 空行当作上下文
                context_lines.append((old_line_idx, ''))
                old_line_idx += 1
                new_line_idx += 1
            elif line.startswith('\\'):
                # "\ No newline at end of file" - 忽略
                pass

        if delete_lines or add_lines:
            has_changes = True

        all_changes.append({
            'hunk': hunk,
            'hunk_lines': hunk_lines,
            'delete': delete_lines,
            'add': add_lines,
            'context': context_lines,
            'old_start': hunk.old_start - 1  # 转为 0-based 索引
        })

    # 如果没有实际变更，返回原始内容
    if not has_changes:
        return original_content, False, "Diff 中没有实际的代码变更"

    # 从后往前应用变更，避免行号偏移
    for change in reversed(all_changes):
        old_start = change['old_start']
        delete_info = change['delete']
        add_info = change['add']
        context_info = change['context']

        # 找到 hunk 在原始内容中的实际位置
        actual_start = find_hunk_position_v2(original_lines, old_start, context_info, delete_info)

        if actual_start is None:
            # 无法匹配，返回错误
            return original_content, False, f"无法定位代码位置：文件 {diff_file.filename}, hunk 起始行 {old_start + 1}"

        # 验证删除的行是否匹配
        for rel_idx, content in delete_info:
            actual_idx = actual_start + rel_idx
            if 0 <= actual_idx < len(original_lines):
                if original_lines[actual_idx].strip() != content.strip():
                    return original_content, False, f"代码不匹配，无法删除第 {actual_idx + 1} 行"

        # 收集所有需要保留的上下文行及其位置
        # 然后构建新行列表
        # 策略：构建一个新的行列表，按顺序处理

        # 创建一个标记数组，标记哪些行需要删除
        to_delete = set(actual_start + idx for idx, _ in delete_info)

        # 创建添加行的映射：位置 -> 要添加的行列表
        # 添加行应该在对应的旧行索引之后添加
        # 在 unified diff 中，添加行的索引是新文件中的位置
        # 我们需要将它们转换为在旧文件中的相对位置

        # 简单方法：按顺序收集所有行
        # 1. 上下文行保留
        # 2. 删除行去掉
        # 3. 添加行插入到适当位置

        # 构建结果：遍历原始行，跳过要删除的，在适当位置插入新行
        # 添加行的位置是相对于 new 文件的，我们需要映射到旧文件位置

        # 更简单的方法：使用 hunk 行的顺序
        # 直接按 hunk 行顺序重建这个区域
        new_region = []
        hunk_line_idx = 0  # 在 hunk 中的位置
        old_line_idx = 0   # 在 old 文件中的位置

        # 遍历 hunk 行，按顺序构建新区域
        for line in change['hunk_lines']:
            if line.startswith(' '):
                # 上下文行：从原始内容获取
                actual_idx = actual_start + old_line_idx
                if 0 <= actual_idx < len(original_lines):
                    new_region.append(original_lines[actual_idx])
                old_line_idx += 1
            elif line.startswith('-'):
                # 删除行：跳过
                old_line_idx += 1
            elif line.startswith('+'):
                # 添加行：添加新内容
                new_region.append(line[1:])

        # 用新区域替换原始区域
        # 计算旧区域的范围
        old_region_len = sum(1 for l in change['hunk_lines'] if not l.startswith('+'))
        new_region_len = len(new_region)

        # 替换
        original_lines[actual_start:actual_start + old_region_len] = new_region

    return '\n'.join(original_lines), True, ""


def find_hunk_position_v2(original_lines: List[str], old_start: int, context_lines: List[tuple], delete_lines: List[tuple]) -> Optional[int]:
    """
    找到 hunk 在原始内容中的起始位置

    Args:
        original_lines: 原始内容（按行分割）
        old_start: hunk 在 old 文件中的起始行（0-based）
        context_lines: 上下文行列表 [(index_in_hunk, content), ...] - index_in_hunk 是在 hunk 内的旧文件行索引
        delete_lines: 删除行列表 [(index_in_hunk, content), ...]

    Returns:
        实际起始位置（0-based），如果找不到返回 None
    """
    # 使用删除行和上下文行作为匹配模式
    match_lines = delete_lines if delete_lines else context_lines

    if not match_lines:
        return old_start

    # match_lines 中的索引是相对于 hunk 开始位置的偏移量
    # 例如 (0, 'line1') 表示 hunk 第 1 行是 'line1'
    # 我们需要找到 original_lines 中的一个位置，使得从该位置开始的行与 match_lines 匹配

    # 找到最小和最大的相对索引
    min_rel_idx = min(idx for idx, _ in match_lines)
    max_rel_idx = max(idx for idx, _ in match_lines)
    span = max_rel_idx - min_rel_idx + 1

    # 在原始内容中滑动窗口匹配
    # 优先在 old_start 附近查找
    search_range = range(max(0, old_start - 5), min(len(original_lines) - span + 1, old_start + 10))

    for start_pos in search_range:
        # start_pos 是 hunk 第 0 行在 original_lines 中的位置
        # match_lines 中的索引是相对于 hunk 第 0 行的
        if match_span_v2(original_lines, start_pos, match_lines):
            return start_pos

    # 如果附近找不到，尝试全局匹配
    for start_pos in range(len(original_lines) - span + 1):
        if match_span_v2(original_lines, start_pos, match_lines):
            return start_pos

    return None


def match_span_v2(original_lines: List[str], start_pos: int, match_lines: List[tuple]) -> bool:
    """
    检查从 start_pos 开始是否匹配所有行

    Args:
        original_lines: 原始内容
        start_pos: hunk 第 0 行在 original_lines 中的位置
        match_lines: 匹配行列表 [(rel_idx, content), ...] - rel_idx 是相对于 hunk 第 0 行的偏移
    """
    for rel_idx, content in match_lines:
        actual_idx = start_pos + rel_idx
        if actual_idx < 0 or actual_idx >= len(original_lines):
            return False
        # 宽松匹配：忽略前后空白
        if original_lines[actual_idx].strip() != content.strip():
            return False

    return True


def find_hunk_position(original_lines: List[str], change: Dict) -> Optional[int]:
    """
    通过匹配上下文找到 hunk 在原始内容中的位置

    返回 hunk 第一行在原始内容中的索引（从 0 开始），如果找不到返回 None
    """
    context = change['context']
    delete_lines = change['delete']
    hunk = change['hunk']

    if not context and not delete_lines:
        # 没有上下文也没有删除，使用 hunk 头部的行号
        return hunk.old_start - 1

    # 使用所有非删除行作为匹配模式
    # 优先考虑删除行，因为它们更能精确定位
    match_lines = delete_lines if delete_lines else context

    if not match_lines:
        return hunk.old_start - 1

    # 在原始内容中滑动窗口匹配
    for start_pos in range(len(original_lines)):
        if matches_context(original_lines, start_pos, match_lines):
            # 返回第一个匹配行的位置
            return match_lines[0][0] - (hunk.old_start - 1) + start_pos

    return None


def matches_context(original_lines: List[str], start_pos: int, match_lines: List[tuple]) -> bool:
    """检查从 start_pos 开始是否匹配所有上下文/删除行"""
    if not match_lines:
        return True

    # 计算相对位置
    first_line_num = match_lines[0][0]

    for rel_num, content in match_lines:
        actual_pos = start_pos + (rel_num - first_line_num)
        if actual_pos < 0 or actual_pos >= len(original_lines):
            return False
        # 宽松匹配：忽略前后空白
        if original_lines[actual_pos].strip() != content.strip():
            return False

    return True


def generate_diff(old_content: str, new_content: str, filename: str) -> str:
    """
    生成 unified diff（用于调试和日志）
    """
    from difflib import unified_diff

    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = unified_diff(old_lines, new_lines,
                        fromfile=f'a/{filename}',
                        tofile=f'b/{filename}')

    return ''.join(diff)


def validate_diff(diff_text: str) -> Tuple[bool, str]:
    """
    验证 diff 格式是否正确

    Args:
        diff_text: diff 文本

    Returns:
        (is_valid, error_message)
        - is_valid: 是否有效
        - error_message: 错误信息（有效时为空）
    """
    if not diff_text or not diff_text.strip():
        return False, "Diff 内容为空"

    lines = diff_text.strip().split('\n')

    # 检查是否包含 diff 标记
    has_diff_header = False
    has_hunk = False

    for i, line in enumerate(lines):
        # 跳过 markdown 代码块标记
        if line.startswith('```'):
            continue

        # 检查文件头
        if line.startswith('--- '):
            has_diff_header = True
            # 检查下一行是否是 +++
            if i + 1 < len(lines) and not lines[i + 1].startswith('+++ '):
                return False, f"文件头格式错误：'---' 后应紧跟 '+++' (第 {i + 1} 行)"

        # 检查 hunk 头
        if line.startswith('@@'):
            has_hunk = True
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if not match:
                return False, f"Hunk 头格式错误：{line} (第 {i + 1} 行)"

            old_start = int(match.group(1))
            new_start = int(match.group(3))
            if old_start < 1 or new_start < 1:
                return False, f"行号不能小于 1：old={old_start}, new={new_start} (第 {i + 1} 行)"

    if not has_diff_header:
        return False, "缺少文件头（--- a/filename 和 +++ b/filename）"

    if not has_hunk:
        return False, "缺少 hunk（@@ -old_start,old_count +new_start,new_count @@）"

    return True, ""
