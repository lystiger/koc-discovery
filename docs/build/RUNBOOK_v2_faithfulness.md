# RUNBOOK v2 item 5: chấm độ trung thực của lý do S4 (chỉ Lystiger chạy)

Chạy từ thư mục repo chính `~/Projects/KOC-Discovery` sau khi nhánh `v2/faithfulness` đã nằm trong `feat/koc-mvp`. Người soạn không gọi mạng và không chạy lệnh trả phí nào. Bằng chứng: [EVIDENCE_v2_faithfulness.md](EVIDENCE_v2_faithfulness.md).

Lệnh `koc faithfulness` ghi một bảng mới `faithfulness` vào `data/koc.db` (tự tạo) và các dòng `llm_calls` loại `faithfulness` (không gắn `run_id`, nên không lẫn vào benchmark chi phí S3/S4). Chạy lại cùng đầu vào tốn 0 lượt gọi.

## Khối 1: thử miễn phí (0 USD, dừng nếu mã thoát 3)

Script sao chép DB sang thư mục tạm, chấm bằng mô hình `:free`, rồi chạy lại để chứng minh lần hai 0 lượt gọi. Mã thoát 0 = PASS, 1 = FAIL, 3 = mô hình báo chi phí khác 0 (dừng, không chạy khối 2).

```bash
(
  set -euo pipefail
  cd ~/Projects/KOC-Discovery
  mkdir -p data/backup
  sqlite3 -readonly data/koc.db ".backup data/backup/koc.faith-$(date +%Y%m%d-%H%M%S).db"
  read -r -s -p "OPENROUTER_API_KEY: " OPENROUTER_API_KEY; echo
  export OPENROUTER_API_KEY
  set +e
  .venv/bin/python scripts/faithfulness_free_smoke.py baidu/ernie-5.5-flash-preview:free 7372009b22764b339fbcf0f3efb4bc4e
  code=$?
  set -e
  if [ "$code" -eq 3 ]; then echo "DUNG: mo hinh bao chi phi > 0 (ma 3). Khong chay khoi 2."; exit 3; fi
  if [ "$code" -ne 0 ]; then echo "FAIL (ma $code). Khong chay khoi 2."; exit "$code"; fi
  echo "Thu mien phi dat (0 USD)."
)
```

## Khối 2: chạy thật (trả phí, có xác nhận)

In ước tính trước (không gọi mạng), chờ gõ đúng `yes`, rồi chạy và in số USD đã chi (chênh lệch tổng `llm_calls` trước và sau). Hạn mức USD là `config/llm_caps.yaml` (`usd_cap`), tính trên tổng mọi lượt gọi LLM.

```bash
(
  set -euo pipefail
  cd ~/Projects/KOC-Discovery
  RUN=0e555cac95fb4fb49168410e40ea92d5
  mkdir -p data/backup
  sqlite3 -readonly data/koc.db ".backup data/backup/koc.faith-paid-$(date +%Y%m%d-%H%M%S).db"
  read -r -s -p "OPENROUTER_API_KEY: " OPENROUTER_API_KEY; echo
  export OPENROUTER_API_KEY
  .venv/bin/python -m koc.cli faithfulness --run "$RUN" --dry-run
  read -r -p "Chay that va tra phi? Go 'yes' de tiep tuc: " answer
  [ "$answer" = "yes" ] || { echo "Da huy."; exit 1; }
  before=$(sqlite3 data/koc.db "SELECT COALESCE(SUM(cost_usd),0) FROM llm_calls")
  .venv/bin/python -m koc.cli faithfulness --run "$RUN"
  after=$(sqlite3 data/koc.db "SELECT COALESCE(SUM(cost_usd),0) FROM llm_calls")
  echo "USD da chi: $(python3 -c "print(round($after - $before, 6))")"
  echo "Chay lai se ton 0 lan goi: .venv/bin/python -m koc.cli faithfulness --run $RUN --cache-only"
)
```

Sau đó ghi điểm vào benchmark (ghi đè `reports/benchmark.json` và `docs/BENCHMARK.md`, nên chỉ làm khi muốn cập nhật bản phát hành): `.venv/bin/python -m koc.cli benchmark --run "$RUN"`. Mục 10 chỉ xuất hiện khi lượt chạy đã được chấm.
