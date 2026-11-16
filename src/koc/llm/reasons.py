"""Recommendation reasons generator module (Stage 4)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING
from pydantic import BaseModel, Field

from koc.types import (
    CandidateSummary,
    BrandBrief,
    Recommendation,
    Usage,
)
from koc.llm.pricing import estimate_usd, estimate_tokens_and_usd, load_pricing_config
from koc.llm.gemini import GeminiClient
from koc.llm.factory import get_llm_client
from koc.llm.guard import DATA_NOTICE_VI, fence

if TYPE_CHECKING:
    from koc.types import BudgetGuard

PROMPT_FILE = Path(__file__).resolve().parents[3] / "prompts" / "reasons_v4.md"


class RecommendationPayload(BaseModel):
    """Schema enforced for Gemini structured JSON output for recommendations."""
    creator_id: str
    reasons_vi: list[str] = Field(default_factory=list)
    cited_evidence_ids: list[str] = Field(default_factory=list)
    caveats_vi: list[str] = Field(default_factory=list)


def build_recommendation_schema(valid_ids: set[str]) -> dict:
    """Build the strict JSON schema sent to the model for one candidate.

    All fields are required, reasons_vi has 3-5 items, and cited_evidence_ids
    has at least one item restricted to this candidate's valid evidence ids.
    """
    schema = RecommendationPayload.model_json_schema()
    props = schema["properties"]
    schema["required"] = ["creator_id", "reasons_vi", "cited_evidence_ids", "caveats_vi"]
    schema["additionalProperties"] = False
    props["reasons_vi"].update({"minItems": 3, "maxItems": 5})
    props["cited_evidence_ids"]["minItems"] = 1
    if valid_ids:
        props["cited_evidence_ids"]["items"] = {"type": "string", "enum": sorted(valid_ids)}
    return schema


def _get_valid_evidence_ids(c: CandidateSummary) -> set[str]:
    valid = set(c.metric_evidence_ids.values())
    for a in c.analyses:
        for e in a.evidence:
            valid.add(e.evidence_id)
    return valid


AUDIENCE_MISSING_CAVEAT_VI = (
    "Chưa xác minh hồ sơ khán giả (gói Kalodata không có dữ liệu khán giả); cần xác nhận trực tiếp với creator."
)
# Audience-claim screening, used only when audience_score is None (the creator's audience is unverified).
#
# Structural rule, applied per CLAUSE (sentences are split on . ; ! ? and clauses on "," ";" "nhưng" "tuy nhiên" "song"):
#  - A clause is an audience assertion when it mentions the creator's audience (khán giả, người xem, người theo dõi,
#    follower, tệp của KOC) together with a gender/age term or a percentage, or pairs a percentage with a gender/age
#    term, or says an age range ("độ tuổi 18-30") outside a brand-target clause. It is rejected unless the SAME
#    clause says it is unverified (chưa xác minh, chưa có dữ liệu, không có dữ liệu, cần xác nhận). Uncertainty about
#    another thing (e.g. conversion) in a different clause does not exempt it.
#  - A clause saying the creator's audience matches/fits something (khớp, trùng, phù hợp + khán giả của KOC/creator)
#    is rejected as well, because that match is unsupported.
#  - A brand-target restatement is allowed: a clause whose subject is the brand/campaign/product (nhãn hàng, chiến
#    dịch, thương hiệu, sản phẩm, tệp mục tiêu) with "hướng đến"/"mục tiêu", e.g. "Nhãn hàng hướng đến khán giả nữ
#    18-30 tuổi." It stays allowed unless it also asserts the creator's audience matches it.
#
# Limit: this is regex screening, a safety net and not proof of semantic support. It cannot judge paraphrases it has
# no words for. The prompt (reasons_v4) and the mandatory caveat appended in code are the primary control.
_PERCENT_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|phần trăm)", re.IGNORECASE)
_AGE_RANGE = r"\d{2}\s*[-–—]\s*\d{2}"
_DEMOGRAPHIC_RE = re.compile(rf"(?:\b(?:nữ|nam giới|giới tính|độ tuổi|tuổi|female|male|gender)\b|{_AGE_RANGE})", re.IGNORECASE)
_AUDIENCE_RE = re.compile(r"(?:khán giả|người xem|người theo dõi|follower|tệp của (?:KOC|creator))", re.IGNORECASE)
_CREATOR_AUDIENCE_RE = re.compile(r"(?:khán giả|người xem|người theo dõi|tệp|follower)\s+(?:của\s+)?(?:KOC|creator|kênh)", re.IGNORECASE)
_MATCH_RE = re.compile(r"(?:khớp|trùng|phù hợp)", re.IGNORECASE)
_AGE_PHRASE_RE = re.compile(rf"độ tuổi\s*(?:từ\s*)?{_AGE_RANGE}", re.IGNORECASE)
_BRAND_SUBJECT_RE = re.compile(r"(?:nhãn hàng|chiến dịch|thương hiệu|sản phẩm|tệp mục tiêu)", re.IGNORECASE)
_TARGET_VERB_RE = re.compile(r"(?:hướng đến|mục tiêu)", re.IGNORECASE)
_UNVERIFIED_RE = re.compile(r"(?:chưa xác minh|chưa có dữ liệu|không có dữ liệu|cần xác nhận)", re.IGNORECASE)
_CLAUSE_SPLIT_RE = re.compile(r"(?<=[.;!?])\s+|\n|;|,(?=\s)|\bnhưng\b|\btuy nhiên\b|\bsong\b", re.IGNORECASE)


def _states_audience_unverified(caveat: str) -> bool:
    text = caveat.casefold()
    return ("khán giả" in text or "người xem" in text) and ("chưa xác minh" in text or "không có dữ liệu" in text)


def _is_audience_claim(clause: str) -> bool:
    if _UNVERIFIED_RE.search(clause):
        return False
    brand_target = bool(_BRAND_SUBJECT_RE.search(clause) and _TARGET_VERB_RE.search(clause))
    if _MATCH_RE.search(clause) and _CREATOR_AUDIENCE_RE.search(clause):
        return True  # claims the creator's audience matches something
    if brand_target:
        return False  # about the brand/campaign target, not about the creator's audience
    if _AUDIENCE_RE.search(clause) and (_DEMOGRAPHIC_RE.search(clause) or _PERCENT_RE.search(clause)):
        return True
    if _PERCENT_RE.search(clause) and _DEMOGRAPHIC_RE.search(clause):
        return True
    return bool(_AGE_PHRASE_RE.search(clause))


def _audience_claims(reasons: list[str]) -> list[str]:
    """Reasons containing at least one unsupported audience assertion (see the rule above; a safety net only)."""
    return [reason for reason in reasons if any(_is_audience_claim(clause) for clause in _CLAUSE_SPLIT_RE.split(reason))]


def _validate_recommendation(
    payload: RecommendationPayload,
    expected_creator_id: str,
    valid_ids: set[str],
    audience_missing: bool = False,
) -> list[str]:
    errors = []

    # 1. Creator ID match
    if payload.creator_id != expected_creator_id:
        errors.append(f"Creator ID không khớp: mong đợi '{expected_creator_id}', nhận được '{payload.creator_id}'")

    # 2. Reason count 3 to 5
    if not (3 <= len(payload.reasons_vi) <= 5):
        errors.append(f"Số lượng lý do (reasons_vi) phải từ 3 đến 5, nhận được {len(payload.reasons_vi)}")

    # 3. Non-empty reasons
    for idx, r in enumerate(payload.reasons_vi):
        if not r or not r.strip():
            errors.append(f"Lý do thứ {idx + 1} bị rỗng")

    # 4. Citations non-empty
    if not payload.cited_evidence_ids:
        errors.append("Danh sách bằng chứng trích dẫn (cited_evidence_ids) không được rỗng")

    # 5. Citation membership
    invalid_ids = set(payload.cited_evidence_ids) - valid_ids
    if invalid_ids:
        errors.append(f"Mã bằng chứng trích dẫn không tồn tại trong dữ liệu đầu vào: {sorted(invalid_ids)}")

    # 6. Duplicate citations
    if len(payload.cited_evidence_ids) != len(set(payload.cited_evidence_ids)):
        errors.append("Mã bằng chứng trích dẫn có phần tử trùng lặp")

    # 7. No audience demographic claims when the audience is unverified
    if audience_missing:
        for reason in _audience_claims(payload.reasons_vi):
            errors.append(f"Lý do nêu tỷ lệ giới tính/độ tuổi dù chưa có dữ liệu khán giả: '{reason}'")

    return errors


def write_reasons(
    c: CandidateSummary,
    brief: BrandBrief,
    *,
    budget_guard: BudgetGuard,
    client: GeminiClient | None = None,
) -> Recommendation:
    """Generate 3-5 recommendation reasons and caveats for a KOC candidate.

    Cites only evidence IDs provided in CandidateSummary (metrics and video analyses).
    Enforces validation and retries once on invalid evidence, wrong creator, or reason count.
    """
    llm_client = client or get_llm_client()
    client_cfg_path = getattr(llm_client, "config_path", None)
    if not isinstance(client_cfg_path, (str, Path)):
        client_cfg_path = None
    cfg = load_pricing_config(client_cfg_path)
    max_output_tokens = int(cfg.get("token_accounting", {}).get("default_reasons_output_tokens", 800))
    valid_ids = _get_valid_evidence_ids(c)

    # Build prompt summaries
    metrics_summary_lines = []
    for k, v in c.metrics.items():
        eid = c.metric_evidence_ids.get(k, f"metric:{c.creator_id}:{k}")
        metrics_summary_lines.append(f"- {k}: {v} (ID: {eid})")
    metrics_summary = "\n".join(metrics_summary_lines) or "Không có số liệu bổ sung."

    video_evidence_lines = []
    for a in c.analyses:
        video_evidence_lines.append(f"Video {a.video_id}:")
        for e in a.evidence:
            video_evidence_lines.append(f"  - [{e.kind}] {fence(e.quote_vi, 200)} (ID: {e.evidence_id}, {e.start_s}s)")
    video_evidence_summary = "\n".join(video_evidence_lines) or "Chưa có bằng chứng video."

    valid_ids_str = "\n".join(f"- {eid}" for eid in sorted(valid_ids))

    prompt_tpl = PROMPT_FILE.read_text(encoding="utf-8")
    prompt_text = prompt_tpl.format(
        product_vi=brief.product_vi,
        audience_vi=brief.audience_vi,
        budget_vnd=brief.budget_vnd,
        handle=c.handle,
        creator_id=c.creator_id,
        followers=c.followers or "Không rõ",
        est_cost_vnd=c.est_cost_vnd,
        final_score=c.final_score,
        commercial_score=c.commercial_score,
        audience_score=f"{c.audience_score:.1f}" if c.audience_score is not None else "không có dữ liệu",
        content_score=f"{c.content_score:.1f}" if c.content_score is not None else "N/A",
        metrics_summary=metrics_summary,
        video_evidence_summary=video_evidence_summary,
        valid_evidence_ids=valid_ids_str,
    )

    # Gemini client takes the pydantic class; OpenRouter takes the per-call strict dict.
    response_schema = (
        RecommendationPayload
        if isinstance(llm_client, GeminiClient)
        else build_recommendation_schema(valid_ids)
    )

    last_errors: list[str] = []
    last_raw_json: str = ""
    last_usage: Usage | None = None

    prompt_text = prompt_text + "\n\n" + DATA_NOTICE_VI

    for attempt in range(2):
        if attempt == 0:
            call_contents = [prompt_text]
            prompt_version = "reasons_v4"
        else:
            prompt_version = "reasons_v4_repair"
            repair_instructions = (
                "Bản đề xuất trước đó không hợp lệ do các lỗi sau:\n"
                + "\n".join(f"- {e}" for e in last_errors)
                + "\n\nYêu cầu bắt buộc khi sửa:\n"
                + "1. Chỉ xuất duy nhất một đối tượng JSON hợp lệ, hoàn toàn bằng tiếng Việt.\n"
                + f"2. creator_id phải chính xác là '{c.creator_id}'.\n"
                + "3. Cung cấp đúng từ 3 đến 5 lý do trong reasons_vi bằng tiếng Việt rõ ràng.\n"
                + "4. Bắt buộc có ít nhất một mã bằng chứng trong cited_evidence_ids, và chỉ được trích dẫn các mã có trong danh sách sau:\n"
                + valid_ids_str
                + "\n5. Tuyệt đối không suy diễn doanh số hoặc bịa đặt thông tin không có trong số liệu.\n"
                + f"\nNội dung phản hồi trước đó bị lỗi:\n{last_raw_json}"
            )
            call_contents = [prompt_text, repair_instructions]

        # Conservative upper bound before every call (including repair)
        text_parts = [c for c in call_contents if isinstance(c, str)]
        client_model = getattr(llm_client, "model", None)
        model_name = client_model if isinstance(client_model, str) else None
        est_tokens, est_usd = estimate_tokens_and_usd(
            n_frames=0,
            audio_s=0.0,
            est_output_tokens=max_output_tokens,
            config_path=client_cfg_path,
            text_parts=text_parts,
            response_schema=response_schema,
            has_audio=False,
            model=model_name,
        )
        budget_guard.check(est_usd)

        raw_json, usage = llm_client.generate_json(
            contents=call_contents,
            response_schema=response_schema,
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

        errors: list[str] = []
        if not raw_json or not raw_json.strip():
            errors.append("Phản hồi rỗng từ Gemini API")
            last_errors = errors
            continue

        try:
            payload = RecommendationPayload.model_validate_json(raw_json)
        except Exception as schema_err:
            errors.append(f"Lỗi cú pháp hoặc schema JSON: {schema_err}")
            last_errors = errors
            continue

        audience_missing = c.audience_score is None
        errors = _validate_recommendation(
            payload, expected_creator_id=c.creator_id, valid_ids=valid_ids, audience_missing=audience_missing
        )
        if not errors:
            caveats = list(payload.caveats_vi)
            if audience_missing and not any(_states_audience_unverified(cv) for cv in caveats):
                caveats.append(AUDIENCE_MISSING_CAVEAT_VI)
            return Recommendation(
                creator_id=payload.creator_id,
                reasons_vi=payload.reasons_vi,
                cited_evidence_ids=payload.cited_evidence_ids,
                caveats_vi=caveats,
                usage=last_usage,
            )

        last_errors = errors

    raise ValueError(f"Recommendation validation failed after repair: {'; '.join(last_errors)}")


def validate_cached_recommendation(rec: Recommendation, c: CandidateSummary) -> Recommendation:
    """Re-validate a cached recommendation against the candidate's current audience state.

    Returns the recommendation with the mandatory caveat appended when needed, or raises ValueError
    when it cites unknown evidence or makes unsupported audience claims.
    """
    payload = RecommendationPayload(creator_id=rec.creator_id, reasons_vi=rec.reasons_vi,
                                    cited_evidence_ids=rec.cited_evidence_ids, caveats_vi=rec.caveats_vi)
    audience_missing = c.audience_score is None
    errors = _validate_recommendation(payload, c.creator_id, _get_valid_evidence_ids(c), audience_missing=audience_missing)
    if errors:
        raise ValueError("; ".join(errors))
    if audience_missing and not any(_states_audience_unverified(cv) for cv in rec.caveats_vi):
        return rec.model_copy(update={"caveats_vi": [*rec.caveats_vi, AUDIENCE_MISSING_CAVEAT_VI]})
    return rec
