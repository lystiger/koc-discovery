import { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api';
import type { OpsRun } from '../types';
import { TitleBlock } from './SharedSite';

const statusLabels: Record<string, string> = {
  done: 'Hoàn tất', blocked: 'Bị chặn', running: 'Đang chạy', pending: 'Đang chờ', failed: 'Thất bại',
};
const stageLabels: Record<string, string> = {
  S0: 'Lọc người sáng tạo', S1: 'Điểm thương mại', S2: 'Phân tích khán giả', S3: 'Phân tích nội dung', S4: 'Đề xuất',
};
const calibrationLabels: Record<string, string> = {
  views: 'Lượt xem', gpm: 'Doanh thu trên 1.000 lượt xem',
};

export function OperatorPage() {
  const [runs, setRuns] = useState<OpsRun[]>([]);
  const [error, setError] = useState('');
  useEffect(() => { api.runs().then(setRuns).catch((reason: Error) => setError(reason.message)); }, []);
  const chartData = useMemo(() => runs.slice(0, 8).map((run) => ({ name: new Date(run.started_at).toLocaleDateString('vi-VN'), credits: run.costs.credits, tokens: run.costs.input_tokens + run.costs.output_tokens })), [runs]);
  if (error) return <section className="page narrow empty-state"><p>{error}</p></section>;
  return <section className="page ops-page"><div className="page-heading"><TitleBlock subtitle="Chi phí và trạng thái xử lý của các lượt chạy.">Vận hành</TitleBlock></div>
    {runs.length === 0 ? <p>Chưa có lượt chạy.</p> : <>
      <section className="ops-chart"><h2>Tín dụng và lượng token theo lượt chạy</h2><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={chartData}><CartesianGrid strokeDasharray="3 3" stroke="#e3ddd3" /><XAxis dataKey="name" /><YAxis yAxisId="credits" /><YAxis yAxisId="tokens" orientation="right" /><Tooltip /><Legend /><Bar yAxisId="credits" dataKey="credits" name="Tín dụng" fill="#315f53" /><Bar yAxisId="tokens" dataKey="tokens" name="Token" fill="#b78355" /></BarChart></ResponsiveContainer></div></section>
      <div className="ops-table-wrap" role="region" aria-label="Bảng chi phí lượt chạy" tabIndex={0}><table><thead><tr><th>Lượt chạy</th><th>Trạng thái</th><th>Tín dụng</th><th>Token vào</th><th>Token ra</th><th>Chi phí USD</th><th>Độ trễ</th></tr></thead><tbody>{runs.map((run) => <tr key={run.run_id}><td>{run.run_id.slice(0, 10)} · {new Date(run.started_at).toLocaleString('vi-VN')}</td><td>{statusLabels[run.status] || 'Trạng thái khác'}</td><td>{run.costs.credits}</td><td>{run.costs.input_tokens.toLocaleString('vi-VN')}</td><td>{run.costs.output_tokens.toLocaleString('vi-VN')}</td><td>{run.costs.cost_usd.toFixed(4)}</td><td>{run.costs.api_latency_ms.toLocaleString('vi-VN')} ms</td></tr>)}</tbody></table></div>
      {runs.map((run) => <section className="run-summary" key={run.run_id}><h2>{run.run_id}</h2><div className="task-grid">{run.tasks.map((task) => <p key={`${task.stage}-${task.status}`}>{stageLabels[task.stage] || 'Giai đoạn khác'} · {statusLabels[task.status] || 'Trạng thái khác'}: {task.count}</p>)}</div><p>Tương quan thứ hạng: {Object.entries(run.calibration).map(([name, value]) => `${calibrationLabels[name.replace('spearman_', '')] || 'Chỉ số khác'} ${value}`).join(' · ') || 'Chưa có dữ liệu'}</p></section>)}
    </>}
  </section>;
}
