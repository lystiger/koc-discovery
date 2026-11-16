import { useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, Search } from 'lucide-react';
import { api } from '../api';
import { BrandLogo } from './BrandLogo';

const steps = [
  { title: 'Sản phẩm', icon: 'brief' },
  { title: 'Chọn KOC', icon: 'creators' },
  { title: 'Đề xuất', icon: 'proposal' },
] as const;

export function PrimaryLink({ to, children, className = '', 'aria-label': ariaLabel }: { to: string; children: ReactNode; className?: string; 'aria-label'?: string }) {
  return <Link className={`pill-button ${className}`} to={to} aria-label={ariaLabel}>{children}<ArrowRight size={18} aria-hidden="true" /></Link>;
}

export function PrimaryButton({ children, className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`pill-button ${className}`} {...props}>{children}<ArrowRight size={18} aria-hidden="true" /></button>;
}

export function SecondaryLink({ to, children, className = '' }: { to: string; children: ReactNode; className?: string }) {
  return <Link className={`text-link ${className}`} to={to}>{children}</Link>;
}

export function SiteHeader({ onSearch, hideCTA = false }: { onSearch: () => void; hideCTA?: boolean }) {
  const [proposalPath, setProposalPath] = useState<string | null>(null);
  const location = useLocation();
  useEffect(() => {
    api.latestRun()
      .then(({ run_id }) => api.runProposal(run_id).then(() => '/de-xuat'))
      .catch(() => api.campaigns().then((items) => items[0] ? `/chien-dich/${items[0].campaign_id}/de-xuat` : null))
      .then(setProposalPath);
  }, []);
  return <header className="site-header">
    <Link className="wordmark" to="/" aria-label="DETOLA KOC Discovery"><BrandLogo variant="header" /></Link>
    <nav aria-label="Điều hướng chính">
      <Link to="/chien-dich" aria-current={location.pathname.startsWith('/chien-dich') ? 'page' : undefined}>Chiến dịch của tôi</Link>
      {proposalPath && <Link to={proposalPath}>Đề xuất mẫu</Link>}
    </nav>
    <button className="search-trigger" onClick={onSearch}><Search size={16} aria-hidden="true" /><span className="search-label">Tìm KOC hoặc chiến dịch</span><kbd>Ctrl K</kbd></button>
    {!hideCTA && <PrimaryLink className="header-cta" to="/chien-dich/moi" aria-label="Bắt đầu chiến dịch"><span className="header-cta-label"><span className="header-cta-full">Bắt đầu chiến dịch</span><span className="header-cta-short">Bắt đầu</span></span></PrimaryLink>}
  </header>;
}

export function SiteFooter() {
  return <footer className="site-footer"><BrandLogo variant="stack" /><span>Đề xuất KOC rõ ràng, có căn cứ.</span><Link to="/van-hanh">Vận hành</Link></footer>;
}

export function TitleBlock({ children, subtitle, className = '' }: { children: ReactNode; subtitle?: ReactNode; className?: string }) {
  return <div className={`title-block rise ${className}`}><h1>{children}</h1>{subtitle && <p>{subtitle}</p>}</div>;
}

export function StepIcon({ icon }: { icon: (typeof steps)[number]['icon'] }) {
  if (icon === 'brief') return <svg viewBox="0 0 96 96" fill="none" stroke="#1F2A24" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="48" cy="48" r="44" fill="#F3E3D8" stroke="none"/><rect x="28" y="20" width="40" height="54" rx="6" fill="#FFFDF9"/><path d="M36 34h24M36 44h24M36 54h14"/><path d="m58 60 12-12 6 6-12 12h-6z" fill="#B5643C"/></svg>;
  if (icon === 'creators') return <svg viewBox="0 0 96 96" fill="none" stroke="#1F2A24" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="48" cy="48" r="44" fill="#DCE8E2" stroke="none"/><circle cx="34" cy="40" r="10" fill="#FFFDF9"/><circle cx="62" cy="40" r="10" fill="#FFFDF9"/><path d="M20 70c2-9 8-14 14-14s12 5 14 14m-2 0c2-9 8-14 14-14s12 5 14 14m-30-46 4-6 4 6" stroke="#2F5D50"/></svg>;
  return <svg viewBox="0 0 96 96" fill="none" stroke="#1F2A24" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="48" cy="48" r="44" fill="#F3E3D8" stroke="none"/><path d="M30 18h28l10 10v50H30z" fill="#FFFDF9"/><path d="M58 18v10h10M38 44h22M38 52h22M38 60h12"/><circle cx="64" cy="66" r="10" fill="#2F5D50" stroke="none"/><path d="m59 66 3.5 3.5L69 62" stroke="#fff"/></svg>;
}

export function StepIndicator({ current }: { current: 1 | 2 | 3 }) {
  return <ol className="step-indicator" aria-label={`Đang ở bước ${current} trên 3`}>
    {steps.map((step, index) => <li className={index + 1 === current ? 'current' : index + 1 < current ? 'complete' : ''} key={step.icon} aria-current={index + 1 === current ? 'step' : undefined}>
      <StepIcon icon={step.icon} /><span>{step.title}</span>
    </li>)}
  </ol>;
}
