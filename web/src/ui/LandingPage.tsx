import { useEffect, useState } from 'react';
import NumberFlow from '@number-flow/react';
import { api } from '../api';
import type { Stats } from '../types';
import { BudgetStrip } from './BudgetStrip';
import { PrimaryLink, SecondaryLink, StepIcon, TitleBlock } from './SharedSite';

const steps = [
  { title: 'Kể về sản phẩm', text: 'Tên thương hiệu, loại sản phẩm, ngân sách và kiểu KOC bạn muốn hợp tác.', icon: 'brief' },
  { title: 'Xem KOC phù hợp', text: 'Mỗi người có điểm bán hàng, khán giả, nội dung và lý do viết bằng tiếng Việt.', icon: 'creators' },
  { title: 'Nhận bản đề xuất', text: 'Một trang gọn để gửi cấp trên hoặc in ra PDF, chi phí đã chia theo từng KOC.', icon: 'proposal' },
] as const;

const demoCreators = [
  { id: 'landing-linh', name: 'Linh Skin Daily', costVnd: 6_500_000 },
  { id: 'landing-chou', name: 'Chou Chou', costVnd: 5_500_000 },
  { id: 'landing-trinh', name: 'Trịnh Mỹ Phẩm', costVnd: 7_000_000 },
  { id: 'landing-mai', name: 'BS. Mai', costVnd: 5_000_000 },
  { id: 'landing-an', name: 'An', costVnd: 4_500_000 },
];

export default function LandingPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [sampleProposalPath, setSampleProposalPath] = useState<string | null>(null);

  useEffect(() => {
    api.stats().then(setStats).catch(() => setStats(null));
    api.latestRun()
      .then(({ run_id }) => api.runProposal(run_id).then(() => '/de-xuat'))
      .catch(() => api.campaigns().then((campaigns) => campaigns[0] ? `/chien-dich/${campaigns[0].campaign_id}/de-xuat` : null))
      .then(setSampleProposalPath);
  }, []);

  useEffect(() => {
    const elements = document.querySelectorAll('.landing .landing-reveal');
    if (!('IntersectionObserver' in window)) {
      elements.forEach((element) => element.classList.add('in'));
      return;
    }
    const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in');
        observer.unobserve(entry.target);
      }
    }), { threshold: 0.3 });
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);

  return <div className="landing">
    <section className="landing-hero">
      <div>
        <TitleBlock className="d1">Tìm đúng KOC cho <em>thương hiệu của bạn</em></TitleBlock>
        <p className="landing-lede rise d2">Nhập sản phẩm và ngân sách. KOC Discovery chọn những nhà sáng tạo hợp với khách hàng của bạn, kèm số liệu, đoạn video làm bằng chứng và chi phí ước tính cho từng người.</p>
        <div className="landing-cta rise d3">
          <PrimaryLink className="landing-button" to="/chien-dich/moi">Bắt đầu chiến dịch</PrimaryLink>
          {sampleProposalPath && <SecondaryLink className="landing-text-link" to={sampleProposalPath}>Xem một bản đề xuất mẫu</SecondaryLink>}
        </div>
        <p className="landing-note rise d4">Mất khoảng 2 phút. Không cần tài khoản.</p>
      </div>
      <div className="landing-art" aria-hidden="true">
        <div className="landing-art-floater"><img src="/assets/b-hero.webp" alt="" width="1100" height="697" fetchPriority="high" /></div>
        <svg className="landing-overlay" viewBox="0 0 120 100" preserveAspectRatio="xMidYMid meet" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path className="handoff" d="M44 30 C 56 14, 70 14, 80 24" stroke="#B5643C" strokeWidth=".9" strokeDasharray="2.4 2.4"/>
          <path className="twinkle" d="M14 18l1.4 3.4 3.4 1.4-3.4 1.4-1.4 3.4-1.4-3.4-3.4-1.4 3.4-1.4z" fill="#F3E3D8" stroke="#B5643C" strokeWidth=".7"/>
          <path className="twinkle t2" d="M106 14l1.1 2.7 2.7 1.1-2.7 1.1-1.1 2.7-1.1-2.7-2.7-1.1 2.7-1.1z" fill="#DCE8E2" stroke="#2F5D50" strokeWidth=".7"/>
          <path className="twinkle t3" d="M60 8l.9 2.2 2.2.9-2.2.9-.9 2.2-.9-2.2-2.2-.9 2.2-.9z" fill="#F3E3D8" stroke="#B5643C" strokeWidth=".6"/>
          <path className="heart h1" d="M92 40c-1.6-2.2-5-1-4 1.8.6 1.6 4 4 4 4s3.4-2.4 4-4c1-2.8-2.4-4-4-1.8z" fill="#B5643C"/>
          <path className="heart h2" d="M100 46c-1.2-1.7-3.8-.8-3 1.4.5 1.2 3 3 3 3s2.5-1.8 3-3c.8-2.2-1.8-3.1-3-1.4z" fill="#2F5D50"/>
          <path className="heart h3" d="M84 46c-1.2-1.7-3.8-.8-3 1.4.5 1.2 3 3 3 3s2.5-1.8 3-3c.8-2.2-1.8-3.1-3-1.4z" fill="#3F7464"/>
        </svg>
      </div>
    </section>

    <section className="landing-steps">
      <div className="landing-steps-inner">
        <h2>Từ một bản brief đến danh sách KOC sẵn sàng liên hệ</h2>
        <div className="landing-step-row">
          {steps.map((step) => <article className="landing-step landing-reveal" key={step.icon}>
            <StepIcon icon={step.icon} />
            <h3>{step.title}</h3>
            <p>{step.text}</p>
          </article>)}
        </div>
      </div>
    </section>

    <section className="landing-demo">
      <div>
        <h2>Ngân sách được chia rõ ràng</h2>
        <p>Bạn thấy ngay mỗi KOC chiếm bao nhiêu trong ngân sách, và còn lại bao nhiêu. Chi phí là ước tính, bạn xác nhận lại với KOC trước khi chốt.</p>
      </div>
      <BudgetStrip className="landing-board landing-reveal" budgetVnd={30_000_000} creators={demoCreators} caption="Ví dụ: kem chống nắng, 5 KOC" animateOnReveal
        note="Chi phí là ước tính theo mức booking phổ biến. Cần xác nhận với KOC hoặc MCN trước khi chốt." />
    </section>

    <section className="landing-trust">
      <h2>Dữ liệu đang có</h2>
      <dl>
        <div><dt>KOC trong lượt tuyển chọn mới nhất</dt><dd>{stats ? <NumberFlow value={stats.creators_in_pool} locales="vi-VN" /> : '—'}</dd></div>
        <div><dt>KOC có điểm nội dung</dt><dd>{stats ? <NumberFlow value={stats.creators_with_s3_score} locales="vi-VN" /> : '—'}</dd></div>
        <div><dt>Video đã phân tích</dt><dd>{stats ? <NumberFlow value={stats.analyzed_videos} locales="vi-VN" /> : '—'}</dd></div>
      </dl>
    </section>

    <section className="landing-close">
      <h2>Bắt đầu với sản phẩm của bạn</h2>
      <p>Nhập thông tin chiến dịch để xem danh sách KOC phù hợp.</p>
      <PrimaryLink className="landing-button" to="/chien-dich/moi">Bắt đầu chiến dịch</PrimaryLink>
    </section>
  </div>;
}
