from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..logging_utils import log_event


@dataclass(frozen=True)
class SubtitleConfig:
    video_height: int = 720


class SubtitleGenerator:
    def __init__(
        self, *, config: SubtitleConfig, logger: Optional[logging.Logger] = None
    ):
        self._cfg = config
        self._logger = logger or logging.getLogger("videosup.subtitles")

    def generate_ass(
        self,
        *,
        job_id: str,
        voiceover_script: str,
        duration_sec: float,
        preset: str,
        render_profile: str,
        max_chars_per_line: int,
        safe_area_pct: float,
        out_path: Path,
    ) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        script = (voiceover_script or "").strip()
        words = _tokenize(script)
        if not words:
            words = [" "]

        karaoke = render_profile == "final"
        lines = _split_words(words, max_chars_per_line=max_chars_per_line)
        margin_v = int(self._cfg.video_height * safe_area_pct)

        ass_text = _build_ass(
            lines=lines,
            duration_sec=duration_sec,
            karaoke=karaoke,
            margin_v=margin_v,
        )
        out_path.write_text(ass_text, encoding="utf-8")
        log_event(
            self._logger,
            job_id=job_id,
            step="subtitle",
            message="ass_generated",
            output=str(out_path),
            line_count=len(lines),
            karaoke=karaoke,
            preset=preset,
        )
        return out_path


def _tokenize(s: str) -> List[str]:
    parts = [p for p in s.replace("\n", " ").split(" ") if p]
    return parts


def _split_words(words: List[str], *, max_chars_per_line: int) -> List[List[str]]:
    lines: List[List[str]] = []
    cur: List[str] = []
    cur_len = 0
    for w in words:
        add_len = len(w) + (1 if cur else 0)
        if cur and cur_len + add_len > max_chars_per_line:
            lines.append(cur)
            cur = [w]
            cur_len = len(w)
        else:
            cur.append(w)
            cur_len += add_len
    if cur:
        lines.append(cur)
    return lines


def _build_ass(
    *, lines: List[List[str]], duration_sec: float, karaoke: bool, margin_v: int
) -> str:
    total_cs = max(1, int(round(duration_sec * 100)))
    word_count = sum(len(x) for x in lines)
    per_word_cs = max(1, total_cs // max(1, word_count))
    remain_cs = total_cs - per_word_cs * word_count

    header = _ass_header(margin_v=margin_v)
    events: List[str] = []

    cur_cs = 0
    word_idx = 0
    for li in lines:
        seg_word_count = len(li)
        seg_cs = per_word_cs * seg_word_count
        if remain_cs > 0:
            take = min(remain_cs, seg_word_count)
            seg_cs += take
            remain_cs -= take

        start = _fmt_time_cs(cur_cs)
        end = _fmt_time_cs(min(total_cs, cur_cs + seg_cs))
        if karaoke:
            text = _karaoke_text(
                li, per_word_cs=per_word_cs, extra_cs=1 if word_idx == 0 else 0
            )
        else:
            text = " ".join(li)
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
        cur_cs += seg_cs
        word_idx += seg_word_count

    return header + "\n".join(events) + "\n"


def _ass_header(*, margin_v: int) -> str:
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1280\n"
        "PlayResY: 720\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,48,&H00FFFFFF,&H0000FFFF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,4,1,2,48,48,{margin_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _karaoke_text(words: List[str], *, per_word_cs: int, extra_cs: int) -> str:
    out: List[str] = []
    for i, w in enumerate(words):
        k = per_word_cs + (extra_cs if i == len(words) - 1 else 0)
        out.append(f"{{\\k{k}}}{w}")
        if i != len(words) - 1:
            out.append(" ")
    return "".join(out)


def _fmt_time_cs(cs: int) -> str:
    if cs < 0:
        cs = 0
    h = cs // (3600 * 100)
    cs %= 3600 * 100
    m = cs // (60 * 100)
    cs %= 60 * 100
    s = cs // 100
    c = cs % 100
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"
