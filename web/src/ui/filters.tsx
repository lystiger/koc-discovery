import { useEffect, useState } from 'react';
import { Drawer } from 'vaul';
import { SlidersHorizontal, Search, X } from 'lucide-react';
import type { Creator } from '../types';

/** Lowercase, strip Vietnamese diacritics: "chong nang" matches "Chống nắng". */
export const fold = (value: string) => value.normalize('NFD').replace(/đ/gi, 'd').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

export const TIERS = [
  { id: 'lt50', label: 'Dưới 50 nghìn', test: (n: number) => n < 50_000 },
  { id: '50-100', label: '50–100 nghìn', test: (n: number) => n >= 50_000 && n < 100_000 },
  { id: 'gte100', label: 'Từ 100 nghìn', test: (n: number) => n >= 100_000 },
] as const;
export const PRICE_BANDS = [
  { id: 'lt2', label: 'Dưới 2 triệu', test: (n: number) => n < 2_000_000 },
  { id: '2-4', label: '2–4 triệu', test: (n: number) => n >= 2_000_000 && n < 4_000_000 },
  { id: 'gte4', label: 'Từ 4 triệu', test: (n: number) => n >= 4_000_000 },
] as const;
export const SORTS = [
  { id: 'score', label: 'Điểm cao nhất' },
  { id: 'price-asc', label: 'Giá thấp đến cao' },
  { id: 'price-desc', label: 'Giá cao đến thấp' },
] as const;

export type CreatorFilter = { q: string; tier: string; price: string; sort: string };
const EMPTY: CreatorFilter = { q: '', tier: '', price: '', sort: '' };
const oneOf = (value: string | null, options: readonly { id: string }[]) => options.some((option) => option.id === value) ? value! : '';

export function readFilter(params: URLSearchParams): CreatorFilter {
  return { q: params.get('q') ?? '', tier: oneOf(params.get('tier'), TIERS), price: oneOf(params.get('gia'), PRICE_BANDS), sort: oneOf(params.get('sx'), SORTS.slice(1)) };
}
export function writeFilter(filter: CreatorFilter): URLSearchParams {
  const params = new URLSearchParams();
  if (filter.q) params.set('q', filter.q);
  if (filter.tier) params.set('tier', filter.tier);
  if (filter.price) params.set('gia', filter.price);
  if (filter.sort) params.set('sx', filter.sort);
  return params;
}
export const filterActive = (filter: CreatorFilter) => Boolean(filter.q.trim() || filter.tier || filter.price || filter.sort);
const optionCount = (filter: CreatorFilter) => [filter.tier, filter.price, filter.sort].filter(Boolean).length;

/** Per-video price: the API sends it for the scored pool; older saved campaigns only have the 3-video total. */
export const pricePerVideo = (creator: Creator) => creator.price_per_video_vnd ?? Math.round(creator.cost_vnd / 3);
const byFit = (a: Creator, b: Creator) => b.fit - a.fit || a.creator_id.localeCompare(b.creator_id);

/** Creators that pass the filter. Default order: fit descending, creator id as the stable tie-breaker. */
export function applyFilter(creators: Creator[], filter: CreatorFilter): Creator[] {
  const needle = fold(filter.q).replace(/^@/, '');
  const tier = TIERS.find((item) => item.id === filter.tier);
  const price = PRICE_BANDS.find((item) => item.id === filter.price);
  const rows = creators.filter((creator) =>
    (!needle || fold(`${creator.nickname} ${creator.handle}`).includes(needle))
    && (!tier || tier.test(creator.followers)) && (!price || price.test(pricePerVideo(creator))));
  if (filter.sort === 'price-asc') return rows.sort((a, b) => pricePerVideo(a) - pricePerVideo(b) || byFit(a, b));
  if (filter.sort === 'price-desc') return rows.sort((a, b) => pricePerVideo(b) - pricePerVideo(a) || byFit(a, b));
  return rows.sort(byFit);
}

function Chips({ label, options, value, onChange, allLabel }: { label: string; options: readonly { id: string; label: string }[]; value: string; onChange: (value: string) => void; allLabel: string }) {
  return <fieldset className="filter-group"><legend>{label}</legend><div className="age-picks">
    <button type="button" className="age-chip" aria-pressed={value === ''} onClick={() => onChange('')}>{allLabel}</button>
    {options.map((option) => <button type="button" className="age-chip" key={option.id} aria-pressed={value === option.id} onClick={() => onChange(value === option.id ? '' : option.id)}>{option.label}</button>)}
  </div></fieldset>;
}

function useMobile() {
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 767px)').matches);
  useEffect(() => {
    const query = window.matchMedia('(max-width: 767px)');
    const update = () => setMobile(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  return mobile;
}

export function FilterBar({ filter, onChange, shown, total }: { filter: CreatorFilter; onChange: (filter: CreatorFilter) => void; shown: number; total: number }) {
  const mobile = useMobile();
  const [open, setOpen] = useState(false);
  const set = (patch: Partial<CreatorFilter>) => onChange({ ...filter, ...patch });
  const options = <>
    <Chips label="Số người theo dõi" options={TIERS} value={filter.tier} onChange={(tier) => set({ tier })} allLabel="Tất cả" />
    <Chips label="Giá mỗi video" options={PRICE_BANDS} value={filter.price} onChange={(price) => set({ price })} allLabel="Tất cả" />
    <Chips label="Sắp xếp" options={SORTS.slice(1)} value={filter.sort} onChange={(sort) => set({ sort })} allLabel="Điểm cao nhất" />
  </>;
  const extra = optionCount(filter);
  return <section className="filter-bar" aria-label="Lọc và sắp xếp KOC trong danh sách">
    <div className="filter-row">
      <div className="filter-search"><Search size={16} aria-hidden="true" /><input type="search" aria-label="Lọc KOC theo tên hoặc handle" placeholder="Lọc theo tên hoặc handle" value={filter.q} onChange={(event) => set({ q: event.target.value })} /></div>
      {mobile && <Drawer.Root open={open} onOpenChange={setOpen} direction="bottom">
        <button type="button" className="filter-toggle" onClick={() => setOpen(true)}><SlidersHorizontal size={16} aria-hidden="true" />Bộ lọc{extra > 0 && <span className="filter-badge">{extra}<span className="sr-only"> bộ lọc đang bật</span></span>}</button>
        <Drawer.Portal><Drawer.Overlay className="drawer-overlay" /><Drawer.Content className="drawer-content" aria-describedby={undefined}>
          <Drawer.Handle className="drawer-handle" /><Drawer.Title className="sr-only">Bộ lọc KOC</Drawer.Title>
          <div className="drawer-scroll filter-drawer">{options}
            <div className="filter-drawer-actions"><button type="button" className="text-button" onClick={() => onChange({ ...filter, tier: '', price: '', sort: '' })}>Xóa bộ lọc</button><button type="button" className="pill-button" onClick={() => setOpen(false)}>Xem {shown} KOC</button></div>
          </div>
        </Drawer.Content></Drawer.Portal>
      </Drawer.Root>}
    </div>
    {!mobile && <div className="filter-options">{options}</div>}
    {filterActive(filter) && <p className="filter-status" role="status">Hiển thị {shown}/{total} KOC. <button type="button" className="text-button" onClick={() => onChange(EMPTY)}><X size={14} aria-hidden="true" /> Xóa bộ lọc</button></p>}
  </section>;
}

export function FilterEmpty({ onClear }: { onClear: () => void }) {
  return <div className="empty-state filter-empty" role="status"><p>Không có KOC nào khớp bộ lọc. Thử bỏ bớt điều kiện hoặc tìm tên khác.</p><button type="button" className="pill-button" onClick={onClear}>Xóa bộ lọc</button></div>;
}
