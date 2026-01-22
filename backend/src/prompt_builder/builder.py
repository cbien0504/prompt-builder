
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Tuple, Literal, Dict, Optional
from ..utils import parse_query
from ..core import ChunkRecord
import os
from ..web.routes.folders import PROJECT_ROOT

def _get_token_counter(model: str | None = None) -> Callable[[str], int]:
    try:
        import tiktoken  # type: ignore

        encoding = tiktoken.encoding_for_model(model) if model else tiktoken.get_encoding("cl100k_base")

        def count_tokens(text: str) -> int:
            return len(encoding.encode(text))

        return count_tokens
    except Exception:
        def count_tokens(text: str) -> int:
            return max(1, int(len(text) / 3.5))

        return count_tokens


def estimate_tokens(text: str) -> int:
    counter = _get_token_counter()
    return counter(text)


@dataclass(frozen=True)
class PromptConfig:
    max_tokens: int = 32000
    reserve_reply_tokens: int = 1200
    model: str | None = None
    split_oversized_items: bool = True
    oversized_chunk_soft_limit_tokens: int = 8000


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _read_template(filename: str, language: Literal["eng", "vie"] = "vie") -> str:
    path = TEMPLATE_DIR / language / filename
    return path.read_text(encoding="utf-8")


def _format_context_item(score: float, r: ChunkRecord) -> str:
    return (
        f"\n### {r.path}:{r.start_line}-{r.end_line} (score={score:0.4f})\n"
        f"```\n{r.text.rstrip()}\n```\n"
    )
def read_file_lines(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    if start_line is None and end_line is None:
        return "".join(lines)
    
    total_lines = len(lines)
    if start_line is not None and (start_line < 1 or start_line > total_lines):
        raise ValueError(f"start_line {start_line} out of range (1-{total_lines})")
    if end_line is not None and (end_line < 1 or end_line > total_lines):
        raise ValueError(f"end_line {end_line} out of range (1-{total_lines})")
    if start_line is not None and end_line is not None and start_line > end_line:
        raise ValueError(f"start_line {start_line} cannot be greater than end_line {end_line}")
    
    start_idx = (start_line - 1) if start_line else 0
    end_idx = end_line if end_line else total_lines
    
    return "".join(lines[start_idx:end_idx])


def format_code_section(file_path: str, content: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    if start_line is not None and end_line is not None:
        header = f"// File: {file_path} (lines {start_line}-{end_line})"
    else:
        header = f"// File: {file_path}"
    
    return f"{header}\n```\n{content}\n```\n"
def build_code_context(file_refs: List[Dict[str, Optional[int]]]) -> str:
    if not file_refs:
        return ""
    
    code_sections = []
    
    for file_ref in file_refs:
        file_path = PROJECT_ROOT + "/" + file_ref.get("path")
        start_line = file_ref.get("start_line")
        end_line = file_ref.get("end_line")
        
        if not file_path:
            continue
        
        try:
            content = read_file_lines(file_path, start_line, end_line)
            
            formatted = format_code_section(file_path, content, start_line, end_line)
            code_sections.append(formatted)
            
        except FileNotFoundError as e:
            print(f"Warning: {e}")
            code_sections.append(f"// File not found: {file_path}\n")
            
        except ValueError as e:
            print(f"Warning: {e}")
            code_sections.append(f"// Error reading {file_path}: {e}\n")
    
    return "\n".join(code_sections)

def _split_item_by_lines(
    item: str,
    count_tokens: Callable[[str], int],
    soft_limit: int,
) -> List[str]:
    if count_tokens(item) <= soft_limit:
        return [item]

    start = item.find("```")
    end = item.rfind("```")
    if start == -1 or end == -1 or end <= start:
        chunks: List[str] = []
        step = max(1000, int(len(item) / 5))
        for i in range(0, len(item), step):
            chunks.append(item[i : i + step])
        return chunks

    header = item[: start].rstrip()
    code = item[start + 3 : end].strip("\n")
    footer = item[end + 3 :].rstrip()

    code_lines = code.splitlines()
    out: List[str] = []
    buf: List[str] = []
    buf_tokens = 0

    def flush() -> None:
        nonlocal buf, buf_tokens
        if not buf:
            return
        piece = f"{header}\n```\n" + "\n".join(buf) + "\n```\n" + (footer + "\n" if footer else "")
        out.append(piece)
        buf = []
        buf_tokens = 0

    for ln in code_lines:
        t = count_tokens(ln + "\n")
        if buf and (buf_tokens + t) > soft_limit:
            flush()
        buf.append(ln)
        buf_tokens += t

    flush()
    return out if out else [item]


class PromptBuilder:
    def __init__(self, config: PromptConfig | None = None):
        self.config = config or PromptConfig()
        self.count_tokens = _get_token_counter(self.config.model)

    def build_system_prompt(self, query: str, file_refs: List[Dict[str, Optional[int]]], language: Literal["eng", "vie"] = "vie") -> str:
        tpl = _read_template("system_prompt.md", language)
        code = build_code_context(file_refs)
        return tpl.format(task=query.strip(), code=code)

    def build_human_prompt(self, num_parts: int, language: Literal["eng", "vie"] = "vie") -> str:
        tpl = _read_template("human_prompt.md", language)
        notice = ""
        if num_parts > 1:
            notice = (
                f"> ✅ Đã nhận đủ **{num_parts} phần context**. " if language == "vie" else f"> ✅ Received all **{num_parts} parts of context**. "
                f"Bây giờ hãy phân tích toàn diện và trả lời theo format dưới đây.\n" if language == "vie" else f"Now please analyze the context comprehensively and respond according to the format below.\n"
            )
        return tpl.format(num_parts_notice=notice)

    def build_context_parts(
        self,
        hits: List[Tuple[float, ChunkRecord]],
        language: Literal["eng", "vie"] = "vie",
    ) -> Tuple[List[List[str]], int]:
        context_items: List[str] = []
        for score, chunk in hits:
            context_items.append(_format_context_item(score, chunk))

        total_context_tokens = sum(self.count_tokens(x) for x in context_items)

        if not context_items:
            return [[]], 0

        if self.config.split_oversized_items:
            expanded: List[str] = []
            for item in context_items:
                if self.count_tokens(item) > self.config.oversized_chunk_soft_limit_tokens:
                    expanded.extend(
                        _split_item_by_lines(
                            item, 
                            self.count_tokens, 
                            self.config.oversized_chunk_soft_limit_tokens
                        )
                    )
                else:
                    expanded.append(item)
            context_items = expanded

        per_part_budget = max(1000, self.config.max_tokens - self.config.reserve_reply_tokens)
        parts = self._partition_context_items(context_items, per_part_budget, language)

        return parts, total_context_tokens

    def _partition_context_items(
        self, 
        context_items: List[str], 
        per_part_budget: int,
        language: Literal["eng", "vie"] = "vie",
    ) -> List[List[str]]:
        parts: List[List[str]] = []
        current: List[str] = []
        current_tokens = 0
        part_idx = 1

        def overhead_tokens(part_idx_local: int, num_parts_guess: int = 2, is_last: bool = False, language: Literal["eng", "vie"] = "vie") -> int:
            prefix = self._part_prefix(part_idx_local, num_parts_guess, is_last, language)
            section_header = "\n\n## Code Fragments\n"
            continue_marker = "\n\n... (Continue in the next part)\n" if language == "eng" else "\n\n... (Tiếp tục ở phần sau)\n"
            
            tokens = self.count_tokens(prefix) + self.count_tokens(section_header)
            if not is_last:
                tokens += self.count_tokens(continue_marker)
            return tokens

        base_overhead_first = overhead_tokens(1, num_parts_guess=2, is_last=False, language=language)
        base_overhead_next = overhead_tokens(2, num_parts_guess=2, is_last=False, language=language)

        for item in context_items:
            item_tokens = self.count_tokens(item)
            ov = base_overhead_first if part_idx == 1 else base_overhead_next

            if not current:
                current.append(item)
                current_tokens = item_tokens
                if ov + item_tokens > per_part_budget:
                    parts.append(current)
                    current = []
                    current_tokens = 0
                    part_idx += 1
                continue

            if ov + current_tokens + item_tokens > per_part_budget:
                parts.append(current)
                current = [item]
                current_tokens = item_tokens
                part_idx += 1
            else:
                current.append(item)
                current_tokens += item_tokens

        if current or not parts:
            parts.append(current)

        return parts

    def _part_prefix(self, part_idx: int, num_parts: int, is_last: bool, language: Literal["eng", "vie"] = "vie") -> str:
        if num_parts > 1:
            lines = [f"# [PART {part_idx}/{num_parts}] Context Data"]
            if not is_last:
                lines.append(
                    f"> Note: This is part {part_idx}. Please DO NOT RESPOND YET. " if language == "eng" else f"> Lưu ý: Đây là phần {part_idx}. Vui lòng CHƯA TRẢ LỜI NGAY. "
                    f"Please respond 'Received Part {part_idx}' and wait for the next part." if language == "eng" else f"Hãy trả lời 'Received Part {part_idx}' và chờ phần tiếp theo."
                )
            return "\n".join(lines)
        return "# Context Data"

    def build_full_prompts(
        self,
        clean_query: str,
        file_refs: List[Dict[str, Optional[int]]],
        hits: List[Tuple[float, ChunkRecord]],
        language: Literal["eng", "vie"] = "vie",
    ) -> Tuple[str, List[str], int]:
        system_prompt = self.build_system_prompt(clean_query, file_refs, language)
        parts, total_tokens = self.build_context_parts(hits, language)
        num_parts = len(parts)
        human_footer = self.build_human_prompt(num_parts, language)
        human_prompts: List[str] = []
        for i, batch in enumerate(parts):
            is_last = (i == len(parts) - 1)
            human_prompts.append(self._build_part_text(i, batch, is_last, num_parts, human_footer, language))

        return system_prompt, human_prompts, total_tokens

    def _build_part_text(
        self, 
        i: int, 
        batch: List[str], 
        is_last: bool, 
        num_parts: int,
        footer: str,
        language: Literal["eng", "vie"] = "vie",
    ) -> str:
        lines: List[str] = []
        lines.append(self._part_prefix(i + 1, num_parts, is_last, language))
        lines.append("## Code Fragments")
        lines.extend(batch)
        
        if is_last:
            lines.append(footer)
        else:
            lines.append(f"... (Continue in the next part)") if language == "eng" else lines.append("... (Tiếp tục ở phần sau)")
        
        return "\n".join(lines)


def build_prompt(
    query: str,
    hits: List[Tuple[float, ChunkRecord]],
    language: Literal["eng", "vie"] = "vie",
    max_tokens: int = 40_000,
) -> Tuple[List[str], int]:
    clean_query, file_refs = parse_query(query)
    config = PromptConfig(max_tokens=max_tokens)
    builder = PromptBuilder(config)
    system_prompt, human_prompts, total_tokens = builder.build_full_prompts(clean_query, file_refs, hits, language)
    
    combined = []
    for i, human_prompt in enumerate(human_prompts):
        if i == 0:
            combined.append(f"{system_prompt}\n\n{human_prompt}")
        else:
            combined.append(human_prompt)
    
    return combined, total_tokens