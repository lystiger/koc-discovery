import type { ReactNode } from 'react';
import { Collapsible } from '@base-ui/react/collapsible';
import { ChevronDown } from 'lucide-react';
import type { ExcludedKoc } from '../types';

// TikTok links are built client-side from handle and video id; nothing here calls TikTok.
const cleanHandle = (handle?: string | null) => (handle ?? '').trim().replace(/^@/, '');
// The API falls back to "@<creator_id>" when the handle is unknown: that is not a TikTok handle.
// Only TikTok-legal characters reach the URL: no "/", "?", "#", ".." or spaces can change the path or host.
const validHandle = (handle?: string | null, creatorId?: string) => { const value = cleanHandle(handle); return /^[A-Za-z0-9._]{1,40}$/.test(value) && value !== creatorId && !/^\d+$/.test(value); };
const validVideoId = (videoId?: string | null) => /^\d{1,25}$/.test(videoId ?? '');

export const tiktokProfileUrl = (handle?: string | null, creatorId?: string) => validHandle(handle, creatorId) ? `https://www.tiktok.com/@${cleanHandle(handle)}` : null;
export const tiktokVideoUrl = (handle?: string | null, videoId?: string | null, creatorId?: string) => validHandle(handle, creatorId) && validVideoId(videoId) ? `https://www.tiktok.com/@${cleanHandle(handle)}/video/${videoId}` : null;
export const videoIdFromEvidence = (evidenceId: string) => evidenceId.startsWith('metric:') ? null : evidenceId.split(/[@:]/)[0] || null;

export function TikTokLink({ handle, name, creatorId }: { handle?: string | null; name: string; creatorId?: string }) {
  const url = tiktokProfileUrl(handle, creatorId);
  if (!url) return <span className="tiktok-missing">{handle}</span>;
  return <a className="tiktok-link" href={url} target="_blank" rel="noopener noreferrer">{handle?.startsWith('@') ? handle : `@${handle}`} <span aria-hidden="true">↗</span><span className="sr-only"> — Mở trang TikTok của {name} (mở tab mới)</span></a>;
}

export function PrintProfileUrl({ handle, creatorId }: { handle?: string | null; creatorId?: string }) {
  const url = tiktokProfileUrl(handle, creatorId);
  return url ? <span className="print-url">{url.replace('https://www.', '')}</span> : null;
}

export function TikTokVideoLink({ handle, videoId, creatorId }: { handle?: string | null; videoId: string; creatorId?: string }) {
  const url = tiktokVideoUrl(handle, videoId, creatorId);
  if (!url) return null;
  return <a className="tiktok-video-link" href={url} target="_blank" rel="noopener noreferrer">Xem trên TikTok <span aria-hidden="true">↗</span><span className="sr-only"> (mở tab mới)</span></a>;
}

export type BreakdownPart = { key: string; label: string; weight: number; score: number | null; why: string; links?: ReactNode };

export function ScoreBreakdown({ parts, fit, idSuffix = '' }: { parts: BreakdownPart[]; fit: number; idSuffix?: string }) {
  return <section className="score-box" aria-label="Điểm được tính như thế nào">
    <header><strong>Điểm phù hợp {Math.round(fit)}/100</strong><a href={`#cach-cham-diem${idSuffix}`}>Cách chấm điểm</a></header>
    <div className="score-box-parts">{parts.map((part) => <div className="score-box-part" key={part.key}>
      <h4>{part.label} <small>{part.weight}%</small></h4>
      {part.score === null
        ? <p className="score-box-value missing">Chưa có dữ liệu</p>
        : <p className="score-box-value"><span><span className="tabular">{Math.round(part.score)}</span>/100</span><span className="bar-track" aria-hidden="true"><span style={{ width: `${Math.max(0, Math.min(100, part.score))}%` }} /></span></p>}
      <p className="score-box-why">{part.why}</p>
      {part.links && <p className="score-box-links">{part.links}</p>}
    </div>)}</div>
  </section>;
}

export function ScoringMethod({ idSuffix = '' }: { idSuffix?: string }) {
  return <section className="method-box" id={`cach-cham-diem${idSuffix}`} aria-labelledby={`method-title${idSuffix}`}>
    <h2 id={`method-title${idSuffix}`}>Cách chấm điểm</h2>
    <ol>
      <li><strong>Bước 0, tìm ứng viên:</strong> quét các KOC TikTok bán hàng trong danh mục sản phẩm (khoảng 200 ứng viên).</li>
      <li><strong>Bước 1, thương mại:</strong> chấm GPM video, xu hướng doanh thu, tỷ trọng video so với live và dải người theo dõi (tỷ trọng ngành chăm sóc da chỉ là proxy, không tính điểm); giữ lại 40 KOC cao điểm.</li>
      <li><strong>Bước 2, khán giả:</strong> đọc giới tính và độ tuổi khán giả cho 10 KOC. Nếu nguồn chỉ có số liệu mẫu thì ghi “chưa có dữ liệu” và bỏ phần này khỏi điểm.</li>
      <li><strong>Bước 3, nội dung:</strong> máy xem tối đa 3 video của mỗi KOC và chấm theo bảng tiêu chí (mở đầu, rõ sản phẩm, trình bày, cam kết, kêu gọi mua, phù hợp thương hiệu).</li>
      <li><strong>Bước 4, chọn nhóm:</strong> ghép điểm, loại KOC không hợp thương hiệu, chọn nhóm vừa ngân sách.</li>
    </ol>
    <p><strong>Điểm phù hợp</strong> = 45% Thương mại + 20% Khán giả + 35% Nội dung. Thiếu dữ liệu khán giả thì chia lại 45 và 35 cho đủ 100%.</p>
    <p><strong>Cổng thương hiệu:</strong> KOC chỉ được chọn nếu ít nhất một video đã phân tích đạt “phù hợp thương hiệu” từ 3/5 trở lên.</p>
    <p className="method-cost"><strong>Chi phí (ước tính):</strong> phí mỗi KOC tính theo bậc người theo dõi, nhân 3 video, cần xác nhận với KOC hoặc MCN trước khi ký. Chạy dữ liệu mới là bước có phí do nhân viên vận hành thực hiện, mất khoảng 43 phút (ước tính).</p>
  </section>;
}

export function ExcludedBox({ items }: { items?: ExcludedKoc[] }) {
  const judged = (items ?? []).filter((item) => item.max_brand_fit !== null);
  const unjudged = (items ?? []).filter((item) => item.max_brand_fit === null);
  if (!judged.length && !unjudged.length) return null;
  return <section className="excluded-box" aria-labelledby="excluded-title">
    {judged.length > 0 && <>
      <h2 id="excluded-title">Đã loại {judged.length} KOC vì không hợp thương hiệu</h2>
      <p>Mỗi KOC bị loại khi không có video nào đạt “phù hợp thương hiệu” từ 3/5. Bấm tên để xem điểm từng video.</p>
      <ul>{judged.map((item) => <ExcludedItem key={item.id} item={item} />)}</ul>
    </>}
    {unjudged.length > 0 && <Collapsible.Root className="excluded-unjudged">
      <Collapsible.Trigger className="excluded-trigger"><span>{unjudged.length} KOC khác chưa có video được phân tích, nên chưa xét được độ hợp thương hiệu</span><ChevronDown size={16} aria-hidden="true" /></Collapsible.Trigger>
      <Collapsible.Panel className="excluded-panel"><ul className="excluded-handles">{unjudged.map((item) => <li key={item.id}>{item.nickname && item.nickname !== item.handle ? `${item.nickname} · ` : ''}<TikTokLink handle={item.handle} name={item.nickname || item.handle} creatorId={item.id} /></li>)}</ul></Collapsible.Panel>
    </Collapsible.Root>}
  </section>;
}

function ExcludedItem({ item }: { item: ExcludedKoc }) {
  const name = item.nickname || item.handle;
  return <li>
    <Collapsible.Root>
      <Collapsible.Trigger className="excluded-trigger"><span><strong>{name}</strong> · {item.handle} · điểm cao nhất {item.max_brand_fit}/5</span><ChevronDown size={16} aria-hidden="true" /></Collapsible.Trigger>
      <Collapsible.Panel className="excluded-panel">
        {item.reason_vi && <p>{item.reason_vi}</p>}
        {item.videos?.length ? <ul className="excluded-videos">{item.videos.map((video, index) => <li key={video.video_id}>
          <span>Video {index + 1}: độ hợp thương hiệu <strong>{video.brand_fit === null ? 'chưa có' : `${video.brand_fit}/5`}</strong></span>
          <TikTokVideoLink handle={item.handle} videoId={video.video_id} creatorId={item.id} />
        </li>)}</ul> : <p>Chưa lưu điểm từng video.</p>}
        <p><TikTokLink handle={item.handle} name={name} creatorId={item.id} /> <PrintProfileUrl handle={item.handle} creatorId={item.id} /></p>
      </Collapsible.Panel>
    </Collapsible.Root>
  </li>;
}
