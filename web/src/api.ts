import type { Campaign, CampaignInput, CreatorDetail, OpsRun, PreviousRun, RunProposal, Stats } from './types';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = typeof body === 'object' && body && 'detail' in body ? body.detail : null;
    throw new Error(typeof detail === 'string' ? detail : 'Không thể tải dữ liệu. Vui lòng thử lại.');
  }
  return response.json() as Promise<T>;
}

export const api = {
  stats: () => request<Stats>('/stats'),
  campaigns: () => request<(Pick<Campaign, 'campaign_id' | 'created_at' | 'input'> & { picked_count: number })[]>('/campaigns'),
  campaign: (id: string) => request<Campaign>(`/campaigns/${id}`),
  createCampaign: (input: CampaignInput) => request<Campaign>('/campaigns', { method: 'POST', body: JSON.stringify(input) }),
  creator: (id: string) => request<CreatorDetail>(`/creators/${id}`),
  creators: (query: string) => request<{ creator_id: string; nickname: string; handle: string }[]>(`/creators?q=${encodeURIComponent(query)}`),
  runs: () => request<OpsRun[]>('/ops/runs'),
  latestRun: () => request<{ run_id: string }>('/runs/latest'),
  previousRuns: (productType: string) => request<PreviousRun[]>(`/runs/previous?product_type=${encodeURIComponent(productType)}`),
  runProposal: (id: string) => request<RunProposal>(`/runs/${id}/proposal`),
  runCreator: (runId: string, creatorId: string) => request<CreatorDetail>(`/runs/${runId}/creators/${creatorId}`),
};

export function formatVnd(value: number) {
  return `${new Intl.NumberFormat('vi-VN').format(value)} ₫`;
}

export function formatFollowers(value: number) {
  return `${new Intl.NumberFormat('vi-VN').format(value)} người theo dõi`;
}
