import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import NumberFlow from '@number-flow/react';
import { Dialog } from '@base-ui/react/dialog';
import { Select } from '@base-ui/react/select';
import { Slider } from '@base-ui/react/slider';
import { Drawer } from 'vaul';
import { toast } from 'sonner';
import { Check, ChevronDown, ChevronLeft } from 'lucide-react';
import { api, formatFollowers, formatVnd } from '../api';
import { BudgetStrip } from './BudgetStrip';
import type { Campaign, CampaignInput, Creator, CreatorDetail, PreviousRun, RunEstimate, RunProposal } from '../types';
import { applyFilter, FilterBar, FilterEmpty, filterActive, readFilter, writeFilter, type CreatorFilter } from './filters';
import mascotUrl from '../assets/mascot.webp';
import { BrandLogo } from './BrandLogo';
import { ExcludedBox, PrintProfileUrl, ScoreBreakdown, ScoringMethod, TikTokLink, TikTokVideoLink, videoIdFromEvidence, type BreakdownPart } from './explain';
import { PrimaryButton, PrimaryLink, SecondaryLink, StepIndicator, TitleBlock } from './SharedSite';

const initialForm: CampaignInput = {
  brand_name: '', product_type: 'Chống nắng', product_specs: '', budget_vnd: 30_000_000,
  count: 5, followers_min: 10_000, followers_max: 300_000,
  target: { gender: 'Nữ', age_groups: ['18-24', '25-34'] }, avoid_same_mcn: true,
};
const productTypes = ['Chống nắng', 'Dưỡng ẩm', 'Serum', 'Làm sạch', 'Trang điểm', 'Khác'];
const ageBuckets = ['18-24', '25-34', '35-44', '45-54', '55+'] as const;
type AgeBucket = (typeof ageBuckets)[number];
const agePicks: { label: string; range: readonly [AgeBucket, AgeBucket] }[] = [
  { label: 'Gen Z · 18–24', range: ['18-24', '18-24'] },
  { label: '18–34', range: ['18-24', '25-34'] },
  { label: 'Người đi làm · 25–34', range: ['25-34', '25-34'] },
  { label: '25–44', range: ['25-34', '35-44'] },
  { label: '35–54', range: ['35-44', '45-54'] },
];
const ageRangeLabel = (range: readonly [AgeBucket, AgeBucket]) => range[1] === '55+'
  ? `${range[0].slice(0, 2)} tuổi trở lên`
  : `${range[0].slice(0, 2)}–${range[1].slice(-2)} tuổi`;
const targetAgeRange = (ages: AgeBucket[]) => [ageBuckets.indexOf(ages[0]), ageBuckets.indexOf(ages.at(-1)!)] as const;
const selectedAgeGroups = (values: readonly number[]) => ageBuckets.slice(values[0], values[1] + 1);
const targetAudienceLabel = (target: CampaignInput['target']) => {
  const gender = target.gender === 'Nữ' ? 'nữ' : target.gender === 'Nam' ? 'nam' : 'mọi giới';
  return `Khán giả ${gender}, ${ageRangeLabel([target.age_groups[0], target.age_groups.at(-1)!])}`;
};
const formatInputNumber = (value: number) => new Intl.NumberFormat('vi-VN').format(value);
const parseInputNumber = (value: string) => Number(value.replace(/\D/g, '') || 0);
const campaignPicks = (campaign: Campaign) => campaign.result.picked ?? [];

function displayReason(value: string) {
  return value
    .replace(/\b(thương mại|khán giả|nội dung|phù hợp)\s+S[1-4]\b/gi, '$1')
    .replace(/\bS([1-4])\b/g, (_, stage: string) => ({ '1': 'thương mại', '2': 'khán giả', '3': 'nội dung', '4': 'phù hợp' } as Record<string, string>)[stage] ?? stage)
    .replace(/\b(\d{2})-(\d{2})\b/g, '$1–$2')
    .replace(/(\d+)\.(\d+)(?=%|\/100\b|s\b)/g, '$1,$2');
}

function formatReasonNumbers(value: string) {
  return displayReason(value)
    .replace(/\b\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\b\d{4,}(?:[.,]\d+)?/g, (number) => {
      const normalized = number.replace(/[.,](?=\d{3}(?:[.,]|$))/g, '').replace(',', '.');
      const value = Number(normalized);
      return value >= 1000 ? Math.round(value).toLocaleString('vi-VN') : number;
    })
    .replace(/\b(1(?:[.,]0+)?)\b(?=\s*(?:tỷ trọng|tỷ lệ|share|ratio))/gi, '100%');
}

function summaryText(creator: Pick<Creator, 'fit' | 'components' | 'audience_age_missing'>) {
  const band = (value: number) => value >= 80 ? 'mạnh' : value >= 60 ? 'khá' : 'yếu';
  const parts = [`Phù hợp ${Math.round(creator.fit)}/100`];
  parts.push(creator.components.commercial === null ? 'chưa có dữ liệu bán hàng' : `bán hàng ${band(creator.components.commercial)} (${Math.round(creator.components.commercial)})`);
  parts.push(creator.components.content === null ? 'chưa có dữ liệu nội dung' : `nội dung ${band(creator.components.content)} (${Math.round(creator.components.content)})`);
  if (creator.components.audience === null) parts.push('chưa có dữ liệu khán giả');
  else parts.push(`khán giả ${band(creator.components.audience)} (${Math.round(creator.components.audience)})`);
  if (creator.audience_age_missing) parts.push('thiếu dữ liệu độ tuổi');
  return parts.join(' · ');
}

function evidenceNumbers(creators: Creator[]) {
  const numbers = new Map<string, number>();
  creators.flatMap((creator) => [...(creator.reasons ?? []).flatMap((item) => item.evidence_ids), ...(creator.caveats ?? []).flatMap((item) => item.evidence_ids), ...(creator.video_evidence_ids ?? [])])
    .forEach((id) => { if (!numbers.has(id)) numbers.set(id, numbers.size + 1); });
  return numbers;
}

function EvidenceMarkers({ ids, numbers, creatorId, runId, detail = false }: { ids: string[]; numbers: Map<string, number>; creatorId: string; runId?: string; detail?: boolean }) {
  const location = useLocation();
  return <span className="evidence-markers">{ids.map((id) => {
    const target = detail ? `#${encodeURIComponent(id)}` : runId ? `/de-xuat/${runId}/koc/${creatorId}#${encodeURIComponent(id)}` : `/koc/${creatorId}#${encodeURIComponent(id)}`;
    return <Link className="evidence-marker" key={id} to={target} state={detail ? undefined : { backgroundLocation: location }} aria-label={`Bằng chứng ${numbers.get(id)}: ${evidenceLinkName(id)}`} onClick={() => window.setTimeout(() => revealEvidence(id), 250)}>{numbers.get(id)}</Link>;
  })}</span>;
}

function revealEvidence(id: string, attempts = 0) {
  const target = document.getElementById(id);
  if (!target) {
    if (attempts < 40) window.setTimeout(() => revealEvidence(id, attempts + 1), 50);
    return;
  }
  for (let node = target.closest('details'); node; node = node.parentElement?.closest('details') ?? null) node.setAttribute('open', '');
  target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  target.classList.add('evidence-highlight');
  window.setTimeout(() => target.classList.remove('evidence-highlight'), 1400);
}

function EvidenceNumbers({ ids, numbers }: { ids: string[]; numbers: Map<string, number> }) {
  return <span className="evidence-markers">{ids.map((id) => <span className="evidence-marker" key={id}>{numbers.get(id)}</span>)}</span>;
}

const shortMetric: Record<string, string> = {
  video_gpm: 'GPM video', skincare_revenue_share: 'tỷ trọng ngành chăm sóc da', revenue_trend_slope: 'xu hướng doanh thu',
  video_vs_live_share: 'tỷ trọng video', engagement_per_view: 'tương tác trên lượt xem', follower_band_fit: 'khoảng người theo dõi',
};

type BreakdownInput = {
  creatorId: string; runId?: string; detail?: boolean; fit: number;
  parts: { commercial: number | null; audience: number | null; content: number | null };
  evidenceIds: string[]; videoIds: string[]; analysedVideoIds?: string[]; audienceMissing?: boolean; ageMissing?: boolean;
  commercialWhy?: string; contentWhy?: string;
};

function AnchorLinks({ items, creatorId, runId, detail }: { items: { id: string; label: string; name: string }[]; creatorId: string; runId?: string; detail?: boolean }) {
  const location = useLocation();
  return <>{items.map((item, index) => {
    const to = detail ? `#${encodeURIComponent(item.id)}` : runId ? `/de-xuat/${runId}/koc/${creatorId}#${encodeURIComponent(item.id)}` : `/koc/${creatorId}#${encodeURIComponent(item.id)}`;
    return <span key={item.id}>{index > 0 && ' · '}<Link to={to} state={detail ? undefined : { backgroundLocation: location }} aria-label={item.name} onClick={() => window.setTimeout(() => revealEvidence(item.id), 250)}>{item.label}</Link></span>;
  })}</>;
}

function CreatorBreakdown({ input, idSuffix = '' }: { input: BreakdownInput; idSuffix?: string }) {
  const metricNames = [...new Set(input.evidenceIds.filter((id) => id.startsWith('metric:')).map((id) => id.split(':').at(-1) ?? ''))].filter((name) => shortMetric[name]);
  const videos = [...new Set((input.analysedVideoIds ?? input.videoIds).map(videoIdFromEvidence).filter((id): id is string => Boolean(id)))];
  const link = { creatorId: input.creatorId, runId: input.runId, detail: input.detail };
  const commercialWhy = input.commercialWhy ?? (metricNames.length ? `Dựa trên ${metricNames.map((name) => shortMetric[name]).join(', ')} từ dữ liệu bán hàng.` : 'Tính từ số liệu bán hàng Kalodata (GPM video, tỷ trọng ngành, xu hướng doanh thu).');
  const contentWhy = input.contentWhy ?? (videos.length ? `Máy xem ${videos.length} video và chấm theo bảng tiêu chí nội dung; bấm số video để xem đoạn được trích.` : 'Chưa có video được trích dẫn cho phần này.');
  const audienceWhy = input.parts.audience === null
    ? `Chưa có dữ liệu khán giả đã xác minh${input.audienceMissing ? ' (nguồn chỉ có số liệu mẫu)' : ''}; phần này không tính vào tổng.`
    : `Mức khớp khán giả hiện có với giới tính và nhóm tuổi đã chọn${input.ageMissing ? ' (thiếu dữ liệu độ tuổi)' : ''}.`;
  const parts: BreakdownPart[] = [
    { key: 'commercial', label: 'Thương mại', weight: 45, score: input.parts.commercial, why: commercialWhy, links: metricNames.length ? <AnchorLinks {...link} items={metricNames.map((name) => ({ id: `metric:${input.creatorId}:${name}`, label: shortMetric[name], name: `Đến số liệu ${shortMetric[name]}` }))} /> : undefined },
    { key: 'audience', label: 'Khán giả', weight: 20, score: input.parts.audience, why: audienceWhy },
    { key: 'content', label: 'Nội dung', weight: 35, score: input.parts.content, why: contentWhy, links: videos.length ? <AnchorLinks {...link} items={videos.map((id, index) => ({ id: `video-${id}`, label: `Video ${index + 1}`, name: `Đến bằng chứng của video ${index + 1}` }))} /> : undefined },
  ];
  return <ScoreBreakdown parts={parts} fit={input.fit} idSuffix={idSuffix} />;
}

function ReviewColumns({ strengths, weaknesses, numbers, creatorId, runId, detail = false, videoEvidenceIds = [] }: { strengths: { text: string; evidence_ids: string[] }[]; weaknesses: { text: string; evidence_ids: string[] }[]; numbers: Map<string, number>; creatorId: string; runId?: string; detail?: boolean; videoEvidenceIds?: string[] }) {
  return <div className="review-block"><div className="review-columns"><section><h3>Điểm mạnh</h3><ul>{strengths.length ? strengths.map((item, i) => <li key={i}>{formatReasonNumbers(item.text)} <EvidenceMarkers ids={item.evidence_ids} numbers={numbers} creatorId={creatorId} runId={runId} detail={detail} /></li>) : <li>Chưa có thông tin.</li>}</ul></section><section><h3>Điểm yếu</h3><ul>{weaknesses.length ? weaknesses.map((item, i) => <li key={i}>{formatReasonNumbers(item.text)} <EvidenceMarkers ids={item.evidence_ids} numbers={numbers} creatorId={creatorId} runId={runId} detail={detail} /></li>) : <li>Chưa có lưu ý.</li>}</ul></section></div>{videoEvidenceIds.length > 0 && <p className="video-evidence-links"><strong>Bằng chứng từ video:</strong> <EvidenceMarkers ids={videoEvidenceIds} numbers={numbers} creatorId={creatorId} runId={runId} detail={detail} /></p>}</div>;
}

function isAudienceCaveat(text: string) {
  const normalized = text.normalize('NFKC').replace(/\s+/g, ' ').trim().toLocaleLowerCase('vi');
  return normalized.includes('khán giả') && (normalized.includes('kalodata') || /chưa\s+(?:được\s+)?xác minh/.test(normalized));
}

function sharedCaveats(creators: Creator[]) {
  if (!creators.length) return { shared: [], visible: creators };
  const audienceNote = creators.map((creator) => creator.audience_note).find((text) => text) ?? creators.flatMap((creator) => creator.caveats ?? []).find((item) => isAudienceCaveat(item.text))?.text;
  const withoutAudience = creators.map((creator) => ({ ...creator, caveats: creator.caveats?.filter((item) => !isAudienceCaveat(item.text)) }));
  const common = new Map((withoutAudience[0].caveats ?? []).map((item) => [item.text.normalize('NFKC').replace(/\s+/g, ' ').trim().toLocaleLowerCase('vi'), item]));
  for (const creator of withoutAudience.slice(1)) {
    const texts = new Set((creator.caveats ?? []).map((item) => item.text.normalize('NFKC').replace(/\s+/g, ' ').trim().toLocaleLowerCase('vi')));
    for (const key of common.keys()) if (!texts.has(key)) common.delete(key);
  }
  const keys = new Set(common.keys());
  return { shared: [...(audienceNote ? [{ text: audienceNote, evidence_ids: [] }] : []), ...common.values()], visible: withoutAudience.map((creator) => ({ ...creator, caveats: creator.caveats?.filter((item) => !keys.has(item.text.normalize('NFKC').replace(/\s+/g, ' ').trim().toLocaleLowerCase('vi'))) })) };
}

function useCampaign(id: string | undefined) {
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    if (id) api.campaign(id).then((value) => { if (active) setCampaign(value); }).catch((reason: Error) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [id]);
  return { campaign, error };
}

function Loading({ error }: { error?: string }) {
  return <section className="page narrow empty-state"><p>{error || 'Đang tải dữ liệu…'}</p></section>;
}

export function CampaignListPage() {
  const [items, setItems] = useState<(Pick<Campaign, 'campaign_id' | 'created_at' | 'input'> & { picked_count: number; status?: 'ok' | 'refused' | 'needs_run'; result?: { status?: 'ok' | 'refused' | 'needs_run' } })[]>([]);
  const [error, setError] = useState('');
  const [hasRun, setHasRun] = useState(false);
  useEffect(() => {
    api.campaigns()
      .then((campaigns) => Promise.all(campaigns.map(async (item) => {
        try { return { ...item, result: (await api.campaign(item.campaign_id)).result }; }
        catch { return item; }
      })))
      .then(setItems)
      .catch((reason: Error) => setError(reason.message));
  }, []);
  useEffect(() => {
    api.latestRun().then(({ run_id }) => api.runProposal(run_id)).then(() => setHasRun(true)).catch(() => setHasRun(false));
  }, []);
  return <section className="page narrow">
    <div className="page-heading"><TitleBlock subtitle="Theo dõi chiến dịch và các KOC được đề xuất.">Chiến dịch <em>của tôi</em></TitleBlock>{items.length > 0 && <PrimaryLink to="/chien-dich/moi">Tạo chiến dịch</PrimaryLink>}</div>
    {error && <p role="alert" className="notice warning">{error}</p>}
    {items.length === 0 ? <div className="campaign-empty">
      <img className="campaign-empty-mascot" src={mascotUrl} alt="" width="96" height="96" />
      <h2>Chưa có chiến dịch nào</h2>
      <p>Tạo chiến dịch để xem KOC phù hợp với sản phẩm và ngân sách của bạn.</p>
      <PrimaryLink to="/chien-dich/moi">Tạo chiến dịch đầu tiên</PrimaryLink>
      {hasRun && <SecondaryLink to="/de-xuat">Xem một bản đề xuất mẫu</SecondaryLink>}
    </div> : <div className="campaign-list">
      {items.map((item) => {
        const count = item.input.count;
        const picked = item.picked_count;
        const resultStatus = item.status ?? item.result?.status;
        const needsRun = resultStatus === 'needs_run';
        const refused = resultStatus === 'refused';
        const status = needsRun ? 'needs-run' : refused ? 'refused' : picked === 0 ? 'no-picks' : picked < count ? 'incomplete' : 'ready';
        const statusText = needsRun ? 'Chờ chạy dữ liệu' : refused ? 'Ngân sách chưa đủ' : status === 'no-picks' ? 'Chưa có KOC phù hợp' : status === 'incomplete' ? 'Thiếu KOC' : 'Đã có đề xuất';
        const createdAt = new Date(item.created_at);
        const createdLabel = `${createdAt.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' })}, ${createdAt.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}`;
        return <article className="campaign-card" key={item.campaign_id}>
          <Link className="campaign-card-main" to={`/chien-dich/${item.campaign_id}`}>
            <strong className="campaign-brand">{item.input.brand_name}</strong>
            <span className="campaign-meta">{item.input.product_type} · {createdLabel}</span>
            <span className="campaign-budget tabular">{formatVnd(item.input.budget_vnd)}</span>
            <span className="campaign-count">{picked}/{count} KOC</span>
            <span className={`campaign-status campaign-status-${status}`}>{statusText}</span>
          </Link>
          {!needsRun && !refused && picked > 0 && <SecondaryLink className="campaign-proposal" to={`/chien-dich/${item.campaign_id}/de-xuat`}>Bản đề xuất</SecondaryLink>}
        </article>;
      })}
    </div>}
  </section>;
}

export function CampaignFormPage() {
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [searching, setSearching] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [previous, setPrevious] = useState<PreviousRun[]>([]);
  const [excludePrevious, setExcludePrevious] = useState(false);
  const navigate = useNavigate();
  useEffect(() => {
    let active = true;
    setExcludePrevious(false);
    api.previousRuns(form.product_type).then((runs) => { if (active) setPrevious(runs); }).catch(() => { if (active) setPrevious([]); });
    return () => { active = false; };
  }, [form.product_type]);
  const setField = <K extends keyof CampaignInput>(key: K, value: CampaignInput[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: '' }));
  };
  const validate = () => {
    const next: Record<string, string> = {};
    if (!form.brand_name.trim()) next.brand_name = 'Nhập tên thương hiệu.';
    if (form.brand_name.length > 80) next.brand_name = 'Tên thương hiệu tối đa 80 ký tự.';
    if (!Number.isFinite(form.budget_vnd) || form.budget_vnd < 1_000_000 || form.budget_vnd > 10_000_000_000) next.budget_vnd = 'Ngân sách từ 1.000.000 đến 10.000.000.000 ₫.';
    if (form.count < 1 || form.count > 10) next.count = 'Chọn từ 1 đến 10 KOC.';
    if (form.product_specs.length > 1000) next.product_specs = 'Thông tin sản phẩm tối đa 1.000 ký tự.';
    if (form.followers_min < 0 || form.followers_max < 0 || form.followers_min > form.followers_max) next.followers_min = 'Khoảng người theo dõi chưa hợp lệ.';
    setErrors(next);
    return Object.keys(next).length === 0;
  };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!validate()) return;
    setSubmitError('');
    setSaving(true);
    try {
      const saved = await api.createCampaign({ ...form, brand_name: form.brand_name.trim(), ...(excludePrevious && previous.length ? { exclude_run_ids: previous.map((run) => run.run_id) } : {}) });
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (reducedMotion) {
        navigate(`/chien-dich/${saved.campaign_id}`);
        toast.success('Đã lưu chiến dịch.');
      }
      else {
        setSearching(true);
        window.setTimeout(() => {
          navigate(`/chien-dich/${saved.campaign_id}`);
          toast.success('Đã lưu chiến dịch.');
        }, 1200);
      }
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : 'Không thể lưu chiến dịch.');
    } finally { setSaving(false); }
  };

  if (searching) return <section className="searching-state" role="status" aria-live="polite">
    <img src={mascotUrl} alt="" width="240" height="240" />
    <div><p className="searching-line">Đang tìm KOC phù hợp…</p><div className="searching-strip"><span /></div></div>
  </section>;

  return <section className="page form-page">
    <div className="form-aside">
      <StepIndicator current={1} />
      <TitleBlock subtitle="Cho chúng tôi biết bạn đang tìm KOC như thế nào.">Kể về <em>sản phẩm</em> của bạn</TitleBlock>
      <img className="form-mascot" src={mascotUrl} alt="" width="320" height="320" />
    </div>
    <form className="campaign-form" noValidate onSubmit={submit}>
      {submitError && <p role="alert" className="notice warning">{submitError}</p>}
      <fieldset className="form-section"><legend>Sản phẩm</legend>
      <div className="field"><label htmlFor="brand">Tên thương hiệu</label><input id="brand" required autoComplete="organization" maxLength={80} value={form.brand_name} aria-invalid={Boolean(errors.brand_name)} aria-describedby={errors.brand_name ? 'brand-error' : undefined} onChange={(event) => setField('brand_name', event.target.value)} />{errors.brand_name && <small className="field-error" id="brand-error">{errors.brand_name}</small>}</div>
      <div className="field"><label id="product-label">Loại sản phẩm</label><Select.Root required value={form.product_type} onValueChange={(value) => { if (value) setField('product_type', value); }}>
        <Select.Trigger className="select-trigger" aria-labelledby="product-label"><Select.Value /><Select.Icon><ChevronDown size={16} aria-hidden="true" /></Select.Icon></Select.Trigger>
        <Select.Portal><Select.Positioner className="select-positioner"><Select.Popup className="select-popup"><Select.List>{productTypes.map((product) => <Select.Item className="select-item" value={product} key={product}><Select.ItemText>{product}</Select.ItemText><Select.ItemIndicator><Check size={14} aria-hidden="true" /></Select.ItemIndicator></Select.Item>)}</Select.List></Select.Popup></Select.Positioner></Select.Portal>
      </Select.Root></div>
      <div className="field"><label htmlFor="specs">Thông số sản phẩm <span className="optional">Không bắt buộc</span></label><textarea id="specs" rows={4} maxLength={1000} value={form.product_specs} aria-invalid={Boolean(errors.product_specs)} aria-describedby={errors.product_specs ? 'specs-error' : 'specs-hint'} onChange={(event) => setField('product_specs', event.target.value)} placeholder="Công dụng, thành phần, SPF, mức giá…" />{errors.product_specs ? <small className="field-error" id="specs-error">{errors.product_specs}</small> : <small className="field-hint" id="specs-hint">{form.product_specs.length}/1.000 ký tự</small>}</div>
      </fieldset>
      <fieldset className="form-section"><legend>Ngân sách</legend>
      <div className="field-grid">
        <div className="field"><label htmlFor="budget">Ngân sách chiến dịch (VND)</label><input id="budget" required type="text" inputMode="numeric" value={formatInputNumber(form.budget_vnd)} aria-invalid={Boolean(errors.budget_vnd)} aria-describedby={errors.budget_vnd ? 'budget-error' : undefined} onChange={(event) => setField('budget_vnd', parseInputNumber(event.target.value))} />{errors.budget_vnd && <small className="field-error" id="budget-error">{errors.budget_vnd}</small>}</div>
        <div className="field"><label htmlFor="count">Số KOC cần</label><input id="count" required type="number" min={1} max={10} value={form.count} aria-invalid={Boolean(errors.count)} aria-describedby={errors.count ? 'count-error' : undefined} onChange={(event) => setField('count', Number(event.target.value))} />{errors.count && <small className="field-error" id="count-error">{errors.count}</small>}</div>
      </div>
      </fieldset>
      <fieldset className="form-section"><legend>KOC bạn cần</legend>
      <fieldset className="field-group"><legend>Người theo dõi</legend><div className="field-grid">
        <div className="field"><label htmlFor="followers-min">Từ</label><input id="followers-min" type="text" inputMode="numeric" value={formatInputNumber(form.followers_min)} aria-invalid={Boolean(errors.followers_min)} onChange={(event) => setField('followers_min', parseInputNumber(event.target.value))} /></div>
        <div className="field"><label htmlFor="followers-max">Đến</label><input id="followers-max" type="text" inputMode="numeric" value={formatInputNumber(form.followers_max)} aria-invalid={Boolean(errors.followers_min)} onChange={(event) => setField('followers_max', parseInputNumber(event.target.value))} /></div>
      </div>{errors.followers_min && <small className="field-error">{errors.followers_min}</small>}</fieldset>
      <fieldset className="field-group"><legend>Khán giả mục tiêu</legend><div className="field"><label id="gender-label">Giới tính</label><Select.Root required value={form.target.gender} onValueChange={(value) => { if (value === 'Nữ' || value === 'Nam' || value === 'Tất cả') setForm((current) => ({ ...current, target: { ...current.target, gender: value } })); }}>
        <Select.Trigger className="select-trigger" aria-labelledby="gender-label"><Select.Value /><Select.Icon><ChevronDown size={16} aria-hidden="true" /></Select.Icon></Select.Trigger>
        <Select.Portal><Select.Positioner className="select-positioner"><Select.Popup className="select-popup"><Select.List>{['Nữ', 'Nam', 'Tất cả'].map((gender) => <Select.Item className="select-item" value={gender} key={gender}><Select.ItemText>{gender}</Select.ItemText><Select.ItemIndicator><Check size={14} aria-hidden="true" /></Select.ItemIndicator></Select.Item>)}</Select.List></Select.Popup></Select.Positioner></Select.Portal>
      </Select.Root></div>
        <div className="age-picker">
          <div className="age-picks" aria-label="Chọn nhanh nhóm tuổi">{agePicks.map((pick) => {
            const active = JSON.stringify(targetAgeRange(form.target.age_groups)) === JSON.stringify(targetAgeRange([...pick.range]));
            return <button className="age-chip" type="button" key={pick.label} aria-pressed={active} onClick={() => setForm((current) => ({ ...current, target: { ...current.target, age_groups: selectedAgeGroups(targetAgeRange([...pick.range])) } }))}>{pick.label}</button>;
          })}</div>
          <div className="age-slider">
            <Slider.Root value={targetAgeRange(form.target.age_groups)} min={0} max={ageBuckets.length - 1} step={1} minStepsBetweenValues={0} onValueChange={(values) => setForm((current) => ({ ...current, target: { ...current.target, age_groups: selectedAgeGroups(values) } }))}>
              <Slider.Control className="age-slider-control">
                <Slider.Track className="age-slider-track"><Slider.Indicator className="age-slider-indicator" /></Slider.Track>
                {[0, 1].map((index) => <Slider.Thumb key={index} index={index} className="age-slider-thumb" getAriaLabel={() => index === 0 ? 'Tuổi nhỏ nhất' : 'Tuổi lớn nhất'} getAriaValueText={() => ageRangeLabel([form.target.age_groups[0], form.target.age_groups.at(-1)!])} />)}
              </Slider.Control>
            </Slider.Root>
            <div className="age-ticks" aria-hidden="true">{ageBuckets.map((age) => <span key={age}>{age.replace('-', '–')}</span>)}</div>
          </div>
          <p className="age-summary" aria-live="polite">Đang chọn: {ageRangeLabel([form.target.age_groups[0], form.target.age_groups.at(-1)!])}</p>
        </div>
      </fieldset>
      <label className="switch-row"><input id="avoid-same-mcn" type="checkbox" checked={form.avoid_same_mcn} onChange={(event) => setField('avoid_same_mcn', event.target.checked)} /><span><strong>Không chọn hai KOC cùng MCN</strong><small>Giúp chiến dịch tiếp cận nhiều nhóm sáng tạo hơn.</small></span></label>
      {previous.length > 0 && <label className="switch-row exclude-run"><input id="exclude-previous" type="checkbox" checked={excludePrevious} onChange={(event) => setExcludePrevious(event.target.checked)} /><span><strong>Loại KOC đã đề xuất ở lần trước</strong><small className="exclude-run-note">{excludedSummary(previous)}</small></span></label>}
      </fieldset>
      <div className="form-actions"><SecondaryLink to="/chien-dich">Hủy</SecondaryLink><PrimaryButton type="submit" disabled={saving}>{saving ? 'Đang lưu…' : 'Tìm KOC phù hợp'}</PrimaryButton></div>
    </form>
  </section>;
}

const runDate = (value: string) => { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('vi-VN'); };
const excludedSummary = (runs: PreviousRun[]) => {
  const total = new Set(runs.flatMap((run) => run.creator_ids)).size;
  return `${runs.length === 1 ? `Lần chạy ngày ${runDate(runs[0].started_at)}` : `${runs.length} lần chạy trước (${runs.map((run) => runDate(run.started_at)).join(', ')})`}: loại ${total} KOC đã được đề xuất khỏi kết quả.`;
};

function CreatorRow({ creator, index, numbers, showAll = false, budgetHighlighted = false, picked = false }: { creator: Creator; index: number; numbers: Map<string, number>; showAll?: boolean; budgetHighlighted?: boolean; picked?: boolean }) {
  const location = useLocation();
  const strengths = creator.reasons?.length ? creator.reasons : [{ text: creator.reason, evidence_ids: creator.evidence_ids }];
  const review = [...strengths, ...(creator.caveats ?? [])];
  const visibleStrengths = review.slice(0, Math.min(showAll ? strengths.length : 2, review.length));
  const visibleCaveats = review.slice(strengths.length, strengths.length + (showAll ? 100 : 2));
  return <article className="creator-row" data-creator-id={creator.creator_id} data-budget-highlight={budgetHighlighted}>
    <span className="rank">{index + 1}</span>
    <div className="creator-summary"><Link className="creator-name" to={`/koc/${creator.creator_id}`} state={{ backgroundLocation: location }}>{creator.nickname}</Link>{picked && <span className="pick-badge">Được chọn</span>}<small><TikTokLink handle={creator.handle} name={creator.nickname} creatorId={creator.creator_id} /> · {formatFollowers(creator.followers)}</small><PrintProfileUrl handle={creator.handle} creatorId={creator.creator_id} />
      <p className="creator-summary-line">{summaryText(creator)}</p>
      {!showAll && (strengths.length > 2 || (creator.caveats?.length ?? 0) > 2) && <Link className="detail-link" to={`/koc/${creator.creator_id}`} state={{ backgroundLocation: location }}>Xem chi tiết</Link>}
    </div>
    <ReviewColumns strengths={visibleStrengths} weaknesses={visibleCaveats} numbers={numbers} creatorId={creator.creator_id} videoEvidenceIds={creator.video_evidence_ids} />
    <div className="row-breakdown"><CreatorBreakdown input={{ creatorId: creator.creator_id, fit: creator.fit, parts: creator.components, evidenceIds: [...creator.evidence_ids, ...(creator.reasons ?? []).flatMap((item) => item.evidence_ids)], videoIds: creator.video_evidence_ids ?? [], analysedVideoIds: creator.analysed_video_ids, audienceMissing: Boolean(creator.audience_note), ageMissing: creator.audience_age_missing }} /></div>
    <div className="fit-cell"><strong><NumberFlow value={creator.fit} format={{ maximumFractionDigits: 0 }} /></strong><small>Phù hợp</small><span className={`confidence confidence-${creator.confidence_count}`}>{creator.confidence}</span></div>
    <div className="cost-cell"><strong>{formatVnd(creator.cost_vnd)}</strong><small>ước tính / video</small></div>
  </article>;
}

export function CampaignResultsPage() {
  const { id } = useParams();
  const { campaign, error } = useCampaign(id);
  const [budgetHighlight, setBudgetHighlight] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();
  const filter = useMemo(() => readFilter(params), [params]);
  const setFilter = (next: CreatorFilter) => setParams(writeFilter(next), { replace: true });
  if (!campaign) return <Loading error={error} />;
  const { result, input } = campaign;
  if (result.status === 'refused') return <RefusedCampaign campaign={campaign} />;
  if (result.status === 'needs_run') return <NeedsRunCampaign campaign={campaign} />;
  const picked = campaignPicks(campaign);
  const alternates = result.alternates ?? [];
  const hasPicks = picked.length > 0;
  const chosen = [...picked, ...alternates];
  const chosenById = new Map(chosen.map((creator) => [creator.creator_id, creator]));
  const pool = (result.ranked_pool ?? chosen).map((creator) => chosenById.get(creator.creator_id) ?? creator);
  const allCreators = [...chosen, ...pool.filter((creator) => !chosenById.has(creator.creator_id))];
  const pickedIds = new Set(picked.map((creator) => creator.creator_id));
  const { shared, visible } = sharedCaveats(chosen);
  const visibleById = new Map(visible.map((creator) => [creator.creator_id, creator]));
  const numbers = evidenceNumbers(allCreators);
  const filtering = filterActive(filter);
  const filtered = filtering ? applyFilter(pool, filter) : [];
  return <section className="page results-page">
    <StepIndicator current={2} />
    <div className="results-intro"><TitleBlock subtitle={`${targetAudienceLabel(input.target)}. ${input.product_type}${input.product_specs ? `, ${input.product_specs}` : ''}. Ngân sách ${formatVnd(input.budget_vnd)} cho ${input.count} KOC, từ ${formatFollowers(input.followers_min)} đến ${formatFollowers(input.followers_max)}.`}>{input.brand_name}{input.product_specs ? ` · ${input.product_type}` : ''}</TitleBlock><div className="button-row">{hasPicks && <PrimaryLink to={`/chien-dich/${campaign.campaign_id}/de-xuat`}>Xem bản đề xuất</PrimaryLink>}<SecondaryLink to="/chien-dich/moi">Tạo chiến dịch khác</SecondaryLink></div></div>
    <BudgetStrip budgetVnd={input.budget_vnd} caption="Ngân sách dự kiến" onActiveChange={setBudgetHighlight}
      creators={picked.map((creator) => ({ id: creator.creator_id, name: creator.nickname, costVnd: creator.cost_vnd, href: `/koc/${creator.creator_id}` }))}
      note="Chi phí là ước tính theo mức booking phổ biến. Cần xác nhận với KOC hoặc MCN trước khi chốt." />
    {result.low_confidence_pool && <p className="notice warning">Nhóm dữ liệu hiện có tập trung vào chăm sóc da. Kết quả này có độ tin cậy thấp hơn.</p>}
    {result.warnings?.map((warning, index) => <p className="notice warning" role="status" key={`${index}-${warning}`}>{warning}</p>)}
    {hasPicks && <FilterBar filter={filter} onChange={setFilter} shown={filtering ? filtered.length : pool.length} total={pool.length} />}
    <h2>{filtering ? `${filtered.length} KOC khớp bộ lọc` : `${picked.length} KOC phù hợp nhất`}</h2>
    {shared.map((item, index) => <p className="notice shared-caveat" key={index}>{formatReasonNumbers(item.text)} <EvidenceMarkers ids={item.evidence_ids} numbers={numbers} creatorId={allCreators[0]?.creator_id ?? ''} /></p>)}
    {filtering ? (filtered.length > 0
      ? <div className="ranked-list">{filtered.map((creator, index) => <CreatorRow key={creator.creator_id} creator={visibleById.get(creator.creator_id) ?? creator} index={index} numbers={numbers} picked={pickedIds.has(creator.creator_id)} budgetHighlighted={budgetHighlight === creator.creator_id} />)}</div>
      : <FilterEmpty onClear={() => setFilter({ q: '', tier: '', price: '', sort: '' })} />)
    : hasPicks ? <div className="ranked-list">{picked.map((creator, index) => <CreatorRow key={creator.creator_id} creator={visibleById.get(creator.creator_id) ?? creator} index={index} numbers={numbers} budgetHighlighted={budgetHighlight === creator.creator_id} />)}</div> : <div className="empty-state"><p>{result.run_id === null ? 'Chưa có dữ liệu KOC' : result.ranked_count === 0 ? 'Không có KOC trong khoảng người theo dõi đã chọn.' : 'Chưa tìm thấy KOC phù hợp với yêu cầu.'}</p><SecondaryLink to="/chien-dich/moi">Sửa yêu cầu</SecondaryLink></div>}
    <ExcludedBox items={result.brand_fit_excluded} />
    {!filtering && alternates.length > 0 && <section className="alternates"><h2>{alternates.length} KOC thay thế</h2>{alternates.map((creator, index) => <CreatorRow key={creator.creator_id} creator={visibleById.get(creator.creator_id) ?? creator} index={index + picked.length} numbers={numbers} />)}</section>}
    <ScoringMethod />
  </section>;
}

function NeedsRunCommand({ command, productType }: { command: string; productType: string }) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command);
      toast.success('Đã sao chép');
    } catch {
      toast.error('Không thể sao chép lệnh. Hãy chọn và sao chép thủ công.');
    }
  };
  const parts = productType === 'Khác' ? command.split(/(<id>)/g) : [command];
  return <div className="needs-run-command">
    <pre><code>{parts.map((part, index) => part === '<id>' ? <mark key={index}>{part}</mark> : part)}</code></pre>
    <button type="button" className="needs-run-copy" onClick={copy}>Sao chép</button>
  </div>;
}

const nf = (value: number, digits = 0) => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: digits }).format(value);
const range = (r: { low: number; high: number }, digits = 0) => r.low === r.high ? nf(r.low, digits) : `${nf(r.low, digits)}–${nf(r.high, digits)}`;

function RunEstimateBox({ estimate }: { estimate: RunEstimate }) {
  return <section className="run-estimate" aria-labelledby="run-estimate-title">
    <div className="run-estimate-head"><strong id="run-estimate-title">Ước tính cho lượt chạy này</strong><span>{estimate.label}, quét tối đa {nf(estimate.limit)} KOC. Số thật có thể lệch.</span></div>
    <dl>
      <div><dt>Tín dụng Kalodata</dt><dd>{range(estimate.credits, 1)} tín dụng</dd></div>
      <div><dt>Chi phí LLM</dt><dd>{range(estimate.usd, 2)} USD</dd></div>
      <div><dt>Token LLM</dt><dd>{range(estimate.tokens)} token</dd></div>
      <div><dt>Thời gian</dt><dd>{range(estimate.minutes)} phút</dd></div>
    </dl>
  </section>;
}

function ExcludedRunsNote({ productType, runIds }: { productType: string; runIds: string[] }) {
  const [runs, setRuns] = useState<PreviousRun[]>([]);
  useEffect(() => { api.previousRuns(productType).then((all) => setRuns(all.filter((run) => runIds.includes(run.run_id)))).catch(() => setRuns([])); }, [productType, runIds]);
  return <p className="needs-run-excluded">{runs.length > 0 ? `Lệnh có --exclude-run. ${excludedSummary(runs)}` : `Lệnh có --exclude-run cho ${runIds.length} lần chạy trước.`}</p>;
}

function NeedsRunCampaign({ campaign }: { campaign: Campaign }) {
  const { input, result } = campaign;
  const command = result.run_command ?? '';
  const realCommand = command.replace(' --dry-run', '');
  const notes = result.run_command_notes ?? [];
  const refusal = notes[0];
  const remainingNotes = refusal ? notes.slice(1) : notes;
  return <section className="page results-page needs-run-page">
    <StepIndicator current={2} />
    <div className="needs-run-panel">
      <TitleBlock>Chưa có dữ liệu KOC cho {input.product_type}</TitleBlock>
      <p className="needs-run-intro">Trang web không chạy lượt có phí. Nhân viên vận hành chạy lệnh bên dưới.</p>
      {refusal && <p className="notice warning needs-run-refusal" role="alert">{refusal}</p>}
      {result.run_estimate && <RunEstimateBox estimate={result.run_estimate} />}
      {(input.exclude_run_ids?.length ?? 0) > 0 && <ExcludedRunsNote productType={input.product_type} runIds={input.exclude_run_ids!} />}
      <section className="needs-run-step" aria-labelledby="needs-run-estimate">
        <h2 id="needs-run-estimate">1. Ước tính chi phí</h2>
        <NeedsRunCommand command={command} productType={input.product_type} />
      </section>
      <section className="needs-run-step" aria-labelledby="needs-run-execute">
        <h2 id="needs-run-execute">2. Chạy thật</h2>
        <NeedsRunCommand command={realCommand} productType={input.product_type} />
      </section>
      {remainingNotes.length > 0 && <ul className="needs-run-notes">{remainingNotes.map((note, index) => <li key={`${index}-${note}`}>{note}</li>)}</ul>}
    </div>
  </section>;
}

function RefusedCampaign({ campaign }: { campaign: Campaign }) {
  const { input, result } = campaign;
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState('');
  const [error, setError] = useState('');
  const options = result.options;
  const warnings = result.warnings ?? [];
  const retry = async (key: string, changes: Partial<CampaignInput>) => {
    setSubmitting(key);
    setError('');
    try {
      const next = await api.createCampaign({ ...input, ...changes });
      navigate(`/chien-dich/${next.campaign_id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không thể tạo chiến dịch.');
      setSubmitting('');
    }
  };
  return <section className="page results-page">
    <StepIndicator current={2} />
    <div className="refusal-panel" role="status">
      <TitleBlock subtitle={`${input.brand_name} · Ngân sách ${formatVnd(input.budget_vnd)}`}>Ngân sách chưa đủ cho {input.count} KOC</TitleBlock>
      {warnings.length > 0 && <ul className="refusal-warnings">{warnings.map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}</ul>}
      {error && <p className="notice warning" role="alert">{error}</p>}
      <div className="refusal-options">
        {options?.max_count_within_budget && <button className="refusal-option" type="button" disabled={Boolean(submitting)} onClick={() => retry('count', { count: options.max_count_within_budget!.count })}>
          {submitting === 'count' ? 'Đang tạo chiến dịch…' : `Chọn ${options.max_count_within_budget.count} KOC (${formatVnd(options.max_count_within_budget.cost_vnd)})`}
        </button>}
        {options?.min_budget_for_count && <button className="refusal-option" type="button" disabled={Boolean(submitting)} onClick={() => retry('budget', { budget_vnd: options.min_budget_for_count!.budget_vnd })}>
          {submitting === 'budget' ? 'Đang tạo chiến dịch…' : `Tăng ngân sách lên ${formatVnd(options.min_budget_for_count.budget_vnd)}`}
        </button>}
        {options?.cheaper_follower_band && <button className="refusal-option" type="button" disabled={Boolean(submitting)} onClick={() => retry('followers', { followers_min: options.cheaper_follower_band!.follower_min, followers_max: options.cheaper_follower_band!.follower_max })}>
          {submitting === 'followers' ? 'Đang tạo chiến dịch…' : `Đổi sang người theo dõi ${formatInputNumber(options.cheaper_follower_band.follower_min)}–${formatInputNumber(options.cheaper_follower_band.follower_max)} (${formatVnd(options.cheaper_follower_band.cost_vnd)})`}
        </button>}
      </div>
      <SecondaryLink to="/chien-dich/moi">Sửa yêu cầu</SecondaryLink>
    </div>
  </section>;
}

export function ProposalPage() {
  const { id } = useParams();
  const { campaign, error } = useCampaign(id);
  const [budgetHighlight, setBudgetHighlight] = useState<string | null>(null);
  if (!campaign) return <Loading error={error} />;
  const { input, result } = campaign;
  const picked = campaignPicks(campaign);
  const { shared, visible } = sharedCaveats(picked);
  const visibleById = new Map(visible.map((creator) => [creator.creator_id, creator]));
  const numbers = evidenceNumbers(picked);
  const totalCost = result.total_cost_vnd ?? picked.reduce((sum, creator) => sum + creator.cost_vnd, 0);
  return <article className="page proposal">
    <StepIndicator current={3} />
    <header className="proposal-brand"><BrandLogo variant="stack" /></header>
    <div className="proposal-actions"><SecondaryLink to={`/chien-dich/${campaign.campaign_id}`}>Quay lại kết quả</SecondaryLink><PrimaryButton onClick={() => window.print()}>In / Lưu PDF</PrimaryButton></div>
    <TitleBlock>Đề xuất KOC cho <em>{input.brand_name}</em></TitleBlock>
    <p className="proposal-lede">{targetAudienceLabel(input.target)}. {input.product_type}{input.product_specs ? ` · ${input.product_specs}` : ''}</p>
    <BudgetStrip budgetVnd={input.budget_vnd} caption="Ngân sách dự kiến" onActiveChange={setBudgetHighlight}
      creators={picked.map((creator) => ({ id: creator.creator_id, name: creator.nickname, costVnd: creator.cost_vnd, href: `/koc/${creator.creator_id}` }))} />
    {shared.map((item, index) => <p className="notice shared-caveat" key={index}>{formatReasonNumbers(item.text)} <EvidenceMarkers ids={item.evidence_ids} numbers={numbers} creatorId={picked[0]?.creator_id ?? ''} /></p>)}
    <h2>Danh sách đề xuất</h2>
    <ol className="proposal-list">{picked.map((creator) => {
      const item = visibleById.get(creator.creator_id) ?? creator;
      return <li key={creator.creator_id} data-creator-id={creator.creator_id} data-budget-highlight={budgetHighlight === creator.creator_id}>
      <div className="proposal-item-head"><div><h3>{creator.nickname}</h3><p><TikTokLink handle={creator.handle} name={creator.nickname} creatorId={creator.creator_id} /> · {formatFollowers(creator.followers)} · Phù hợp {Math.round(creator.fit)}/100 · {creator.confidence}</p><PrintProfileUrl handle={creator.handle} creatorId={creator.creator_id} /></div><strong>{formatVnd(creator.cost_vnd)} <small>ước tính</small></strong></div><div className="proposal-item-body"><p className="creator-summary-line">{summaryText(creator)}</p><ReviewColumns strengths={(item.reasons?.length ? item.reasons : [{ text: item.reason, evidence_ids: item.evidence_ids }]).slice(0, 2)} weaknesses={(item.caveats ?? []).slice(0, 2)} numbers={numbers} creatorId={item.creator_id} videoEvidenceIds={item.video_evidence_ids} />{((item.reasons?.length ?? 1) > 2 || (item.caveats?.length ?? 0) > 2) && <Link className="detail-link" to={`/koc/${creator.creator_id}#evidence`}>Xem chi tiết</Link>}<CreatorBreakdown input={{ creatorId: creator.creator_id, fit: creator.fit, parts: creator.components, evidenceIds: [...creator.evidence_ids, ...(creator.reasons ?? []).flatMap((reason) => reason.evidence_ids)], videoIds: creator.video_evidence_ids ?? [], analysedVideoIds: creator.analysed_video_ids, audienceMissing: Boolean(creator.audience_note), ageMissing: creator.audience_age_missing }} /></div>
    </li>})}</ol>
    <ExcludedBox items={result.brand_fit_excluded} />
    <p className="proposal-total">Tổng chi phí dự kiến <strong>{formatVnd(totalCost)}</strong></p>
    <aside className="proposal-assumptions"><h2>Điều cần xác nhận</h2><p>Mức phí dựa trên bảng ước tính theo lượng người theo dõi. Cần xác nhận giá, nội dung và lịch đăng trực tiếp với KOC hoặc MCN trước khi ký.</p><p className="proposal-date">Ngày tạo: {new Date(campaign.created_at).toLocaleDateString('vi-VN')}</p></aside>
    <ScoringMethod />
  </article>;
}

export function RunProposalPage() {
  const { runId } = useParams();
  const location = useLocation();
  const [proposal, setProposal] = useState<RunProposal | null>(null);
  const [error, setError] = useState('');
  const [budgetHighlight, setBudgetHighlight] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    const load = runId ? Promise.resolve({ run_id: runId }) : api.latestRun();
    load.then(({ run_id }) => api.runProposal(run_id)).then((value) => { if (active) setProposal(value); }).catch((reason: Error) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [runId]);
  if (!proposal) return <Loading error={error} />;
  const common = proposal.picks.length ? proposal.picks[0].caveats.filter((text) => !isAudienceCaveat(text) && proposal.picks.every((pick) => pick.caveats.some((value) => value.normalize('NFKC').replace(/\s+/g, ' ').trim().toLocaleLowerCase('vi') === text.normalize('NFKC').replace(/\s+/g, ' ').trim().toLocaleLowerCase('vi')))) : [];
  const commonDetails = proposal.picks[0]?.caveat_evidence.filter((item) => common.some((text) => text.normalize('NFKC').trim().toLocaleLowerCase('vi') === item.text.normalize('NFKC').trim().toLocaleLowerCase('vi'))) ?? [];
  const commonAudience = proposal.picks.map((pick) => pick.audience_note || pick.caveats.find(isAudienceCaveat) || pick.audience_text).find((value) => typeof value === 'string' && value.length) ?? null;
  const evidenceMap = new Map<string, number>();
  proposal.picks.flatMap((pick) => [...pick.reasons.flatMap((item) => item.evidence_ids), ...pick.caveat_evidence.flatMap((item) => item.evidence_ids), ...pick.video_evidence_ids]).forEach((id) => { if (!evidenceMap.has(id)) evidenceMap.set(id, evidenceMap.size + 1); });
  return <article className="page proposal run-proposal">
    <StepIndicator current={3} />
    <header className="proposal-brand"><BrandLogo variant="stack" /></header>
    <div className="proposal-actions"><SecondaryLink to="/">Về trang chủ</SecondaryLink><PrimaryButton onClick={() => window.print()}>In / Lưu PDF</PrimaryButton></div>
    <TitleBlock>Đề xuất KOC cho <em>{proposal.product}</em></TitleBlock>
    <p className="proposal-lede">{proposal.target}. Chi phí từng KOC là ước tính, cần xác nhận trước khi hợp tác.</p>
    <BudgetStrip budgetVnd={proposal.budget_vnd} caption="Ngân sách dự kiến" onActiveChange={setBudgetHighlight}
      creators={proposal.picks.map((creator) => ({ id: creator.creator_id, name: creator.nickname, costVnd: creator.cost_vnd, href: `/de-xuat/${proposal.run_id}/koc/${creator.creator_id}` }))} />
    {common.map((text, index) => <p className="notice shared-caveat" key={index}>{formatReasonNumbers(text)} <EvidenceMarkers ids={commonDetails[index]?.evidence_ids ?? []} numbers={evidenceMap} creatorId={proposal.picks[0]?.creator_id ?? ''} runId={proposal.run_id} /></p>)}
    {commonAudience && <p className="notice shared-caveat">{formatReasonNumbers(commonAudience)}</p>}
    <h2>Danh sách đề xuất</h2>
    <ol className="proposal-list run-proposal-list">{proposal.picks.map((creator) => {
      const strengths = creator.reasons.length ? creator.reasons : [{ text: creator.reason, evidence_ids: creator.evidence_ids }];
      const weaknesses = creator.caveat_evidence.filter((item) => !isAudienceCaveat(item.text) && !common.some((text) => text.normalize('NFKC').trim().toLocaleLowerCase('vi') === item.text.normalize('NFKC').trim().toLocaleLowerCase('vi')));
      return <li key={creator.creator_id} data-creator-id={creator.creator_id} data-budget-highlight={budgetHighlight === creator.creator_id}>
      <div className="run-pick-main"><div className="proposal-item-head"><div className="run-pick-title"><span className="rank">{creator.rank}</span><div><h3>{creator.nickname}</h3><p><TikTokLink handle={creator.handle} name={creator.nickname} creatorId={creator.creator_id} /> · {formatFollowers(creator.followers)} · Phù hợp {Math.round(creator.score)}/100</p><PrintProfileUrl handle={creator.handle} creatorId={creator.creator_id} /></div></div><strong>{formatVnd(creator.cost_vnd)} <small>ước tính</small></strong></div>
        <div className="proposal-item-body">
        <p className="creator-summary-line">{summaryText({ fit: creator.score, components: creator.score_parts, audience_age_missing: false })}</p>
        <ReviewColumns strengths={strengths.slice(0, 2)} weaknesses={weaknesses.slice(0, 2)} numbers={evidenceMap} creatorId={creator.creator_id} runId={proposal.run_id} videoEvidenceIds={creator.video_evidence_ids} />
        {creator.evidence_count > 0 && <Link className="detail-link" to={`/de-xuat/${proposal.run_id}/koc/${creator.creator_id}#evidence`} state={{ backgroundLocation: location }}>Xem chi tiết · {creator.evidence_count} bằng chứng</Link>}
        <CreatorBreakdown input={{ creatorId: creator.creator_id, runId: proposal.run_id, fit: creator.score, parts: creator.score_parts, evidenceIds: [...creator.evidence_ids, ...creator.reasons.flatMap((item) => item.evidence_ids), ...creator.caveat_evidence.flatMap((item) => item.evidence_ids)], videoIds: creator.video_evidence_ids, analysedVideoIds: creator.analysed_video_ids, audienceMissing: creator.audience_text !== null || Boolean(creator.audience_note) }} />
        </div>
      </div>
    </li>})}</ol>
    <ExcludedBox items={proposal.brand_fit_excluded} />
    <p className="proposal-total">Tổng chi phí dự kiến <strong>{formatVnd(proposal.total_cost_vnd)}</strong></p>
    <aside className="proposal-assumptions"><h2>Điều cần xác nhận</h2><p>Mức phí là ước tính. Xác nhận giá, nội dung và lịch đăng trực tiếp với KOC hoặc MCN trước khi ký.</p></aside>
    <ScoringMethod />
  </article>;
}

const metricLabels: Record<string, string> = {
  video_gpm: 'GPM video (doanh thu trên 1.000 lượt xem)', skincare_revenue_share: 'Tỷ trọng doanh thu ngành chăm sóc da',
  engagement_per_view: 'Tỷ lệ tương tác trên lượt xem', revenue_trend_slope: 'Xu hướng doanh thu',
  female_ratio: 'Tỷ lệ khán giả nữ', female_pct: 'Tỷ lệ khán giả nữ', age_18_24_share: 'Tỷ lệ khán giả 18–24 tuổi',
  age_25_34_share: 'Tỷ lệ khán giả 25–34 tuổi', follower_band_fit: 'Độ phù hợp với khoảng người theo dõi',
  age_18_24_pct: 'Khán giả 18–24 tuổi', age_25_34_pct: 'Khán giả 25–34 tuổi',
  age_35_44_pct: 'Khán giả 35–44 tuổi', age_35_44_share: 'Tỷ lệ khán giả 35–44 tuổi',
  age_45_54_pct: 'Khán giả 45–54 tuổi', age_45_54_share: 'Tỷ lệ khán giả 45–54 tuổi',
  age_55_plus_pct: 'Khán giả từ 55 tuổi', age_55_plus_share: 'Tỷ lệ khán giả từ 55 tuổi',
  video_vs_live_share: 'Tỷ trọng video so với phát trực tiếp',
};
const rubricLabels: Record<string, string> = {
  brand_fit: 'Mức phù hợp với thương hiệu', claim_quality: 'Độ tin cậy của tuyên bố',
  hook: 'Sức hút mở đầu', cta: 'Lời kêu gọi hành động', demonstration: 'Cách trình bày sản phẩm',
  product_clarity: 'Độ rõ của thông tin sản phẩm', production_quality: 'Chất lượng sản xuất',
};

function evidenceLinkName(evidenceId: string) {
  if (evidenceId.startsWith('metric:')) {
    const name = evidenceId.split(':').at(-1) || '';
    return `Số liệu ${metricLabels[name] || 'khác'}`;
  }
  const timestamp = evidenceId.match(/@(\d+(?:\.\d+)?)s?$/)?.[1];
  if (timestamp) {
    const seconds = Math.floor(Number(timestamp));
    return `Khung hình video ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
  }
  const transcript = evidenceId.match(/:transcript:(\d+)$/)?.[1];
  return transcript ? `Lời thoại đoạn ${transcript}` : 'Khung hình video';
}

function formatVideoTime(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
}

function CreatorDetailContent({ creator, runId }: { creator: CreatorDetail; runId?: string }) {
  const cited = [...creator.reasons, ...creator.caveats].flatMap((item) => item.evidence_ids).concat(creator.video_evidence_ids);
  const strengths = creator.reasons;
  const weaknesses = creator.caveats;
  const numbers = new Map<string, number>();
  cited.forEach((id) => { if (!numbers.has(id)) numbers.set(id, numbers.size + 1); });
  const metrics = Object.entries(creator.metrics).filter(([name]) => !creator.audience_text || !name.includes('age_') && !name.includes('female'));
  const citedMetrics = metrics.filter(([name]) => numbers.has(`metric:${creator.creator_id}:${name}`));
  const keyMetrics = [...citedMetrics, ...metrics.filter(([name]) => !citedMetrics.some(([used]) => used === name))].slice(0, 6);
  const videos = creator.videos.map((video) => ({ ...video, evidence: video.evidence.filter((item) => numbers.has(item.evidence_id)).sort((a, b) => a.start_s - b.start_s) }));
  const citedVideos = videos.filter((video) => video.evidence.length);
  const otherVideos = videos.filter((video) => !video.evidence.length);
  const components = { commercial: creator.scores.S1 ?? null, audience: creator.scores.S2 ?? null, content: creator.scores.S3 ?? null };
  const commercialNames: [string, string][] = [['video_gpm', 'GPM video'], ['skincare_revenue_share', 'doanh thu ngành chăm sóc da'], ['revenue_trend_slope', 'xu hướng doanh thu']];
  const commercialBits = commercialNames.filter(([name]) => typeof creator.metrics[name]?.value === 'number').map(([name, label]) => `${label} ${formatMetric(name, creator.metrics[name].value as number)}`);
  const commercialWhy = commercialBits.length ? `Dựa trên ${commercialBits.join(', ')}.` : undefined;
  const rubricTotals = new Map<string, number[]>();
  videos.forEach((video) => video.rubric.forEach((item) => rubricTotals.set(item.criterion, [...(rubricTotals.get(item.criterion) ?? []), item.score])));
  const rubricAverages = [...rubricTotals].map(([criterion, scores]) => ({ label: rubricLabels[criterion] || 'Tiêu chí khác', value: scores.reduce((sum, value) => sum + value, 0) / scores.length })).sort((a, b) => b.value - a.value);
  const rubricVideos = videos.filter((video) => video.rubric.length).length;
  const fmtScore = (value: number) => value.toLocaleString('vi-VN', { maximumFractionDigits: 1 });
  const contentWhy = rubricAverages.length ? `${rubricVideos} video được chấm theo tiêu chí nội dung. Cao nhất: ${rubricAverages[0].label} ${fmtScore(rubricAverages[0].value)}/5. Thấp nhất: ${rubricAverages.at(-1)!.label} ${fmtScore(rubricAverages.at(-1)!.value)}/5.` : undefined;
  return <div className="creator-detail">
    <header className="detail-heading"><div className="avatar-initial" aria-hidden="true">{creator.nickname.slice(0, 1)}</div><div><TitleBlock>{creator.nickname}</TitleBlock><p><TikTokLink handle={creator.handle} name={creator.nickname} creatorId={creator.creator_id} /> · {formatFollowers(creator.followers)} · Phù hợp {Math.round(creator.scores.S4 ?? 0)}/100 · {formatVnd(creator.cost_vnd ?? 0)}{creator.mcn ? ` · ${creator.mcn}` : ''}</p><PrintProfileUrl handle={creator.handle} creatorId={creator.creator_id} /></div></header>
    <section className="detail-review"><h2>Tóm tắt</h2><p>{summaryText({ fit: creator.scores.S4 ?? 0, components, audience_age_missing: false })}</p>
      <ReviewColumns strengths={strengths} weaknesses={weaknesses} numbers={numbers} creatorId={creator.creator_id} runId={runId} detail videoEvidenceIds={creator.video_evidence_ids} />
      {(creator.audience_note || creator.audience_text) && <p className="notice">{creator.audience_note || creator.audience_text}</p>}
    </section>
    <CreatorBreakdown idSuffix="-koc" input={{ creatorId: creator.creator_id, runId, detail: true, fit: creator.scores.S4 ?? 0, parts: components, evidenceIds: [...numbers.keys()], videoIds: [], analysedVideoIds: videos.map((video) => video.video_id), audienceMissing: Boolean(creator.audience_text || creator.audience_note), commercialWhy, contentWhy }} />
    <section><h2>Số liệu chính</h2><dl className="metric-list">{keyMetrics.map(([name, metric]) => <MetricRow key={name} creator={creator} name={name} metric={metric} numbers={numbers} />)}</dl>
      {metrics.length > keyMetrics.length && <details><summary>Xem tất cả số liệu</summary><dl className="metric-list">{metrics.filter(([name]) => !keyMetrics.some(([key]) => key === name)).map(([name, metric]) => <MetricRow key={name} creator={creator} name={name} metric={metric} numbers={numbers} />)}</dl></details>}
    </section>
    <section id="evidence"><h2>Bằng chứng từ video</h2>{citedVideos.length ? citedVideos.map((video) => <article className="video-evidence" id={`video-${video.video_id}`} key={video.video_id}>
      <h3>{video.title}</h3><p><TikTokVideoLink handle={creator.handle} videoId={video.video_id} creatorId={creator.creator_id} /></p><p>{video.views ? `${new Intl.NumberFormat('vi-VN').format(video.views)} lượt xem` : 'Chưa có số lượt xem'} · {video.evidence.length} thời điểm được trích dẫn</p>
      <div className="evidence-table">{video.evidence.map((item) => <div className={`evidence-row${item.frame_url ? '' : ' no-frame'}`} id={item.evidence_id} key={item.evidence_id}>
        <time>{formatVideoTime(item.start_s)}</time>{item.frame_url && <Dialog.Root><Dialog.Trigger className="frame-trigger" aria-label={`Phóng to khung hình tại ${formatVideoTime(item.start_s)}`}><img src={item.frame_url} alt={`Khung hình tại ${formatVideoTime(item.start_s)}`} loading="lazy" decoding="async" width={120} height={68} /></Dialog.Trigger><Dialog.Portal><Dialog.Backdrop className="image-backdrop" /><Dialog.Popup className="image-dialog"><Dialog.Close className="image-close">Đóng</Dialog.Close><img src={item.frame_url} alt={`Khung hình tại ${formatVideoTime(item.start_s)}`} /></Dialog.Popup></Dialog.Portal></Dialog.Root>}
        <div><p className="evidence-quote">{item.quote_vi || 'Khung hình được dùng làm bằng chứng.'}</p>{item.quote_vi && item.quote_vi.length > 140 && <details><summary>Xem nội dung đầy đủ</summary><p>{item.quote_vi}</p></details>}</div><EvidenceNumbers ids={[item.evidence_id]} numbers={numbers} />
      </div>)}</div>
      <details className="transcript-disclosure"><summary>Xem toàn bộ lời thoại</summary><blockquote>{video.transcript_vi || 'Chưa có lời thoại.'}</blockquote>{video.rubric.map((item, index) => <p key={index}><strong>{rubricLabels[item.criterion] || 'Tiêu chí khác'}</strong> · {item.score}/5 {formatReasonNumbers(item.rationale_vi)}</p>)}{video.risks_vi.map((risk, index) => <p key={index}>{formatReasonNumbers(risk)}</p>)}</details>
    </article>) : <p>Chưa có thời điểm video được trích dẫn.</p>}
      {otherVideos.length > 0 && <details className="other-videos"><summary>Video khác ({otherVideos.length})</summary>{otherVideos.map((video) => <details key={video.video_id} id={`video-${video.video_id}`}><summary>{video.title}</summary><p><TikTokVideoLink handle={creator.handle} videoId={video.video_id} creatorId={creator.creator_id} /></p><p>{video.transcript_vi || 'Chưa có lời thoại.'}</p></details>)}</details>}
    </section>
    <ScoringMethod idSuffix="-koc" />
  </div>;
}

function MetricRow({ creator, name, metric, numbers }: { creator: CreatorDetail; name: string; metric: CreatorDetail['metrics'][string]; numbers: Map<string, number> }) {
  const value = metric.value;
  const missing = value === null || value === undefined || value === '';
  const shown = typeof value === 'number' ? formatMetric(name, value) : String(value ?? '');
  const evidenceId = `metric:${creator.creator_id}:${name}`;
  return <div id={evidenceId} key={name}><dt>{metricLabels[name] || 'Chỉ số khác'}</dt><dd>{missing ? 'Chưa phân tích' : shown} {numbers.has(evidenceId) && <EvidenceNumbers ids={[evidenceId]} numbers={numbers} />}</dd></div>;
}

function formatMetric(name: string, value: number) {
  if (name.includes('ratio') || name.includes('share') || name.endsWith('_pct') || name.includes('engagement')) return `${(value <= 1 ? value * 100 : value).toLocaleString('vi-VN', { maximumFractionDigits: 2 })}%`;
  if (name.includes('trend')) return `${value > 0 ? '+' : ''}${formatCompactVnd(value)} ₫/ngày`;
  if (name.includes('revenue') || name.includes('gpm')) return `${formatCompactVnd(value)} ₫`;
  return value.toLocaleString('vi-VN', { maximumFractionDigits: 2 });
}

function formatCompactVnd(value: number) {
  const absolute = Math.abs(value);
  const divisor = absolute >= 1_000_000 ? 1_000_000 : absolute >= 1_000 ? 1_000 : 1;
  const unit = divisor === 1_000_000 ? 'triệu' : divisor === 1_000 ? 'nghìn' : '';
  return `${(value / divisor).toLocaleString('vi-VN', { maximumFractionDigits: divisor === 1 ? 0 : 1 })}${unit ? ` ${unit}` : ''}`;
}

export function CreatorPage() {
  const { id, runId, creatorId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [creator, setCreator] = useState<CreatorDetail | null>(null);
  const [error, setError] = useState('');
  const mobile = useMemo(() => window.matchMedia('(max-width: 767px)').matches, []);
  const selectedCreatorId = creatorId ?? id;
  useEffect(() => {
    if (selectedCreatorId) (runId ? api.runCreator(runId, selectedCreatorId) : api.creator(selectedCreatorId)).then(setCreator).catch((reason: Error) => setError(reason.message));
  }, [runId, selectedCreatorId]);
  useEffect(() => { if (creator && location.hash) revealEvidence(decodeURIComponent(location.hash.slice(1))); }, [creator, location.hash]);
  if (!creator) return <Loading error={error} />;
  if (mobile) return <Drawer.Root open onOpenChange={(open) => { if (!open) navigate(-1); }} direction="bottom">
    <Drawer.Portal><Drawer.Overlay className="drawer-overlay" /><Drawer.Content className="drawer-content"><Drawer.Handle className="drawer-handle" /><Drawer.Title className="sr-only">Hồ sơ {creator.nickname}</Drawer.Title><div className="drawer-scroll" role="region" aria-label={`Thông tin ${creator.nickname}`} tabIndex={0}><CreatorDetailContent creator={creator} runId={runId} /></div></Drawer.Content></Drawer.Portal>
  </Drawer.Root>;
  return <section className="page detail-page"><button className="back-link text-button" onClick={() => navigate(-1)}><ChevronLeft size={16} aria-hidden="true" /> Quay lại</button><CreatorDetailContent creator={creator} runId={runId} /></section>;
}

