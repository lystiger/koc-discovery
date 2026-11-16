"""Video content analysis module (Stage 3)."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
import tempfile
from typing import TYPE_CHECKING
from pydantic import BaseModel, Field

from koc.types import (
    VideoInput,
    BrandBrief,
    ContentAnalysis,
    RubricScore,
    Evidence,
    Usage,
)
from koc.llm.media import preprocess_video
from koc.llm.pricing import estimate_usd, estimate_tokens_and_usd, load_pricing_config
from koc.llm.gemini import GeminiClient, create_part_from_image, create_part_from_audio
from koc.llm.factory import get_llm_client
from koc.llm.guard import DATA_NOTICE_VI, fence, injection_warning_vi

if TYPE_CHECKING:
    from koc.types import BudgetGuard

PROMPT_FILE = Path(__file__).resolve().parents[3] / "prompts" / "content_v3.md"

REQUIRED_CRITERIA = {
    "hook",
    "product_clarity",
    "demonstration",
    "claim_quality",
    "cta",
    "brand_fit",
    "production_quality",
}


def truncate_at_word_boundary(text: str | None, max_chars: int) -> str | None:
    """Truncate text at a word boundary to at most max_chars.

    If text is None or len(text) <= max_chars, returns text unchanged.
    Otherwise slices at max_chars and rolls back to the last whitespace boundary
    so words are not sliced mid-word. If no whitespace exists, falls back
    to hard slice at max_chars.
    """
    if text is None:
        return None
    if len(text) <= max_chars:
        return text
    sliced = text[:max_chars]
    if text[max_chars].isspace():
        return sliced.rstrip()
    match = re.search(r"\s+\S*$", sliced)
    if match and match.start() > 0:
        return sliced[:match.start()].rstrip()
    return sliced.rstrip()


def enforce_payload_limits(payload: ContentAnalysisPayload) -> ContentAnalysisPayload:
    """Defensively enforce length and count limits before payload validation."""
    for ev in payload.evidence:
        if ev.quote_vi:
            ev.quote_vi = truncate_at_word_boundary(ev.quote_vi, 200) or ""

    for r in payload.rubric:
        if r.rationale_vi:
            r.rationale_vi = truncate_at_word_boundary(r.rationale_vi, 250) or ""

    if len(payload.evidence) > 12:
        ev_by_id = {ev.evidence_id: ev for ev in payload.evidence}
        selected_ids: list[str] = []
        for r in payload.rubric:
            for eid in r.evidence_ids:
                if eid in ev_by_id and eid not in selected_ids:
                    selected_ids.append(eid)
                    break
        for r in payload.rubric:
            for eid in r.evidence_ids:
                if len(selected_ids) >= 12:
                    break
                if eid in ev_by_id and eid not in selected_ids:
                    selected_ids.append(eid)
        for ev in payload.evidence:
            if len(selected_ids) >= 12:
                break
            if ev.evidence_id not in selected_ids:
                selected_ids.append(ev.evidence_id)

        kept_id_set = set(selected_ids)
        payload.evidence = [ev for ev in payload.evidence if ev.evidence_id in kept_id_set][:12]

        final_ev_ids = {ev.evidence_id for ev in payload.evidence}
        for r in payload.rubric:
            valid_eids = [eid for eid in r.evidence_ids if eid in final_ev_ids]
            if valid_eids:
                r.evidence_ids = valid_eids

    return payload


class EvidenceItemPayload(Evidence):
    quote_vi: str = Field(json_schema_extra={"maxLength": 200})
    frame_path: str | None = None


class RubricScorePayload(RubricScore):
    rationale_vi: str = Field(json_schema_extra={"maxLength": 250})


class ContentAnalysisPayload(BaseModel):
    """Schema enforced for structured JSON output."""
    video_id: str
    rubric: list[RubricScorePayload] = Field(default_factory=list)
    risks_vi: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItemPayload] = Field(default_factory=list, json_schema_extra={"maxItems": 12})


def dedupe_payload(payload: ContentAnalysisPayload) -> ContentAnalysisPayload:
    """Drop repeated evidence_ids (keep first) and repeated ids inside rubric lists."""
    seen: set[str] = set()
    unique = []
    for ev in payload.evidence:
        if ev.evidence_id not in seen:
            seen.add(ev.evidence_id)
            unique.append(ev)
    payload.evidence = unique
    for r in payload.rubric:
        r.evidence_ids = list(dict.fromkeys(r.evidence_ids))
    return payload


def _validate_payload(
    payload: ContentAnalysisPayload,
    video_id: str,
    duration_s: float,
    has_audio: bool = True,
) -> list[str]:
    errors = []

    # 1. Video ID match
    if payload.video_id != video_id:
        errors.append(f"Video ID không khớp: mong đợi '{video_id}', nhận được '{payload.video_id}'")

    # 2. Rubric count exactly 7
    if len(payload.rubric) != 7:
        errors.append(f"Số lượng tiêu chí rubric phải đúng 7, nhận được {len(payload.rubric)}")

    # 3. Rubric criteria: no duplicates, exactly the required 7
    criteria_seen = set()
    for r in payload.rubric:
        if r.criterion in criteria_seen:
            errors.append(f"Tiêu chí trùng lặp trong rubric: '{r.criterion}'")
        criteria_seen.add(r.criterion)

    missing = REQUIRED_CRITERIA - criteria_seen
    if missing:
        errors.append(f"Thiếu các tiêu chí rubric bắt buộc: {sorted(missing)}")

    # 4. Rubric citations: non-empty citation per criterion
    for r in payload.rubric:
        if not r.evidence_ids:
            errors.append(f"Tiêu chí '{r.criterion}' không có bằng chứng (danh sách evidence_ids rỗng)")

    # 5. Evidence list must not be empty
    if not payload.evidence:
        errors.append("Danh sách bằng chứng (evidence) không được rỗng")

    # 6. Evidence uniqueness, format, video_id, timestamps (R2-2)
    ev_ids_seen = set()
    re_ts = re.compile(rf"^{re.escape(video_id)}@(\d+(\.\d+)?)$")
    re_tr = re.compile(rf"^{re.escape(video_id)}:transcript:(\d+)$")

    for ev in payload.evidence:
        if ev.evidence_id in ev_ids_seen:
            errors.append(f"Mã bằng chứng trùng lặp trong evidence: '{ev.evidence_id}'")
        ev_ids_seen.add(ev.evidence_id)

        if ev.video_id != video_id:
            errors.append(f"Bằng chứng '{ev.evidence_id}' có video_id sai: '{ev.video_id}' != '{video_id}'")

        m_ts = re_ts.match(ev.evidence_id)
        m_tr = re_tr.match(ev.evidence_id)

        if not (m_ts or m_tr):
            errors.append(
                f"Định dạng mã bằng chứng không hợp lệ: '{ev.evidence_id}' "
                f"(phải là {video_id}@<start_s> hoặc {video_id}:transcript:<n>)"
            )
        elif m_ts:
            ts_str = m_ts.group(1)
            try:
                id_ts = float(ts_str)
                if not math.isfinite(ev.start_s) or abs(id_ts - ev.start_s) > 1e-3:
                    errors.append(
                        f"Mốc thời gian trong evidence_id '{ev.evidence_id}' ({id_ts}s) "
                        f"không khớp với start_s ({ev.start_s}s)"
                    )
            except ValueError:
                errors.append(f"Mốc thời gian trong evidence_id không hợp lệ: '{ev.evidence_id}'")

        if not has_audio:
            if ev.kind == "speech":
                errors.append(f"Video không có luồng âm thanh nhưng bằng chứng '{ev.evidence_id}' có loại là speech")
            if m_tr:
                errors.append(f"Video không có luồng âm thanh nhưng bằng chứng '{ev.evidence_id}' là dạng transcript")

        if not math.isfinite(ev.start_s):
            errors.append(f"Mốc thời gian start_s không phải số hữu hạn: {ev.start_s}")
        elif ev.start_s < 0.0 or ev.start_s > duration_s:
            errors.append(f"Mốc thời gian start_s không hợp lệ: {ev.start_s}s (video dài {duration_s}s)")

        if ev.end_s is not None:
            if not math.isfinite(ev.end_s):
                errors.append(f"Mốc thời gian end_s không phải số hữu hạn: {ev.end_s}")
            elif not math.isfinite(ev.start_s) or ev.end_s < ev.start_s or ev.end_s > duration_s:
                errors.append(
                    f"Mốc thời gian end_s không hợp lệ: {ev.end_s}s (start_s={ev.start_s}s, video dài {duration_s}s)"
                )

        if not ev.quote_vi or not ev.quote_vi.strip():
            errors.append(f"Bằng chứng '{ev.evidence_id}' thiếu nội dung quote_vi")

    # 7. Unresolved evidence IDs in rubric
    for r in payload.rubric:
        unresolved = [eid for eid in r.evidence_ids if eid not in ev_ids_seen]
        if unresolved:
            errors.append(f"Tiêu chí '{r.criterion}' trích dẫn mã bằng chứng không tồn tại: {sorted(unresolved)}")

    # 8. Length limits and evidence count
    if len(payload.evidence) > 12:
        errors.append(f"Số lượng bằng chứng (evidence) vượt quá 12: {len(payload.evidence)}")

    for ev in payload.evidence:
        if ev.quote_vi and len(ev.quote_vi) > 200:
            errors.append(f"Độ dài quote_vi của bằng chứng '{ev.evidence_id}' vượt quá 200 ký tự: {len(ev.quote_vi)}")

    for r in payload.rubric:
        if r.rationale_vi and len(r.rationale_vi) > 250:
            errors.append(f"Độ dài rationale_vi của tiêu chí '{r.criterion}' vượt quá 250 ký tự: {len(r.rationale_vi)}")

    return errors


def analyze_video(
    video: VideoInput,
    brief: BrandBrief,
    *,
    budget_guard: BudgetGuard,
    client: GeminiClient | None = None,
    frames_dir: str | None = None,
    preprocess_dir: str | None = None,
) -> ContentAnalysis:
    """Analyze a single video (multimodal: 8 frames + audio + metadata + brief).

    Enforces 7 rubric criteria, non-empty citations, evidence-id resolution,
    and budget guard checks. Retries once with a repair prompt (including full
    context and media) if validation fails.
    """
    if frames_dir is not None:
        work_dir = Path(frames_dir) / video.video_id
        work_dir.mkdir(parents=True, exist_ok=True)
    elif preprocess_dir is not None:
        work_dir = Path(preprocess_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
    else:
        work_dir = Path(tempfile.mkdtemp(prefix="koc_media_"))

    media_info = preprocess_video(video.mp4_path, str(work_dir), n_frames=8)
    frames_list = media_info["frames"]
    duration_s = float(media_info["duration_s"])
    frame_sizes = [(f["width"], f["height"]) for f in frames_list]

    llm_client = client or get_llm_client()
    client_cfg_path = getattr(llm_client, "config_path", None)
    if not isinstance(client_cfg_path, (str, Path)):
        client_cfg_path = None
    cfg = load_pricing_config(client_cfg_path)
    max_output_tokens = int(cfg.get("token_accounting", {}).get("default_content_output_tokens", 1200))

    # Load prompt template
    prompt_tpl = PROMPT_FILE.read_text(encoding="utf-8")
    prompt_text = prompt_tpl.format(
        product_vi=brief.product_vi,
        audience_vi=brief.audience_vi,
        video_id=video.video_id,
        title=fence(video.title, 200),
        views=video.views or 0,
        likes=video.likes or 0,
        comments=video.comments or 0,
        shares=video.shares or 0,
    )

    # Build multimodal base contents
    base_contents: list[object] = [prompt_text, DATA_NOTICE_VI]
    for frame in frames_list:
        base_contents.append(f"Frame at {frame['t_s']}s:")
        base_contents.append(create_part_from_image(frame["path"]))

    audio_path_str = media_info.get("audio_path")
    has_audio = (
        audio_path_str is not None
        and Path(audio_path_str).is_file()
        and Path(audio_path_str).stat().st_size > 0
    )

    if has_audio:
        base_contents.append("Full video audio:")
        base_contents.append(create_part_from_audio(Path(audio_path_str)))
    else:
        base_contents.append(
            "Lưu ý: Video không có luồng âm thanh. "
            "Không tạo bằng chứng dạng speech/transcript, và ghi rõ rủi ro thiếu âm thanh trong risks_vi."
        )

    last_errors: list[str] = []
    last_raw_json: str = ""
    last_usage: Usage | None = None
    last_is_truncation: bool = False

    for attempt in range(2):
        if attempt == 0:
            call_contents = list(base_contents)
            prompt_version = "content_v3"
        else:
            if last_is_truncation:
                repair_instructions = (
                    "Phản hồi trước đó bị cắt ngắn do vượt quá giới hạn độ dài.\n"
                    "Yêu cầu bắt buộc khi làm lại:\n"
                    "1. Phân tích thật ngắn gọn, súc tích.\n"
                    "2. Mỗi trích dẫn quote_vi trong evidence tối đa 200 ký tự; mỗi giải trình rationale_vi tối đa 250 ký tự; danh sách evidence tối đa 12 mục.\n"
                    "3. Chỉ xuất duy nhất một đối tượng JSON hợp lệ, hoàn toàn bằng tiếng Việt, không kèm văn bản giải thích ngoài JSON."
                )
            else:
                included_output = (
                    f"\nNội dung phản hồi trước đó bị lỗi:\n{last_raw_json}"
                    if len(last_raw_json) < 4000
                    else ""
                )
                repair_instructions = (
                    "Phản hồi trước đó không hợp lệ do các lỗi sau:\n"
                    + "\n".join(f"- {e}" for e in last_errors)
                    + "\n\nYêu cầu bắt buộc khi sửa:\n"
                    + "1. Chỉ xuất duy nhất một đối tượng JSON hợp lệ, hoàn toàn bằng tiếng Việt.\n"
                    + "2. Tuyệt đối không phỏng đoán lời nói hoặc suy diễn doanh số từ hình ảnh/âm thanh.\n"
                    + "3. Mỗi quote_vi tối đa 200 ký tự; mỗi rationale_vi tối đa 250 ký tự.\n"
                    + "4. Đảm bảo đúng 7 tiêu chí rubric, mỗi tiêu chí có ít nhất một mã bằng chứng hợp lệ trích dẫn từ danh sách evidence.\n"
                    + "5. Danh sách bằng chứng evidence có tối đa 12 mục, video_id và mốc thời gian phải chính xác tuyệt đối (khớp start_s và nằm trong thời lượng phân tích)."
                    + included_output
                )
            call_contents = list(base_contents) + [repair_instructions]
            prompt_version = "content_v3_repair"

        # Conservative upper bound before every call (including repair)
        text_parts = [c for c in call_contents if isinstance(c, str)]
        client_model = getattr(llm_client, "model", None)
        model_name = client_model if isinstance(client_model, str) else None
        est_tokens, est_usd = estimate_tokens_and_usd(
            n_frames=len(frames_list),
            audio_s=duration_s if has_audio else 0.0,
            est_output_tokens=max_output_tokens,
            config_path=client_cfg_path,
            frame_sizes=frame_sizes,
            text_parts=text_parts,
            response_schema=ContentAnalysisPayload,
            has_audio=has_audio,
            model=model_name,
        )
        budget_guard.check(est_usd)

        raw_json, usage = llm_client.generate_json(
            contents=call_contents,
            response_schema=ContentAnalysisPayload,
            prompt_version=prompt_version,
            max_output_tokens=max_output_tokens,
            budget_guard=budget_guard,
            upper_bound_usd=est_usd,
            initial_check_done=True,
            est_tokens=est_tokens,
        )
        budget_guard.record(usage)
        last_usage = usage
        last_raw_json = raw_json

        finish_reason = getattr(llm_client, "last_finish_reason", None)
        is_truncation = finish_reason == "length"

        errors: list[str] = []
        if not raw_json or not raw_json.strip():
            errors.append("Phản hồi rỗng từ mô hình LLM")
            last_errors = errors
            last_is_truncation = is_truncation
            continue

        try:
            payload = ContentAnalysisPayload.model_validate_json(raw_json)
        except Exception as schema_err:
            err_str = str(schema_err)
            err_lower = err_str.lower()
            if "eof" in err_lower or "unterminated" in err_lower or is_truncation:
                is_truncation = True
                errors.append(f"Phản hồi JSON bị cắt ngắn (truncation/EOF): {schema_err}")
            else:
                errors.append(f"Lỗi cú pháp hoặc schema JSON: {schema_err}")
            last_errors = errors
            last_is_truncation = is_truncation
            continue

        payload = enforce_payload_limits(dedupe_payload(payload))

        errors = _validate_payload(
            payload,
            video_id=video.video_id,
            duration_s=duration_s,
            has_audio=has_audio,
        )
        if not errors:
            # Map Evidence frame_path by code to nearest extracted frame (Amendment A1)
            for ev in payload.evidence:
                if ev.kind == "frame" and frames_list:
                    nearest = min(frames_list, key=lambda f: abs(f["t_s"] - ev.start_s))
                    ev.frame_path = str(nearest["path"])
                else:
                    ev.frame_path = None

            final_transcript: str | None = None
            if has_audio:
                speech_quotes = [
                    ev.quote_vi.strip()
                    for ev in sorted(
                        payload.evidence,
                        key=lambda e: (e.start_s, e.end_s if e.end_s is not None else e.start_s),
                    )
                    if ev.kind == "speech" and ev.quote_vi and ev.quote_vi.strip()
                ]
                if speech_quotes:
                    joined = " ".join(speech_quotes)
                    final_transcript = truncate_at_word_boundary(joined, 1200)

            final_risks = list(payload.risks_vi)
            warning = injection_warning_vi({
                "tiêu đề": video.title,
                "lời nói/chữ trên màn hình": " ".join(ev.quote_vi for ev in payload.evidence),
                "giải trình": " ".join(r.rationale_vi for r in payload.rubric),
                "rủi ro": " ".join(payload.risks_vi),
            })
            if warning:
                final_risks.append(warning)
            if not has_audio:
                has_audio_mention = any(
                    "âm thanh" in r.lower() or "audio" in r.lower() for r in final_risks
                )
                if not has_audio_mention:
                    final_risks.append("Video không có luồng âm thanh (silent video).")

            return ContentAnalysis(
                video_id=video.video_id,
                transcript_vi=final_transcript,
                rubric=payload.rubric,
                risks_vi=final_risks,
                evidence=payload.evidence,
                usage=last_usage,
            )

        last_errors = errors
        last_is_truncation = is_truncation

    raise ValueError(f"ContentAnalysis validation failed after repair: {'; '.join(last_errors)}")
