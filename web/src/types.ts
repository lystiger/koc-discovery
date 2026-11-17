export type ExcludedKoc = {
  id: string;
  handle: string;
  nickname?: string;
  max_brand_fit: number | null;
  reason_vi: string | null;
  videos?: { video_id: string; title: string; brand_fit: number | null }[];
};

export type Creator = {
  creator_id: string;
  nickname: string;
  handle: string;
  followers: number;
  avatar?: string | null;
  mcn?: string | null;
  fit: number;
  confidence: 'Đầy đủ' | 'Một phần' | 'Sơ bộ';
  confidence_count: number;
  audience_age_missing?: boolean;
  components: { commercial: number | null; audience: number | null; content: number | null };
  cost_vnd: number;
  price_per_video_vnd?: number;
  reason: string;
  evidence_ids: string[];
  video_evidence_ids?: string[];
  analysed_video_ids?: string[];
  audience_note?: string | null;
  scoring_note?: string | null;
  caveats?: { text: string; evidence_ids: string[] }[];
  reasons?: { text: string; evidence_ids: string[] }[];
};

export type CampaignInput = {
  brand_name: string;
  product_type: string;
  product_specs: string;
  budget_vnd: number;
  count: number;
  followers_min: number;
  followers_max: number;
  target: { gender: 'Nữ' | 'Nam' | 'Tất cả'; age_groups: ('18-24' | '25-34' | '35-44' | '45-54' | '55+')[] };
  avoid_same_mcn: boolean;
  exclude_run_ids?: string[];
};

export type Range = { low: number; high: number };
export type RunEstimate = { label: string; limit: number; credits: Range; usd: Range; tokens: Range; minutes: Range };
export type PreviousRun = { run_id: string; started_at: string; creator_ids: string[] };

export type Campaign = {
  campaign_id: string;
  created_at: string;
  input: CampaignInput;
  result: {
    status?: 'ok' | 'refused' | 'needs_run';
    picked?: Creator[];
    alternates?: Creator[];
    total_cost_vnd?: number;
    warnings?: string[];
    run_command?: string;
    run_command_notes?: string[];
    leftover_vnd?: number;
    budget_vnd?: number;
    options?: {
      max_count_within_budget: { count: number; cost_vnd: number } | null;
      min_budget_for_count: { budget_vnd: number } | null;
      cheaper_follower_band: { follower_min: number; follower_max: number; cost_vnd: number } | null;
    };
    ranked_count?: number;
    run_id?: string | null;
    low_confidence_pool?: boolean;
    brand_fit_excluded?: ExcludedKoc[];
    run_estimate?: RunEstimate | null;
    ranked_pool?: Creator[];
  };
};

export type CreatorDetail = {
  creator_id: string;
  nickname: string;
  handle: string;
  followers: number;
  cost_vnd?: number;
  avatar?: string | null;
  bio: string;
  mcn?: string | null;
  metrics: Record<string, { value: unknown; source: string | null }>;
  audience_text?: string | null;
  audience_note?: string | null;
  scoring_note?: string | null;
  scores: Record<string, number>;
  reasons: { text: string; evidence_ids: string[] }[];
  caveats: { text: string; evidence_ids: string[] }[];
  video_evidence_ids: string[];
  videos: { video_id: string; title: string; views?: number; transcript_vi?: string; rubric: { criterion: string; score: number; rationale_vi: string; evidence_ids: string[] }[]; risks_vi: string[]; evidence: { evidence_id: string; start_s: number; end_s?: number; quote_vi?: string; frame_url?: string | null }[] }[];
};

export type OpsRun = {
  run_id: string;
  started_at: string;
  status: string;
  costs: { credits: number; input_tokens: number; output_tokens: number; cost_usd: number; api_latency_ms: number };
  tasks: { stage: string; status: string; count: number }[];
  calibration: Record<string, number>;
};

export type Stats = {
  creators_in_pool: number;
  creators_with_s3_score: number;
  analyzed_videos: number;
};

export type RunProposal = {
  run_id: string;
  started_at: string;
  product: string;
  target: string;
  picks: {
    creator_id: string;
    rank: number;
    nickname: string;
    handle: string;
    followers: number;
    cost_vnd: number;
    score: number;
    score_parts: { commercial: number | null; audience: number | null; content: number | null };
    audience_text: string | null;
    reason: string;
    reasons: { text: string; evidence_ids: string[] }[];
    caveats: string[];
    caveat_evidence: { text: string; evidence_ids: string[] }[];
    audience_note?: string | null;
    scoring_note?: string | null;
    video_evidence_ids: string[];
    analysed_video_ids?: string[];
    evidence_count: number;
    evidence_ids: string[];
  }[];
  total_cost_vnd: number;
  budget_vnd: number;
  brand_fit_excluded?: ExcludedKoc[];
};
