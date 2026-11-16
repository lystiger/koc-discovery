import { useRef, useState, type CSSProperties, type KeyboardEvent, type MutableRefObject } from 'react';
import NumberFlow from '@number-flow/react';
import { Link } from 'react-router-dom';
import { Popover } from '@base-ui/react/popover';
import { formatVnd } from '../api';

export type BudgetCreator = {
  id: string;
  name: string;
  costVnd: number;
  href?: string;
};

type BudgetStripProps = {
  budgetVnd: number;
  creators: BudgetCreator[];
  caption: string;
  note?: string;
  className?: string;
  onActiveChange?: (id: string | null) => void;
  animateOnReveal?: boolean;
};

function shareText(costVnd: number, budgetVnd: number) {
  const share = budgetVnd > 0 ? costVnd / budgetVnd * 100 : 0;
  return `${new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 }).format(share)}% ngân sách`;
}

function compactVnd(costVnd: number) {
  const unit = costVnd >= 1_000_000 ? 1_000_000 : 1_000;
  const suffix = costVnd >= 1_000_000 ? 'tr' : 'nghìn';
  return `${new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 }).format(costVnd / unit)} ${suffix}`;
}

export function BudgetStrip({ budgetVnd, creators, caption, note, className = '', onActiveChange, animateOnReveal = false }: BudgetStripProps) {
  const totalCost = creators.reduce((sum, creator) => sum + creator.costVnd, 0);
  const spent = Math.min(totalCost, budgetVnd);
  const remaining = Math.max(0, budgetVnd - totalCost);
  const smallRemaining = remaining > 0 && (remaining / Math.max(1, budgetVnd) < 0.22);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const activate = (id: string | null) => {
    setActiveId(id);
    onActiveChange?.(id);
  };
  const moveFocus = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const next = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? (index + 1) % buttons.current.length
      : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? (index - 1 + buttons.current.length) % buttons.current.length
        : event.key === 'Home' ? 0 : event.key === 'End' ? buttons.current.length - 1 : null;
    if (next !== null) {
      event.preventDefault();
      buttons.current[next]?.focus();
    }
  };
  return <section className={`budget-strip ${className}${animateOnReveal ? ' budget-strip-animated' : ''}`} aria-label="Phân bổ ngân sách">
    <div className="budget-strip-heading"><span>{caption}</span><strong><NumberFlow value={spent} locales="vi-VN" format={{ style: 'currency', currency: 'VND', maximumFractionDigits: 0 }} /> / {formatVnd(budgetVnd)}</strong></div>
    <div className="budget-track" role="list" aria-label="Tỷ trọng ngân sách theo KOC">
      {creators.map((creator, index) => {
        return <BudgetSegment key={creator.id} kind="creator" id={creator.id} name={creator.name} costVnd={creator.costVnd}
          budgetVnd={budgetVnd} href={creator.href} index={index} buttons={buttons} activeId={activeId}
          open={openId === creator.id} onOpenChange={(isOpen) => setOpenId(isOpen ? creator.id : null)}
          onActivate={activate} onKeyDown={moveFocus} weight={creator.costVnd} basis="0%" />;
      })}
      {remaining > 0 && <BudgetSegment kind="remaining" id="remaining" name="Còn lại" costVnd={remaining}
        budgetVnd={budgetVnd} index={creators.length} buttons={buttons} activeId={activeId}
        open={openId === 'remaining'} onOpenChange={(isOpen) => setOpenId(isOpen ? 'remaining' : null)}
        onActivate={activate} onKeyDown={moveFocus} weight={smallRemaining ? 0 : remaining}
        basis={smallRemaining ? 'max(12%, 4.5rem)' : '0%'} />}
    </div>
    <div className="budget-breakdown" aria-hidden="true">
      {creators.map((creator) => <div key={creator.id} className="budget-breakdown-item" style={{ '--budget-weight': creator.costVnd, '--budget-basis': '0%' } as CSSProperties}>
        <strong>{compactVnd(creator.costVnd)}</strong><span title={creator.name}>{creator.name}</span>
      </div>)}
      {remaining > 0 && <div className="budget-breakdown-spacer" style={{ '--budget-weight': smallRemaining ? 0 : remaining, '--budget-basis': smallRemaining ? 'max(12%, 4.5rem)' : '0%' } as CSSProperties} />}
    </div>
    <p className="budget-remaining-copy">Còn lại <strong>{formatVnd(remaining)} chưa dùng</strong></p>
    <ul className="budget-accessible-list" aria-label="Số tiền theo từng phần ngân sách">
      {creators.map((creator) => <li key={creator.id}>{creator.name}: {formatVnd(creator.costVnd)}, {shareText(creator.costVnd, budgetVnd)}</li>)}
      {remaining > 0 && <li>Còn lại: {formatVnd(remaining)}, {shareText(remaining, budgetVnd)}</li>}
    </ul>
    <ul className="budget-print-labels" aria-hidden="true">
      {creators.map((creator) => <li key={creator.id}>{creator.name}: {formatVnd(creator.costVnd)}</li>)}
      {remaining > 0 && <li>Còn lại: {formatVnd(remaining)}</li>}
    </ul>
    {note && <small>{note}</small>}
  </section>;
}

type BudgetSegmentProps = {
  kind: 'creator' | 'remaining';
  id: string;
  name: string;
  costVnd: number;
  budgetVnd: number;
  href?: string;
  index: number;
  buttons: MutableRefObject<(HTMLButtonElement | null)[]>;
  activeId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onActivate: (id: string | null) => void;
  onKeyDown: (event: KeyboardEvent<HTMLButtonElement>, index: number) => void;
  weight: number;
  basis: string;
};

function BudgetSegment({ kind, id, name, costVnd, budgetVnd, href, index, buttons, activeId, open, onOpenChange, onActivate, onKeyDown, weight, basis }: BudgetSegmentProps) {
  const remaining = kind === 'remaining';
  const share = shareText(costVnd, budgetVnd);
  return <div className="budget-item" role="listitem" style={{ '--budget-weight': weight, '--budget-basis': basis } as CSSProperties}>
    <Popover.Root open={open} onOpenChange={(isOpen, eventDetails) => {
      if (!isOpen && eventDetails.reason === 'trigger-press') {
        eventDetails.cancel();
        return;
      }
      onOpenChange(isOpen);
    }}>
      <Popover.Trigger
        ref={(element: HTMLButtonElement | null) => { buttons.current[index] = element; }}
        className={`budget-segment${remaining ? ' budget-segment-remaining' : ''}${activeId === id ? ' is-active' : ''}`}
        data-segment={remaining ? 'remaining' : 'creator'}
        data-creator-id={remaining ? undefined : id}
        openOnHover
        delay={250}
        onFocus={() => { onOpenChange(true); onActivate(remaining ? null : id); }}
        onBlur={() => onActivate(null)}
        onMouseEnter={() => onActivate(remaining ? null : id)}
        onMouseLeave={() => onActivate(null)}
        onClick={() => onOpenChange(true)}
        onKeyDown={(event) => onKeyDown(event, index)}
      >{remaining ? <><span className="budget-segment-name">Còn lại</span><span className="budget-segment-amount">{compactVnd(costVnd)}</span></> : <><span className="budget-initial" aria-hidden="true">{Array.from(name.trim())[0]}</span><span className="budget-segment-name">{name}</span></>}</Popover.Trigger>
      <Popover.Portal>
          <Popover.Positioner side="top" sideOffset={8}>
          <Popover.Popup className="budget-popover" initialFocus={false} aria-label={remaining ? "Ngân sách còn lại" : `Chi phí của ${name}`}>
            <strong>{name}</strong>
            <span>{formatVnd(costVnd)}</span>
            <span>{share}</span>
            {!remaining && href && <Link to={href}>Xem KOC</Link>}
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  </div>;
}
