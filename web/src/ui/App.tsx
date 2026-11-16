import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react';
import { Command } from 'cmdk';
import { Search } from 'lucide-react';
import { Link, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { api } from '../api';
import type { Campaign, RunProposal } from '../types';
import { fold } from './filters';
import { SiteFooter, SiteHeader } from './SharedSite';

const CampaignListPage = lazy(() => import('./pages').then((pages) => ({ default: pages.CampaignListPage })));
const LandingPage = lazy(() => import('./LandingPage'));
const CampaignFormPage = lazy(() => import('./pages').then((pages) => ({ default: pages.CampaignFormPage })));
const CampaignResultsPage = lazy(() => import('./pages').then((pages) => ({ default: pages.CampaignResultsPage })));
const ProposalPage = lazy(() => import('./pages').then((pages) => ({ default: pages.ProposalPage })));
const RunProposalPage = lazy(() => import('./pages').then((pages) => ({ default: pages.RunProposalPage })));
const CreatorPage = lazy(() => import('./pages').then((pages) => ({ default: pages.CreatorPage })));
const OperatorPage = lazy(() => import('./ops').then((page) => ({ default: page.OperatorPage })));

function PageBoundary({ children }: { children: ReactNode }) {
  return <Suspense fallback={<section className="page narrow empty-state">Đang tải trang…</section>}>{children}</Suspense>;
}

function SearchPalette({ open, onClose, runPicks, latestRunId }: { open: boolean; onClose: () => void; runPicks: RunProposal['picks']; latestRunId: string }) {
  const [query, setQuery] = useState('');
  const [creators, setCreators] = useState<{ creator_id: string; nickname: string; handle: string }[]>([]);
  const [campaigns, setCampaigns] = useState<Pick<Campaign, 'campaign_id' | 'input'>[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    api.campaigns().then(setCampaigns).catch(() => setCampaigns([]));
  }, [open]);

  useEffect(() => {
    if (query.trim().length < 1) {
      setCreators([]);
      return;
    }
    api.creators(query).then(setCreators).catch(() => setCreators([]));
  }, [query]);

  return (
    <Command.Dialog open={open} filter={(value, search) => fold(value).includes(fold(search)) ? 1 : 0} onOpenChange={onClose} label="Tìm KOC hoặc chiến dịch" className="search-dialog">
      <div className="search-box"><Search size={18} aria-hidden="true" /><Command.Input autoFocus value={query} onValueChange={setQuery} placeholder="Nhập tên KOC hoặc chiến dịch" /></div>
      <Command.List>
        <Command.Empty>Không tìm thấy kết quả.</Command.Empty>
        {creators.length > 0 && <Command.Group heading="KOC">
          {creators.map((creator) => <Command.Item key={creator.creator_id} value={`${creator.nickname} ${creator.handle}`} onSelect={() => { navigate(`/koc/${creator.creator_id}`); onClose(); }}>
            <span>{creator.nickname}</span><small>{creator.handle}</small>
          </Command.Item>)}
        </Command.Group>}
        {runPicks.length > 0 && <Command.Group heading="KOC trong đề xuất mẫu">
          {runPicks.map((creator) => <Command.Item key={creator.creator_id} value={`${creator.nickname} ${creator.handle}`} onSelect={() => { navigate(`/de-xuat/${latestRunId}/koc/${creator.creator_id}`); onClose(); }}>
            <span>{creator.nickname}</span><small>{creator.handle}</small>
          </Command.Item>)}
        </Command.Group>}
        <Command.Group heading="Điều hướng">
          <Command.Item value="Danh sách chiến dịch" onSelect={() => { navigate('/chien-dich'); onClose(); }}>
            <span>Danh sách chiến dịch</span><small>Xem các chiến dịch đã lưu</small>
          </Command.Item>
        </Command.Group>
        {campaigns.length > 0 && <Command.Group heading="Chiến dịch đã lưu">
          {campaigns.filter((campaign) => fold(`${campaign.input.brand_name} ${campaign.input.product_type}`).includes(fold(query))).map((campaign) => <Command.Item key={campaign.campaign_id} value={`${campaign.input.brand_name} ${campaign.input.product_type}`} onSelect={() => { navigate(`/chien-dich/${campaign.campaign_id}`); onClose(); }}>
            <span>{campaign.input.brand_name}</span><small>{campaign.input.product_type}</small>
          </Command.Item>)}
        </Command.Group>}
      </Command.List>
      <p className="search-hint">Dùng phím ↑ ↓ để chọn, Enter để mở, Esc để đóng</p>
    </Command.Dialog>
  );
}

export default function App() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [sampleProposal, setSampleProposal] = useState<RunProposal | null>(null);
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 767px)').matches);
  const location = useLocation();
  const latestRunId = sampleProposal?.run_id ?? '';
  useEffect(() => { api.latestRun().then(({ run_id }) => api.runProposal(run_id)).then(setSampleProposal).catch(() => setSampleProposal(null)); }, []);
  const backgroundLocation = mobile ? location.state?.backgroundLocation : undefined;
  useEffect(() => {
    const path = location.pathname;
    document.title = path === '/' ? 'DETOLA KOC Discovery'
      : path === '/chien-dich/moi' ? 'Tạo chiến dịch · DETOLA KOC Discovery'
        : path === '/chien-dich' ? 'Chiến dịch · DETOLA KOC Discovery'
          : path.startsWith('/de-xuat') ? 'Đề xuất · DETOLA KOC Discovery'
            : path.startsWith('/chien-dich/') ? 'Kết quả · DETOLA KOC Discovery'
              : path.startsWith('/koc/') ? 'KOC · DETOLA KOC Discovery'
                : path === '/van-hanh' ? 'Vận hành · DETOLA KOC Discovery'
                  : 'Không tìm thấy trang · DETOLA KOC Discovery';
  }, [location.pathname]);
  useEffect(() => {
    const query = window.matchMedia('(max-width: 767px)');
    const update = () => setMobile(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setSearchOpen((value) => !value);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return <>
    <div className="app-shell" inert={searchOpen}>
    <a className="skip-link" href="#main-content">Đến nội dung chính</a>
    <SiteHeader onSearch={() => setSearchOpen(true)} hideCTA={location.pathname === '/chien-dich' || location.pathname === '/chien-dich/moi'} />
    <main id="main-content" tabIndex={-1} inert={Boolean(backgroundLocation)} aria-hidden={backgroundLocation ? true : undefined}><Routes location={backgroundLocation || location}>
      <Route path="/" element={<PageBoundary><LandingPage /></PageBoundary>} />
      <Route path="/chien-dich" element={<PageBoundary><CampaignListPage /></PageBoundary>} />
      <Route path="/chien-dich/moi" element={<PageBoundary><CampaignFormPage /></PageBoundary>} />
      <Route path="/chien-dich/:id" element={<PageBoundary><CampaignResultsPage /></PageBoundary>} />
      <Route path="/chien-dich/:id/de-xuat" element={<PageBoundary><ProposalPage /></PageBoundary>} />
      <Route path="/de-xuat" element={<PageBoundary><RunProposalPage /></PageBoundary>} />
      <Route path="/de-xuat/:runId" element={<PageBoundary><RunProposalPage /></PageBoundary>} />
      <Route path="/de-xuat/:runId/koc/:creatorId" element={<PageBoundary><CreatorPage /></PageBoundary>} />
      <Route path="/koc/:id" element={<PageBoundary><CreatorPage /></PageBoundary>} />
      <Route path="/van-hanh" element={<PageBoundary><OperatorPage /></PageBoundary>} />
      <Route path="*" element={<section className="page narrow"><h1>Không tìm thấy trang</h1><Link to="/chien-dich">Về danh sách chiến dịch</Link></section>} />
    </Routes></main>
    <SiteFooter />
    </div>
    {backgroundLocation && <Routes><Route path="/koc/:id" element={<PageBoundary><CreatorPage /></PageBoundary>} /><Route path="/de-xuat/:runId/koc/:creatorId" element={<PageBoundary><CreatorPage /></PageBoundary>} /></Routes>}
    <Toaster position="top-center" richColors toastOptions={{ classNames: { success: 'toast-success' } }} />
    <SearchPalette open={searchOpen} onClose={() => setSearchOpen(false)} runPicks={sampleProposal?.picks ?? []} latestRunId={latestRunId} />
  </>;
}
