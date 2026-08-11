/** Shared types for Content Intelligence Workspace (Plan). */

export interface ConfidenceFactors {
  composite: number;
  trend: number;
  audience_fit: number;
  authority: number;
  timing: number;
  competition: number;
  freshness: number;
}

export interface OpportunityRecommendation {
  should_generate: boolean;
  stars: number;
  why: string[];
  estimated_read_minutes?: number;
  editing_effort?: string;
}

export interface PublisherCount {
  name: string;
  count: number;
}

export interface SimilarPost {
  id: string;
  title: string;
  content_type?: string;
  impressions?: number | null;
  note?: string;
}

export interface ContentOpportunity {
  id: string;
  title: string;
  kind?: string;
  timeline_bucket: 'today' | 'this_week' | 'later' | string;
  timing_advice?: string;
  opportunity_score: number;
  confidence: ConfidenceFactors;
  recommendation: OpportunityRecommendation;
  sources: {
    by_publisher: PublisherCount[];
    article_ids: string[];
    source_count?: number;
  };
  why_selected: string[];
  audiences: string[];
  primary_angle: string;
  alt_angles: string[];
  lifecycle_stage: string;
  duplicate?: {
    already_covered?: boolean;
    covered_at?: string | null;
    peer_draft_id?: string | null;
  };
  similar_posts: SimilarPost[];
  similar_posts_note?: string | null;
  fortnight_fit?: { content_type?: string; gap_remaining?: number };
  priority?: string;
  primary_article_id?: string;
  user_decision?: string;
  estimates_label?: string;
}

export interface StrategistBriefing {
  greeting: string;
  narrative: string[];
  recommended_action?: {
    label: string;
    action?: 'regenerate_plan' | 'generate_post' | string;
    opportunity_id: string;
    content_type?: string;
    primary_article_id?: string;
    stars?: number;
  } | null;
  memory?: string[];
  spacing_hint?: string | null;
  briefing: {
    articles_analysed: number;
    opportunities: number;
    trends: number;
    high_priority: number;
    recommended_today: number;
    already_scheduled: number;
    needs_review: number;
    average_opportunity_score?: number;
    label?: string;
  };
  strategic_goal: {
    statement: string;
    progress_pct: number;
    suggested_next_topic: string;
  };
  generate_first?: Array<{ id: string; title: string; score: number; primary_article_id?: string }>;
  later?: Array<{ id: string; title: string; score: number; primary_article_id?: string }>;
  plan_health?: {
    target?: Record<string, number>;
    counts?: Record<string, number>;
    gaps?: Record<string, number>;
    window?: { mode?: 'weekly' | 'fortnight' | string; start?: string; end?: string };
    days_left?: number;
    slots?: PlanSlot[];
    needs_capture?: Record<string, number>;
  };
  review_queue?: ReviewQueueItem[];
}

export interface PlanSlotItem {
  draft_id: string;
  content_type?: string | null;
  status?: string | null;
  suggested_date?: string;
}

export interface PlanSlot {
  date: string;
  label: string;
  draft_ids: string[];
  items: PlanSlotItem[];
  open: boolean;
  suggested_content_type?: string | null;
}

export interface ReviewQueueItem {
  id: string;
  hook?: string | null;
  body?: string | null;
  cta?: string | null;
  hashtags?: string[];
  content_type?: string;
  status?: string;
  created_at?: string | null;
  image_url?: string | null;
  image_generating?: boolean;
  article_id?: string | null;
}
