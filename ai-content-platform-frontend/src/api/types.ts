export interface ApiEnvelope<T> {
  data: T;
  error: string | null;
  meta: ApiMeta | null;
}

export interface ApiMeta {
  page?: number;
  per_page?: number;
  total?: number;
  total_pages?: number;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'editor' | 'viewer';
  organization_id: string;
  avatar_url?: string;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Article {
  id: string;
  title: string;
  summary: string;
  source_name: string;
  source_url?: string;
  url?: string;
  published_at: string;
  relevance_score?: number;
  category?: string;
  categories?: string[];
  status?: string;
  created_at?: string;
}

export interface Draft {
  id: string;
  title?: string;
  content?: string;
  generated_text?: string;
  edited_text?: string;
  hook?: string;
  cta?: string;
  hashtags?: string[];
  article_id?: string;
  article_title?: string;
  content_type?: string;
  status: 'draft' | 'pending_review' | 'approved' | 'published' | 'rejected' | string;
  tone?: string;
  word_count?: number;
  version?: number;
  linkedin_preview?: string;
  created_at?: string;
  updated_at?: string;
  article?: {
    id: string;
    title: string;
    summary?: string;
    url?: string;
    source_name?: string;
    published_at?: string;
    category?: string;
  } | null;
  variations?: Array<{ index: number; hook?: string; body?: string }>;
  quality?: unknown;
  visual_brief?: unknown;
  metadata?: Record<string, unknown>;
}

export interface Carousel {
  id: string;
  title: string;
  slides_count: number;
  status: 'generating' | 'ready' | 'published';
  thumbnail_url?: string;
  created_at: string;
}

export interface BrandKit {
  id: string;
  organization_id?: string;
  name?: string;
  organization_name?: string;
  tagline?: string;
  primary_color: string;
  secondary_color: string;
  accent_color?: string;
  tone_of_voice?: string;
  tone_json?: Record<string, unknown>;
  target_audience?: string;
  industry?: string;
  logo_url?: string;
  description?: string;
  footer_text?: string;
  services_line?: string;
  client_profile_path?: string | null;
  /** Org brand profile Markdown — relevance + draft memory */
  client_profile_md?: string | null;
  extra_settings?: Record<string, unknown>;
  default_image_count?: number;
  /** When true, image generation is queued automatically after draft creation */
  auto_generate_image_with_draft?: boolean;
  /** Brand publishing mix window */
  publishing_window?: 'weekly' | 'fortnight';
  publishing_targets?: {
    educational?: number;
    success_story?: number;
    personal_achievement?: number;
  } | null;
}

export interface BrandProfileTemplate {
  generator_prompt: string;
  outline: string;
  section_headings: string[];
}

export interface NewsSource {
  id: string;
  name: string;
  url: string;
  type: 'rss' | 'api' | 'scraper';
  status: 'active' | 'inactive' | 'error';
  last_fetched_at?: string;
  articles_count: number;
}

export interface Job {
  id: string;
  type: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | string;
  progress: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  created_at: string;
  payload?: Record<string, unknown>;
  result?: Record<string, unknown>;
  attempts?: number;
}

export interface LearningExample {
  id: string;
  title: string;
  content: string;
  category: string;
  rating: number;
  created_at: string;
}

export interface LearningRule {
  id: string;
  rule: string;
  category: string;
  priority: number;
  active: boolean;
}

export interface HealthResponse {
  status: string;
  version: string;
  uptime: number;
  counts?: {
    articles: number;
    drafts: number;
    sources: number;
    jobs_running: number;
  };
}
