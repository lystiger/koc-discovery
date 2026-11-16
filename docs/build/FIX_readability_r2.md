# Fix: readability round 2 (orchestrator review of 0ddf467 + merge of feat/koc-mvp@8fbef7e)

Same rules as `BRIEF_readability.md`. Data: post-S4 copy
`/tmp/claude-1000/-home-lystiger-Projects/ece17a96-b63c-4740-b5b1-fce29258bcb4/scratchpad/audit2/koc.db`.
Do not edit `src/koc/web/adapter.py`; shape in `api.py` / client.

Finding: S4 (`reasons_v4`) stores `cited_evidence_ids` per recommendation, not per point. The API hangs all 8 ids on
the first reason and the first caveat, so markers 1-8 sit on point 1 and nothing else (screenshot: KOC 7594293671543079957).

1. Evidence per point, honestly:
   - A metric id `metric:<creator>:<key>` attaches to every point whose raw text mentions `<key>` or its label.
   - Video and transcript ids do not attach to a point. Show them once per KOC as a row
     "Bằng chứng từ video: [1] [2] [3] [4]" under the strengths/weaknesses block.
   - Never attach the whole list to the first point. No point shows a marker it was not matched to.
2. Shared audience caveat: when the page-level Kalodata note is shown, drop each KOC's caveats about unverified
   audience. Match normalised text containing "khán giả" plus "Kalodata" or "chưa (được) xác minh". Also dedupe
   inside one KOC (7594293671543079957 has two). The KOC page shows the note once, not in Điểm yếu.
3. Strengths and weaknesses as bulleted lists, body text at least 15 px (now about 12 px on the KOC page),
   line-height about 1.55, and a gap between the two columns.
4. Video rows without a frame: use the same video's nearest frame within ±3 s; else show only the time chip,
   no grey "Không có ảnh" box.

Verify: full list; on all 5 real KOCs assert no point carries all ids, metric markers match their key, the audience
caveat appears 0 times inside KOC blocks and once per page, and no "Không có ảnh" box. Screenshots 375/1440 into
`docs/build/shots/readability/`. Update AC21 evidence, commit, stop.
