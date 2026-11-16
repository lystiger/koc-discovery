# RUNBOOK v2 item 4: chạy lại S3 theo video đúng chủ đề (chỉ Lystiger chạy)

Soạn ngày 2026-11-16 trên nhánh `v2/s3-rerun-prep`. Mọi lệnh dưới đây chạy từ thư mục repo chính `~/Projects/KOC-Discovery`, sau khi nhánh này và `v2/video-rerank` đã nằm trong `feat/koc-mvp` (script đọc `data/` theo thư mục hiện tại). Người soạn không gọi mạng và không chạy lệnh trả phí nào; bằng chứng diễn tập ở [EVIDENCE_v2_s3_rerun_prep.md](EVIDENCE_v2_s3_rerun_prep.md).

## 1. Việc này làm gì

Chạy một lượt mới `koc run` (không cờ) với đúng brief của lượt live `7372009b22764b339fbcf0f3efb4bc4e`: lượt live không lưu khóa `brief` trong `params_json`, nên brief rơi về mặc định (kem chống nắng, Nữ 18-30, 30.000.000 VND, 5 KOC), đúng brief đã chạy. Lượt mới dùng lại bản lưu S0/S1/S2 và 17 bản phân tích video đã có, chỉ trả tiền cho:

- tải và phân tích **13 video chưa có bản phân tích** (10 video đúng chủ đề thay đổi của 5 KOC, cộng 3 video của `@cleanboy.tips`, xem mục 2),
- viết lại lý do S4 cho các KOC trong top 5 có điểm S3 thay đổi (tối đa 5 lần gọi nhỏ).

Lượt live cũ không bị sửa. Kết quả mới là một `run_id` mới trong cùng `data/koc.db`.

```
koc run (no flags)
  S0 rank (cache 11-14, 0 credit) -> S1a/S1b (cache, 0) -> S2 (metrics in DB, 0; CDP :9333 still opened)
  -> S3: 17 analyses reused, 13 paid (video/url 0.5 credit + 1 LLM call each)
  -> S4: reasons for top 5 (cache where the creator's inputs are unchanged)
```

## 2. Điểm khác so với bản xem trước (đọc trước khi chạy)

1. **13 video, không phải 10.** `s3_rerank_preview.py` chỉ xét 9 KOC có S3 ở lượt live. Lượt live đã bỏ S3 của `7471573167103378440` (`@cleanboy.tips`) bằng tay ("tiết kiệm chi phí, đủ 9 KOC"). Lượt mới tạo tác vụ S3 cho cả 10 KOC của S2, nên sẽ trả thêm 3 video của KOC này (+1,5 tín dụng, khoảng +0,05-0,14 USD). Chọn phương án chấm đủ 10 KOC vì đó là cách đúng và không cần sửa DB bằng tay. Muốn bỏ KOC này như lượt live thì phải sửa bảng `tasks` của lượt mới bằng tay (không khuyến nghị, không có lệnh trong runbook).
2. **S2 không cần đăng nhập Kalodata, nhưng vẫn cần một trình duyệt lắng nghe ở cổng 9333.** Dữ liệu khán giả đã nằm trong bảng `metrics`, nên S2 không mở trang Kalodata nào (`ui/creator_detail` giá 0 tín dụng). Tuy vậy `pipeline.execute` vẫn gọi `connect_over_cdp("http://127.0.0.1:9333")` khi S2 bắt đầu; không có trình duyệt thì chạy dừng ở S2 với `ECONNREFUSED`. Khối lệnh bên dưới dùng Chromium đang chạy ở cổng 9333 nếu có, nếu không thì tự mở một Chromium headless với profile tạm rồi tắt khi xong. Không cần phiên đăng nhập.
3. **Hạn dùng cache 7 ngày không chặn.** Hàng cache cũ nhất của `creator/rank`, `creator/detail`, `video/rank` tạo lúc 2026-11-14 22:37 UTC; hạn dùng là 2026-11-21 22:37 UTC. Ngày 16 và 17/11 các hàng này mới 1,6-2,6 ngày tuổi nên S0/S1 tốn 0 tín dụng. **Sau 21/11 mỗi hàng hết hạn phải mua lại** (S0 2 trang x 0,1, S1b 60 x 0,2, S3 10 trang video/rank x 0,1: khoảng 13,4 tín dụng thêm): đừng trì hoãn quá ngày đó.
4. **Ước tính của `koc run --dry-run` không dùng được cho lần này.** Nó in toàn pipeline (27,6-29,4 tín dụng, 0,48-1,46 USD) và bỏ qua cache. Số đúng là mục 3.
5. `koc run` in "Đã hoàn tất lượt chạy ..." kể cả khi lượt `blocked`. Hãy đọc trạng thái trong DB (khối lệnh in sẵn).
6. **Không chạy `koc report` hay `koc benchmark` vào repo** cho lượt mới. Cả hai ghi đè `reports/benchmark.json` và `docs/BENCHMARK.md`; lượt mới chỉ trả vài giai đoạn nên đơn giá mỗi KOC bị kéo về gần 0 và làm hỏng ước tính `--dry-run` và web. Benchmark của v1 giữ nguyên. Muốn xem chi phí thật của lượt mới, ghi ra thư mục tạm (khối lệnh có sẵn).

## 3. Chi phí và hạn mức

| Khoản | Công thức | Khoảng dự kiến | Trần cứng |
|---|---|---|---|
| Tín dụng Kalodata | 13 `video/url` x 0,5 là sàn: 6,5. Cận trên = đơn vị S3 của benchmark ("tổng thực chi") x 1,3 so với bản xem trước 5,37-5,93 cho 10 video | **6,5-7,7** (S0/S1/S2 = 0 nếu cache còn hạn) | `credits_cap` = 60 trong `config/kalodata_prices.yaml`; đã dùng 37,9 nên còn 22,1. Code dừng khi vượt. |
| USD LLM | S3: 13 video x 0,015-0,045; S4: tối đa 5 x 0,0054-0,0195 | **0,23-0,69** (kế hoạch V2-7 ước 0,3-0,5) | `usd_cap` = 5 trong `config/llm_caps.yaml`; đã dùng 1,3242 nên còn 3,68. `BudgetGuard` chặn trước mỗi lần gọi. |
| Token | bản xem trước 139.500-399.696 cho 10 video, nhân 1,3, cộng S4 ~20.000-77.000 | ~0,2-0,6 triệu | không có trần riêng |
| Thời gian | S3 ~175 s mỗi KOC x 6 KOC (6 trong 10 KOC có video chưa phân tích), S4 ~29 s x 5; có thể thêm vài phút khi Kalodata trả "đang xử lý" (mã 1054, không tính phí) | 20-40 phút | |

Quy tắc dừng: nếu khối lệnh báo mức tăng tín dụng > 8,0 hoặc USD > 1,0 thì dừng và báo lại, đừng chạy tiếp. Bước 1 (smoke) tốn 0 USD và 0 tín dụng.

## 4. Bước 1: smoke trên mô hình `:free` (0 USD)

Prompt nội dung đã đổi (bỏ dòng ngân sách khỏi `prompts/content_v3.md`), nên theo quy tắc phải chứng minh trên mô hình miễn phí trước. `scripts/s3_free_smoke.py` chạy đúng `koc.llm.content.analyze_video` (8 khung hình JPEG + audio + JSON schema + bộ kiểm hợp lệ + một lần sửa) trên một video đã tải (`7701594488619191573`, @meixiuriviu) và kiểm tra prompt gửi đi không chứa chữ "ngân sách", "budget", "VND" hay con số ngân sách. Chỉ gọi OpenRouter (và danh mục mô hình công khai).

Người soạn **không xác minh được** mô hình `:free` nào nhận khung hình + audio (không có mạng). Vì vậy script tự tra danh mục công khai `https://openrouter.ai/api/v1/models`, chọn tối đa 3 mô hình `:free` có đầu vào `image` và `audio`, và có ba chế độ giảm dần. Khối lệnh thử lần lượt từng chế độ đến khi một chế độ PASS.

| Chế độ | Chứng minh | Không chứng minh |
|---|---|---|
| đầy đủ (khung hình + audio) | đúng đầu vào của bước trả phí, prompt mới, schema, bộ kiểm | chất lượng điểm của Gemini trả phí |
| `--no-audio` | prompt mới + schema + khung hình; video được tách tiếng nên prompt đi nhánh "không có âm thanh" | đường đầu vào audio |
| `--text-only` | prompt mới + schema ra JSON hợp lệ từ mô tả khung hình và lời nói đã lưu trong DB | mô hình nhìn được ảnh, nghe được audio, chất lượng điểm |

Khuyến nghị: PASS ở chế độ đầy đủ là đủ. PASS ở `--no-audio` hoặc `--text-only` vẫn là bằng chứng chấp nhận được vì thay đổi prompt chỉ là xóa một dòng ngân sách và đường audio đã chạy thật trên bản live content_v3, nhưng đó là quyết định của Lystiger; khối lệnh in rõ chế độ nào đã PASS.

```bash
(
  set -euo pipefail
  cd ~/Projects/KOC-Discovery
  test -f scripts/s3_free_smoke.py || { echo "thiếu scripts/s3_free_smoke.py: merge nhánh trước"; exit 1; }
  test -f data/media/7701594488619191573.mp4
  BK="data/koc_backup_before_s3_smoke_$(date +%Y%m%d_%H%M%S).db"
  sqlite3 -readonly data/koc.db ".backup $BK"; echo "backup: $BK"
  BEFORE=$(sha256sum data/koc.db | cut -d' ' -f1)
  read -rsp "OPENROUTER_API_KEY: " OPENROUTER_API_KEY; echo; export OPENROUTER_API_KEY
  PASSED=""
  for MODE in "" "--no-audio" "--text-only"; do
    echo; echo "##### s3_free_smoke.py $MODE"
    rc=0; .venv/bin/python scripts/s3_free_smoke.py $MODE || rc=$?
    if [ "$rc" -eq 0 ]; then PASSED="${MODE:-full}"; break; fi
    if [ "$rc" -eq 3 ]; then echo "STOP: a :free model reported a cost"; exit 3; fi
  done
  AFTER=$(sha256sum data/koc.db | cut -d' ' -f1)
  [ "$BEFORE" = "$AFTER" ] && echo "DB unchanged: OK" || { echo "DB CHANGED: STOP"; exit 1; }
  [ -n "$PASSED" ] && echo "SMOKE PASS in mode: $PASSED" || { echo "SMOKE FAIL in every mode: do not run step 2"; exit 1; }
)
```

Kết quả mong đợi (thành công):
- dòng `N :free model(s) with image+audio input: [...]` (N >= 1), sau đó mỗi mô hình in `rubric {...7 tiêu chí...}`, `validator errors []`, `budget words in prompt []`, `cost 0.0 USD`;
- `RESULT PASS: frames + audio, model <id>, cost 0 USD` (chế độ khác in thêm `NOT PROVEN by this run: ...`);
- `DB unchanged: OK` và `SMOKE PASS in mode: full` (hoặc `--no-audio` / `--text-only`).

Thất bại: `RESULT FAIL: no candidate model produced valid output`, hoặc `No :free model accepts this input` (thoát mã 2, khối lệnh tự thử chế độ kế tiếp), hoặc `STOP: model reported cost ...` (mô hình báo có phí: dừng ngay). Mô hình miễn phí hay bị giới hạn tốc độ 429 hoặc trả JSON hỏng; thử lại sau hoặc chỉ định `--model <id>:free`. Không có gì ghi vào DB ở bước này.

## 5. Bước 2: chạy trả phí

Điều kiện: bước 1 PASS, đã đọc mục 2 và 3. Khối lệnh làm theo thứ tự: sao lưu DB, kiểm tra số dư ban đầu khớp (37,9 tín dụng, 1,3242 USD), nhập khóa bằng `read -s`, diễn tập `--cache-only` trên bản sao DB (0 tín dụng, phải dừng đúng ở S3 vì thiếu tệp video), liệt kê 13 video, in `--dry-run`, hỏi xác nhận, bật Chromium cho cổng 9333 nếu chưa có, chạy thật, rồi in số liệu và so sánh top 5 cũ/mới.

```bash
(
  set -euo pipefail
  cd ~/Projects/KOC-Discovery
  TS=$(date +%Y%m%d_%H%M%S)
  BK="data/koc_backup_before_s3_rerun_$TS.db"
  sqlite3 -readonly data/koc.db ".backup $BK"; echo "backup: $BK (rollback = mục 7)"
  TMP=$(mktemp -d); trap '{ [ -z "${CPID:-}" ] || { kill "$CPID" 2>/dev/null; wait "$CPID" 2>/dev/null; }; } || true; rm -rf "$TMP"' EXIT

  # 0. the DB must be in the state this runbook was written for
  CR0=$(sqlite3 -readonly data/koc.db "select round(coalesce(sum(credits),0),2) from api_calls")
  USD0=$(sqlite3 -readonly data/koc.db "select round(coalesce(sum(cost_usd),0),4) from llm_calls")
  echo "before: $CR0 credits, $USD0 USD (expected 37.9 and 1.3242)"
  [ "$CR0" = "37.9" ] && [ "$USD0" = "1.3242" ] || { echo "DB differs from the runbook: STOP and re-check"; exit 1; }

  # 1. keys: only in this subshell's environment, never on disk
  read -rsp "KALODATA_API_KEY: " KALODATA_API_KEY; echo; read -rsp "OPENROUTER_API_KEY: " OPENROUTER_API_KEY; echo
  export KALODATA_API_KEY OPENROUTER_API_KEY

  # 2. rehearsal on a copy: 0 credits, must stop at S3 on a missing video file
  sqlite3 -readonly data/koc.db ".backup $TMP/pre.db"
  KOC_DB="$TMP/pre.db" .venv/bin/koc run --cache-only
  PRE=$(sqlite3 "$TMP/pre.db" "select run_id from runs order by started_at desc limit 1")
  sqlite3 "$TMP/pre.db" "select stage,status,count(*) from tasks where run_id='$PRE' group by 1,2"
  [ "$(sqlite3 "$TMP/pre.db" "select count(*) from tasks where run_id='$PRE' and stage='S3' and status='blocked' and error like '%tệp video%'")" = 1 ] || { echo "rehearsal did not stop at S3 as expected: STOP"; exit 1; }
  [ "$(sqlite3 "$TMP/pre.db" "select round(coalesce(sum(credits),0),2) from api_calls")" = "$CR0" ] || { echo "rehearsal spent credits: STOP"; exit 1; }
  sqlite3 -readonly data/koc.db ".backup $TMP/plan.db"
  PYTHONPATH=src .venv/bin/python scripts/s3_pending_videos.py --db "$TMP/plan.db"   # expect: needing paid analysis (*): 13; 6.5 credits

  # 3. printed estimate (whole-pipeline, ignores cache: see mục 2.4) and go/no-go
  .venv/bin/koc run --dry-run
  read -rp "Expected marginal cost 6.5-7.7 credits, 0.23-0.69 USD. Type yes to run: " ANS; [ "$ANS" = yes ]

  # 4. S2 needs something listening on CDP 9333 (no login is used: audience data is cached)
  if ! curl -fsS http://127.0.0.1:9333/json/version >/dev/null 2>&1; then
    chromium --headless=new --remote-debugging-port=9333 --user-data-dir="$TMP/chromium" about:blank >/dev/null 2>&1 &
    CPID=$!; sleep 5
  fi
  curl -fsS http://127.0.0.1:9333/json/version >/dev/null

  # 5. the paid run, same brief as the live run (no flags)
  .venv/bin/koc run

  # 6. results
  NEW=$(sqlite3 -readonly data/koc.db "select run_id from runs order by started_at desc limit 1")
  echo "new run: $NEW"
  sqlite3 -readonly data/koc.db "select status from runs where run_id='$NEW'"
  sqlite3 -readonly data/koc.db "select stage,status,count(*) from tasks where run_id='$NEW' group by 1,2"
  CR1=$(sqlite3 -readonly data/koc.db "select round(sum(credits),2) from api_calls"); USD1=$(sqlite3 -readonly data/koc.db "select round(sum(cost_usd),4) from llm_calls")
  echo "spent this run: $(sqlite3 :memory: "select round($CR1 - $CR0, 2)") credits, $(sqlite3 :memory: "select round($USD1 - $USD0, 4)") USD; totals $CR1 credits (cap 60), $USD1 USD (cap 5)"
  sqlite3 -readonly data/koc.db "select 'old' as run, r.rank, c.handle, round(s.score,1) as final, r.est_cost_vnd from recommendations r join creators c on c.creator_id=r.creator_id left join scores s on s.run_id=r.run_id and s.creator_id=r.creator_id and s.stage='S4' where r.run_id='7372009b22764b339fbcf0f3efb4bc4e' union all select 'new', r.rank, c.handle, round(s.score,1), r.est_cost_vnd from recommendations r join creators c on c.creator_id=r.creator_id left join scores s on s.run_id=r.run_id and s.creator_id=r.creator_id and s.stage='S4' where r.run_id='$NEW' order by 1 desc, 2"
  sqlite3 -readonly data/koc.db "select c.handle, json_extract(s.breakdown_json,'\$.video_selection') from scores s join creators c on c.creator_id=s.creator_id where s.run_id='$NEW' and s.stage='S3'" | cut -c1-260
  .venv/bin/koc status | tail -12

  # 7. what it really cost, written to a temp dir, NOT to the repo (mục 2.6)
  .venv/bin/koc benchmark --run "$NEW" --out-dir "/tmp/koc_bench_$NEW" && echo "benchmark of the new run: /tmp/koc_bench_$NEW (outside the repo, kept after the block)"
  git status --short reports docs/BENCHMARK.md
)
```

Kết quả mong đợi (thành công):
- `before: 37.9 credits, 1.3242 USD`.
- Diễn tập: `Đã hoàn tất lượt chạy <id>.` rồi các dòng `S0|done|1`, `S1a|done|200`, `S1b|done|60`, `S2|done|10`, `S2|skipped|30`, `S3|blocked|1`, `S3|pending|9`; sau đó `s3_pending_videos.py` in 10 dòng KOC và `videos picked: 30; needing paid analysis (*): 13; video/url cost 6.5 credits`.
- `--dry-run` kết thúc bằng `Chạy thử: không gọi mạng, không ghi dữ liệu.` (số 27,6-29,4 tín dụng là ước tính toàn pipeline, bỏ qua).
- Chạy thật in `Đã hoàn tất lượt chạy <run_id mới>.` và, nếu có, dòng số dư ngân sách. Trạng thái lượt = `done`; `tasks`: `S3|done|10`, `S4|done|1`, `S2|skipped|30`.
- Chi phí lượt này: 6,5-7,7 tín dụng và 0,23-0,69 USD; tổng không quá 45,6 tín dụng và 2,0 USD.
- Bảng so sánh top 5 cũ/mới. Điều kiện chấp nhận A4 (holdout): các video chọn của `@rio100806` đều nói về chống nắng (`video_selection` có `"on_topic": true`, không còn video dầu gội), và `@ducvietbe__` (7234931025289217051) không có video nào khớp chủ đề nên vẫn lấp bằng 3 video "deal" đánh dấu `"on_topic": false` (đã biết từ bản xem trước, không phải lỗi). Thứ hạng top 5 có thể đổi; không phải điều kiện pass/fail.
- `git status --short reports docs/BENCHMARK.md` không in gì (benchmark v1 nguyên vẹn).

Thất bại và cách xử lý:
- `ECONNREFUSED 127.0.0.1:9333`: không có Chromium ở cổng 9333 (bước 4 lỗi); chạy lại.
- Lượt `blocked` hoặc `S3|failed`: ví dụ `Yêu cầu Kalodata thất bại (...)`, `Hạn mức ... đã bị vượt`, `blocked: tài khoản LLM (nạp tiền/khóa API)`. Đọc `koc status`; sau khi sửa nguyên nhân, chạy `koc resume` (bên dưới). Không mất tiền đã trả: video đã phân tích nằm trong cache.
- Dừng giữa chừng bằng Ctrl-C hoặc mất mạng: an toàn (C5 PASS), chạy tiếp bằng:

```bash
(
  set -euo pipefail
  cd ~/Projects/KOC-Discovery
  read -rsp "KALODATA_API_KEY: " KALODATA_API_KEY; echo; read -rsp "OPENROUTER_API_KEY: " OPENROUTER_API_KEY; echo
  export KALODATA_API_KEY OPENROUTER_API_KEY
  TMP=$(mktemp -d); trap '{ [ -z "${CPID:-}" ] || { kill "$CPID" 2>/dev/null; wait "$CPID" 2>/dev/null; }; } || true; rm -rf "$TMP"' EXIT
  curl -fsS http://127.0.0.1:9333/json/version >/dev/null 2>&1 || { chromium --headless=new --remote-debugging-port=9333 --user-data-dir="$TMP/chromium" about:blank >/dev/null 2>&1 & CPID=$!; sleep 5; }
  .venv/bin/koc resume
  .venv/bin/koc status | tail -12
)
```

## 6. Sau khi chạy

- `koc status` liệt kê cả lượt cũ lẫn lượt mới. Web đọc DB nên lượt `done` mới nhất có thể thay lượt cũ ở trang đề xuất; kiểm tra bằng mắt.
- Ghi số dư mới vào HANDOVER (tín dụng và USD sau lượt này) và dán bảng so sánh top 5 vào EVIDENCE của item 4.
- Không commit `data/koc.db` (đã bị `.gitignore` bởi `*.db`).

## 7. Khôi phục (rollback)

Lượt mới chỉ thêm dòng, không sửa lượt cũ, nên thường không cần khôi phục. Nếu DB hỏng hoặc muốn xóa lượt mới: tắt web/uvicorn nếu đang chạy, rồi dùng bản sao lưu in ra ở đầu bước 2 (`data/koc_backup_before_s3_rerun_<thời gian>.db`).

```bash
(
  set -euo pipefail
  cd ~/Projects/KOC-Discovery
  BK=$(ls -1t data/koc_backup_before_s3_rerun_*.db | head -1)
  echo "restoring from $BK"
  ! pgrep -f "uvicorn|koc.web" >/dev/null || { echo "stop the web server first"; exit 1; }
  cp data/koc.db "data/koc_before_rollback_$(date +%Y%m%d_%H%M%S).db"
  cp "$BK" data/koc.db
  rm -f data/koc.db-wal data/koc.db-shm
  sqlite3 -readonly data/koc.db "pragma integrity_check; select run_id,status from runs; select round(sum(credits),2) from api_calls; select round(sum(cost_usd),4) from llm_calls"
)
```

Kết quả mong đợi: `ok`, hai lượt cũ (`e9e12714...|running` và `7372009b...|done`), `37.9`, `1.3242`. Lưu ý: khôi phục xóa cả các dòng sổ chi phí của lượt mới trong DB, nhưng tiền thật đã tiêu thì không hoàn lại; ghi số tín dụng/USD đã dùng vào HANDOVER bằng tay. Các tệp mp4 và `data/media/frames` mới tải về không cần xóa (chỉ là bộ nhớ đệm; lần sau dùng lại được).
