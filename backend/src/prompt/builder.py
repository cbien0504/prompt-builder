"""LLM prompt building (optimized)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Tuple

from ..core import ChunkRecord


# ----------------------------
# Token estimation
# ----------------------------

def _get_token_counter(model: str | None = None) -> Callable[[str], int]:
    """
    Return a token counting function.
    - Use tiktoken if available.
    - Fallback to heuristic otherwise.

    Notes:
    - Heuristic is intentionally conservative for code/mixed content.
    """
    try:
        import tiktoken  # type: ignore

        # Default to a common encoding if model is unknown.
        encoding = tiktoken.encoding_for_model(model) if model else tiktoken.get_encoding("cl100k_base")

        def count_tokens(text: str) -> int:
            return len(encoding.encode(text))

        return count_tokens
    except Exception:
        # Fallback heuristic: conservative for code/mixed text.
        # Typical: ~3-4 chars per token; choose 4 to be safer (fewer tokens -> risk overflow),
        # but we want safer upper bound => use 3.2 chars/token or use ceil(len/3).
        # Here we choose ~3.5 chars/token (slightly conservative).
        def count_tokens(text: str) -> int:
            # +1 to avoid zero on short strings
            return max(1, int(len(text) / 3.5))

        return count_tokens


# Keep this for backward compatibility if other modules import it.
def estimate_tokens(text: str) -> int:
    """Estimate token count with fallback heuristic."""
    counter = _get_token_counter()
    return counter(text)


# ----------------------------
# Prompt building
# ----------------------------

@dataclass(frozen=True)
class PromptConfig:
    max_tokens: int = 32000
    reserve_reply_tokens: int = 1200  # reserve for model response + extra system overhead
    model: str | None = None

    # If a single context item is larger than the per-part budget, optionally split it by lines.
    split_oversized_items: bool = True
    oversized_chunk_soft_limit_tokens: int = 8000  # split big items into smaller slices


def _build_header(task: str) -> str:
    lines: List[str] = []
    lines.append("# Vai trò của bạn")
    lines.append("Bạn là một Senior Software Engineer và AI Coding Assistant chuyên nghiệp với kinh nghiệm sâu về:")
    lines.append("- Code review, refactoring và optimization")
    lines.append("- Architecture design và best practices")
    lines.append("- Debugging và problem solving")
    lines.append("- Hiểu sâu về nhiều ngôn ngữ lập trình và frameworks")
    lines.append("")
    lines.append("# Cách thức làm việc")
    lines.append("Tôi sẽ cung cấp context code qua nhiều tin nhắn. Hãy:")
    lines.append("1. **Thu thập đầy đủ context**: Đọc KỸ tất cả code fragments từ các phần được gửi")
    lines.append("2. **Phân tích toàn diện**: Hiểu rõ cấu trúc, dependencies, và relationships giữa các components")
    lines.append("3. **Tổng hợp trước khi trả lời**: KHÔNG trả lời ngay khi nhận phần đầu, hãy chờ nhận đủ tất cả context")
    lines.append("")
    lines.append("# Nhiệm vụ của bạn")
    lines.append(task.strip())
    lines.append("")
    lines.append("# Nguyên tắc quan trọng")
    lines.append("")
    lines.append("## Về Code Quality")
    lines.append("- **KHÔNG BAO GIỜ bịa code hoặc API**: Chỉ sử dụng patterns/APIs có trong context hoặc standard library")
    lines.append("- **Giữ consistency**: Tuân thủ 100% coding style, naming conventions, và patterns hiện có")
    lines.append("- **Type safety**: Sử dụng type hints đầy đủ (Python), TypeScript (JavaScript), etc.")
    lines.append("- **Error handling**: Xử lý edge cases và errors một cách comprehensive")
    lines.append("- **Performance**: Tối ưu code nhưng ưu tiên readability và maintainability")
    lines.append("")
    lines.append("## Về Communication")
    lines.append("- **Nếu thiếu thông tin**: Hỏi cụ thể thông tin cần bổ sung")
    lines.append("- **Nếu có nhiều cách tiếp cận**: Đề xuất các options kèm pros/cons")
    lines.append("- **Nếu phát hiện issues**: Chỉ ra rõ ràng và đề xuất fix")
    lines.append("- **Nếu task không rõ ràng**: Clarify requirements trước khi implement")
    lines.append("")
    lines.append("## Về Security & Best Practices")
    lines.append("- Tránh security vulnerabilities (SQL injection, XSS, etc.)")
    lines.append("- Follow SOLID principles và design patterns phù hợp")
    lines.append("- Viết code dễ test, maintain và scale")
    lines.append("- Add meaningful comments cho complex logic")
    return "\n".join(lines)


def _build_footer(num_parts: int) -> str:
    lines: List[str] = []
    lines.append("")
    lines.append("# Format trả lời bắt buộc")
    lines.append("")
    if num_parts > 1:
        lines.append(f"> ✅ Đã nhận đủ **{num_parts} phần context**. Bây giờ hãy phân tích toàn diện và trả lời theo format dưới đây.")
        lines.append("")
    lines.append("Hãy trả lời theo cấu trúc sau (sử dụng Markdown):")
    lines.append("")
    lines.append("## 1. 📋 Executive Summary")
    lines.append("Tóm tắt ngắn gọn (3-6 bullet points):")
    lines.append("- Vấn đề chính cần giải quyết")
    lines.append("- Approach/solution được chọn")
    lines.append("- Impact và scope của changes")
    lines.append("- Key technical decisions")
    lines.append("")
    lines.append("## 2. 🔍 Analysis & Context")
    lines.append("- **Current State**: Mô tả code structure hiện tại liên quan đến task")
    lines.append("- **Root Cause/Requirements**: Phân tích nguyên nhân hoặc requirements chi tiết")
    lines.append("- **Design Decisions**: Giải thích WHY chọn approach này")
    lines.append("- **Trade-offs**: Các compromises và alternatives đã consider")
    lines.append("")
    lines.append("## 3. 🛠️ Implementation Details")
    lines.append("")
    lines.append("### Modified Files")
    lines.append("Với mỗi file cần sửa, cung cấp:")
    lines.append("")
    lines.append("#### `path/to/file.ext`")
    lines.append("**Changes**: Mô tả ngắn gọn what changed và why")
    lines.append("")
    lines.append("**Location**: Lines X-Y hoặc function/class name")
    lines.append("")
    lines.append("**Code**:")
    lines.append("```language")
    lines.append("// Code implementation với inline comments giải thích logic phức tạp")
    lines.append("```")
    lines.append("")
    lines.append("### New Files (nếu có)")
    lines.append("List các files mới cần tạo kèm full implementation")
    lines.append("")
    lines.append("### Deleted Files (nếu có)")
    lines.append("List các files cần xóa kèm lý do")
    lines.append("")
    lines.append("## 4. 🧪 Testing Strategy")
    lines.append("- **Unit Tests**: Test cases cần thêm/update")
    lines.append("- **Integration Points**: Các dependencies/integrations cần test")
    lines.append("- **Edge Cases**: Scenarios đặc biệt cần verify")
    lines.append("- **Manual Testing**: Steps để test manually nếu cần")
    lines.append("")
    lines.append("## 5. ⚠️ Important Notes")
    lines.append("")
    lines.append("### Risks & Considerations")
    lines.append("- Breaking changes (nếu có)")
    lines.append("- Performance implications")
    lines.append("- Security concerns")
    lines.append("- Migration requirements")
    lines.append("")
    lines.append("### Questions & Clarifications")
    lines.append("Liệt kê các questions cần người dùng clarify (nếu có)")
    lines.append("")
    lines.append("### Next Steps (Optional)")
    lines.append("Đề xuất các improvements hoặc follow-up tasks")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**Lưu ý về code blocks**:")
    lines.append("- Luôn specify language cho syntax highlighting")
    lines.append("- Include đủ context (imports, surrounding code nếu cần)")
    lines.append("- Add comments giải thích complex logic")
    lines.append("- Indicate file path trước mỗi code block")
    return "\n".join(lines)


def _format_context_item(score: float, r: ChunkRecord) -> str:
    # Keep formatting stable; only tighten whitespace.
    return (
        f"\n### {r.path}:{r.start_line}-{r.end_line} (score={score:0.4f})\n"
        f"```\n{r.text.rstrip()}\n```\n"
    )


def _split_item_by_lines(
    item: str,
    count_tokens: Callable[[str], int],
    soft_limit: int,
) -> List[str]:
    """
    Split a huge context item into smaller blocks by lines while preserving code fences.
    This is a best-effort splitter. It keeps header lines and re-wraps code fences.
    """
    if count_tokens(item) <= soft_limit:
        return [item]

    # Very simple parse: find the first ``` and last ``` to extract code.
    # If format doesn't match, fallback to naive slicing.
    start = item.find("```")
    end = item.rfind("```")
    if start == -1 or end == -1 or end <= start:
        # Naive slicing by characters
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
        # +1 for newline
        t = count_tokens(ln + "\n")
        if buf and (buf_tokens + t) > soft_limit:
            flush()
        buf.append(ln)
        buf_tokens += t

    flush()
    return out if out else [item]


from .base import PromptBuilder

class DefaultPromptBuilder(PromptBuilder):
    """Default implementation of PromptBuilder."""
    
    def build_prompt(
        self,
        task: str,
        hits: List[Tuple[float, ChunkRecord]],
        max_tokens: int = 40_000,
    ) -> Tuple[List[str], int]:
        """
        Build LLM prompt(s) from search results, splitting into parts if needed.
    
        Returns:
            (prompts, total_context_tokens)
        """
        cfg = PromptConfig(max_tokens=max_tokens)
        count_tokens = _get_token_counter(cfg.model)
    
        header = _build_header(task)
        # Footer depends on num_parts => built later.
    
        # Prepare formatted context items
        context_items: List[str] = []
        for score, r in hits:
            context_items.append(_format_context_item(score, r))
    
        # Token count (context only)
        total_context_tokens = sum(count_tokens(x) for x in context_items)
    
        # If no context, still produce one prompt
        if not context_items:
            context_items = []
    
        # Helper/part wrappers (small but we account anyway)
        def part_prefix(part_idx: int, num_parts: int, is_last: bool) -> str:
            if num_parts > 1:
                lines = [f"# [PART {part_idx}/{num_parts}] Context Data"]
                if not is_last:
                    lines.append(
                        f"> Lưu ý: Đây là phần {part_idx}. Vui lòng CHƯA TRẢ LỜI NGAY. "
                        f"Hãy trả lời 'Received Part {part_idx}' và chờ phần tiếp theo."
                    )
                return "\n".join(lines)
            return "# Context Data"
    
        section_header = "\n\n## Code Fragments\n"
        continue_marker = "\n\n... (Tiếp tục ở phần sau)\n"
    
        # Compute per-part budget precisely
        # budget = max_tokens - reserve_reply_tokens
        per_part_budget = max(1000, cfg.max_tokens - cfg.reserve_reply_tokens)
    
        # We don't know num_parts until we pack items.
        # We'll pack assuming worst-case: header appears only in part1, footer only in last.
        # Strategy: greedy pack with dynamic overhead:
        # - For each prospective part, compute overhead tokens = prefix + (header if part1) + section_header + (footer if last)
        # Since we can't know "last" while packing, we pack using overhead without footer first,
        # then after packing we add footer to last part; if it overflows, we rebalance.
    
        # Optional: split oversized items first
        if cfg.split_oversized_items:
            expanded: List[str] = []
            for item in context_items:
                if count_tokens(item) > cfg.oversized_chunk_soft_limit_tokens:
                    expanded.extend(_split_item_by_lines(item, count_tokens, cfg.oversized_chunk_soft_limit_tokens))
                else:
                    expanded.append(item)
            context_items = expanded
    
        # First pass greedy packing (without footer)
        parts: List[List[str]] = []
        current: List[str] = []
        current_tokens = 0
    
        # Use a conservative overhead for non-last parts:
        # prefix + (header maybe) + section_header + continue_marker
        # We'll compute exact overhead per part as we pack.
        part_idx = 1
    
        def overhead_tokens(part_idx_local: int, num_parts_guess: int = 2, is_last: bool = False) -> int:
            # num_parts_guess used only to include PART labeling when > 1
            prefix = part_prefix(part_idx_local, num_parts_guess, is_last)
            tokens = count_tokens(prefix) + count_tokens(section_header)
            if part_idx_local == 1:
                tokens += count_tokens("\n" + header + "\n")
            if not is_last:
                tokens += count_tokens(continue_marker)
            return tokens
    
        # While packing, assume multi-part if context is large; we can refine later.
        # If it ends up single-part, the prefix becomes smaller; that's safe.
        base_overhead_first = overhead_tokens(1, num_parts_guess=2, is_last=False)
        base_overhead_next = overhead_tokens(2, num_parts_guess=2, is_last=False)
    
        for item in context_items:
            item_tokens = count_tokens(item)
    
            # Determine overhead for current part
            ov = base_overhead_first if part_idx == 1 else base_overhead_next
    
            # If current is empty, check if item alone fits (with overhead)
            if not current:
                if ov + item_tokens <= per_part_budget:
                    current.append(item)
                    current_tokens = item_tokens
                    continue
                # If an item still doesn't fit (very huge), force it into its own part (best effort).
                current.append(item)
                current_tokens = item_tokens
                parts.append(current)
                current = []
                current_tokens = 0
                part_idx += 1
                continue
    
            # If adding item exceeds budget, close current part
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
    
        # Second pass: add footer to last part and ensure it fits; if not, rebalance.
        # Now we know actual num_parts.
        num_parts = len(parts)
        footer = _build_footer(num_parts)
        footer_tokens = count_tokens("\n" + footer + "\n")
    
        def build_part_text(i: int, batch: List[str], is_last: bool) -> str:
            lines: List[str] = []
            lines.append(part_prefix(i + 1, num_parts, is_last))
            if i == 0:
                lines.append(header)
            lines.append("## Code Fragments")
            lines.extend(batch)
            if is_last:
                lines.append(footer)
            else:
                lines.append("... (Tiếp tục ở phần sau)")
            return "\n".join(lines)
    
        # Rebalance if last part overflows after adding footer.
        # Move items from last to previous parts if possible.
        def part_total_tokens(i: int, batch: List[str], is_last: bool) -> int:
            return count_tokens(build_part_text(i, batch, is_last))
    
        if num_parts >= 1:
            # While last part too large, move one item to previous part if possible
            while part_total_tokens(num_parts - 1, parts[-1], True) > per_part_budget:
                if num_parts == 1:
                    # Can't rebalance; accept overflow (should be rare with reserve)
                    break
                if not parts[-1]:
                    break
                # Move first item from last to previous (or last item; choose one)
                moving = parts[-1].pop(0)
                parts[-2].append(moving)
                # If previous now overflows (as non-last), undo and instead create a new middle part.
                if part_total_tokens(num_parts - 2, parts[-2], False) > per_part_budget:
                    parts[-2].pop()
                    parts[-1].insert(0, moving)
                    # Create a new part before last to offload a chunk from previous
                    if len(parts[-2]) > 1:
                        new_part = [parts[-2].pop()]  # move one item into new part
                        parts.insert(-1, new_part)
                        num_parts = len(parts)
                        footer = _build_footer(num_parts)
                        # continue loop with updated num_parts
                        continue
                    else:
                        # Can't fix further
                        break
    
        # Final render
        prompts: List[str] = []
        for i, batch in enumerate(parts):
            is_last = (i == len(parts) - 1)
            prompts.append(build_part_text(i, batch, is_last))
    
        return prompts, total_context_tokens


def build_prompt(
    task: str,
    hits: List[Tuple[float, ChunkRecord]],
    max_tokens: int = 40_000,
) -> Tuple[List[str], int]:
    """Wrapper for DefaultPromptBuilder."""
    builder = DefaultPromptBuilder()
    return builder.build_prompt(task, hits, max_tokens)
