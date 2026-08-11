import { apiClient } from './client';
import type { ApiEnvelope } from './types';

const BASE = '/brand-intelligence';

export type BrandProfileKind = 'corporate' | 'personal' | 'product' | string;

export interface BrandIntelligenceProfile {
  id: string;
  organization_id: string;
  kind: BrandProfileKind;
  name: string;
  is_default: boolean;
  active_memory_id?: string | null;
}

export interface BrandImportArtifact {
  kind: 'logo' | 'guideline' | 'image' | 'video' | 'pdf' | 'document' | 'email' | 'post' | string;
  filename?: string;
  storage_key?: string;
  extracted_text?: string;
  variant?: string;
  mime_type?: string;
  [key: string]: unknown;
}

export interface CreateBrandProfileRequest {
  kind?: BrandProfileKind;
  name?: string;
  is_default?: boolean;
}

export interface CreateBrandImportRequest {
  brand_profile_id: string;
  linkedin_url?: string | null;
  linkedin_about?: string | null;
  linkedin_headline?: string | null;
  linkedin_display_name?: string | null;
  linkedin_posts?: unknown[];
  website_url?: string | null;
  max_pages?: number;
  use_playwright?: boolean;
  artifacts?: BrandImportArtifact[];
}

export interface BrandImportCreated {
  id: string;
  status: string;
  brand_profile_id: string;
}

export interface BrandAnalyzeAccepted {
  job_id: string;
  brand_import_job_id: string;
  status: string;
}

export interface BrandImportJobProgress {
  job_id: string;
  import_id: string;
  stage: string;
  progress_pct: number;
  message?: string | null;
  error?: Record<string, unknown> | null;
  eta_seconds?: number | null;
}

export interface BrandMemoryReview {
  id: string;
  memory_id: string;
  status: string;
  detections: Record<string, unknown>;
  edits: Record<string, unknown>;
}

export interface BrandMemory {
  id: string;
  brand_profile_id: string;
  version_no: number;
  lifecycle: string;
  confidence: number;
  brand_dna?: Record<string, unknown>;
  writing_dna?: Record<string, unknown>;
  visual_dna?: Record<string, unknown>;
  engagement?: Record<string, unknown>;
  completeness?: Record<string, unknown>;
  health?: Record<string, unknown>;
  recommendations?: unknown[];
}

export interface BrandIntelligenceDashboard {
  overall_score?: number | null;
  health?: Record<string, unknown> | null;
  confidence?: number | null;
  topics?: unknown;
  audience?: unknown;
  writing_dna?: Record<string, unknown> | null;
  visual_dna?: Record<string, unknown> | null;
  engagement?: Record<string, unknown> | null;
  missing_assets?: unknown;
  recommendations?: unknown;
  lifecycle?: string;
  version_no?: number;
}

export interface NeverSayPolicy {
  brand_profile_id: string;
  forbidden: string[];
  discouraged: string[];
  legal_restrictions: string[];
  compliance_restrictions: string[];
  avoid_vocabulary: string[];
  never_use: string[];
  preferred_alternatives: Record<string, string>;
}

export interface LogoUpsertRequest {
  variant?: string;
  storage_key: string;
  make_primary?: boolean;
}

export interface LogoUpsertResult {
  variants: Record<string, string>;
  primary_key?: string | null;
}

export interface LinkedInSessionStart {
  provider: string;
  status: string;
  instructions: string;
  organization_id: string;
}

function unwrap<T>(envelope: ApiEnvelope<T>): T {
  return envelope.data;
}

export async function listBrandProfiles(): Promise<BrandIntelligenceProfile[]> {
  const res = await apiClient.get<ApiEnvelope<BrandIntelligenceProfile[]>>(`${BASE}/profiles`);
  return unwrap(res.data) ?? [];
}

export async function createBrandProfile(
  body: CreateBrandProfileRequest
): Promise<BrandIntelligenceProfile> {
  const res = await apiClient.post<ApiEnvelope<BrandIntelligenceProfile>>(`${BASE}/profiles`, body);
  return unwrap(res.data);
}

export async function createBrandImport(body: CreateBrandImportRequest): Promise<BrandImportCreated> {
  const res = await apiClient.post<ApiEnvelope<BrandImportCreated>>(`${BASE}/imports`, body);
  return unwrap(res.data);
}

export interface LinkedInUrlImportRequest {
  linkedin_url: string;
  brand_profile_id?: string | null;
  profile_name?: string | null;
  max_posts?: number;
  website_url?: string | null;
}

export interface LinkedInUrlImportAccepted {
  brand_profile_id: string;
  import_id: string;
  job_id: string;
  brand_import_job_id: string;
  status: string;
  linkedin_url: string;
  mode: string;
}

/** Paste LinkedIn URL only — backend fetches profile/posts/images via saved session. */
export async function importFromLinkedInUrl(
  body: LinkedInUrlImportRequest
): Promise<LinkedInUrlImportAccepted> {
  const res = await apiClient.post<ApiEnvelope<LinkedInUrlImportAccepted>>(
    `${BASE}/linkedin/import`,
    body
  );
  return unwrap(res.data);
}

export async function analyzeBrandImport(importId: string): Promise<BrandAnalyzeAccepted> {
  const res = await apiClient.post<ApiEnvelope<BrandAnalyzeAccepted>>(
    `${BASE}/imports/${importId}/analyze`
  );
  return unwrap(res.data);
}

export async function getBrandImportJob(jobId: string): Promise<BrandImportJobProgress> {
  const res = await apiClient.get<ApiEnvelope<BrandImportJobProgress>>(`${BASE}/jobs/${jobId}`);
  return unwrap(res.data);
}

export async function getBrandMemory(profileId: string): Promise<BrandMemory> {
  const res = await apiClient.get<ApiEnvelope<BrandMemory>>(`${BASE}/profiles/${profileId}/memory`);
  return unwrap(res.data);
}

export async function getBrandDashboard(profileId: string): Promise<BrandIntelligenceDashboard> {
  const res = await apiClient.get<ApiEnvelope<BrandIntelligenceDashboard>>(
    `${BASE}/profiles/${profileId}/dashboard`
  );
  return unwrap(res.data);
}

export interface BrandSourceItem {
  id: string;
  object_type: string;
  source_type: string;
  title?: string | null;
  body_preview?: string;
  canonical_url?: string | null;
  engagement?: Record<string, unknown>;
}

export type LogoPosition =
  | 'top_left'
  | 'top_right'
  | 'bottom_left'
  | 'bottom_right'
  | 'center'
  | 'custom'
  | 'brand_default'
  | 'learned';

export interface LogoPlacementDefaults {
  include_logo: boolean;
  position: string;
  position_source?: string;
  learned_position?: string | null;
  has_logo_asset: boolean;
  size?: string;
  opacity?: number;
  margin?: number;
  safe_area?: boolean;
  custom_x?: number | null;
  custom_y?: number | null;
}

export interface BrandProfileHub {
  profile: BrandIntelligenceProfile;
  memory: BrandMemory | null;
  logo: { primary_key?: string | null; variants: Record<string, string> };
  logo_placement?: LogoPlacementDefaults;
  never_say?: {
    forbidden: string[];
    never_use: string[];
    discouraged: string[];
  } | null;
  sources: BrandSourceItem[];
}

export async function getLogoPlacementDefaults(
  profileId: string
): Promise<LogoPlacementDefaults> {
  const res = await apiClient.get<ApiEnvelope<LogoPlacementDefaults>>(
    `${BASE}/profiles/${profileId}/logo-placement`
  );
  return unwrap(res.data);
}

export async function getBrandProfileHub(profileId: string): Promise<BrandProfileHub> {
  const res = await apiClient.get<ApiEnvelope<BrandProfileHub>>(
    `${BASE}/profiles/${profileId}/hub`
  );
  return unwrap(res.data);
}

export async function uploadBrandAsset(
  profileId: string,
  file: File,
  kind: string = 'logo',
  makePrimary: boolean = true
): Promise<{ storage_key: string; logo?: { primary_key?: string | null } }> {
  const form = new FormData();
  form.append('file', file);
  form.append('kind', kind);
  form.append('make_primary', makePrimary ? 'true' : 'false');
  const res = await apiClient.post<
    ApiEnvelope<{ storage_key: string; logo?: { primary_key?: string | null } }>
  >(`${BASE}/profiles/${profileId}/assets/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return unwrap(res.data);
}

export async function getBrandReview(memoryId: string): Promise<BrandMemoryReview> {
  const res = await apiClient.get<ApiEnvelope<BrandMemoryReview>>(
    `${BASE}/memories/${memoryId}/review`
  );
  return unwrap(res.data);
}

export async function patchBrandReview(
  reviewId: string,
  edits: Record<string, unknown>
): Promise<{ id: string; edits: Record<string, unknown> }> {
  const res = await apiClient.patch<ApiEnvelope<{ id: string; edits: Record<string, unknown> }>>(
    `${BASE}/reviews/${reviewId}`,
    { edits }
  );
  return unwrap(res.data);
}

export async function approveBrandReview(reviewId: string): Promise<BrandMemory> {
  const res = await apiClient.post<ApiEnvelope<BrandMemory>>(
    `${BASE}/reviews/${reviewId}/approve`
  );
  return unwrap(res.data);
}

export async function rejectBrandReview(reviewId: string): Promise<{ id?: string; status?: string }> {
  const res = await apiClient.post<ApiEnvelope<{ id?: string; status?: string }>>(
    `${BASE}/reviews/${reviewId}/reject`
  );
  return unwrap(res.data);
}

export async function getNeverSay(profileId: string): Promise<NeverSayPolicy> {
  const res = await apiClient.get<ApiEnvelope<NeverSayPolicy>>(
    `${BASE}/profiles/${profileId}/never-say`
  );
  return unwrap(res.data);
}

export async function putNeverSay(
  profileId: string,
  body: Partial<NeverSayPolicy>
): Promise<NeverSayPolicy> {
  const res = await apiClient.put<ApiEnvelope<NeverSayPolicy>>(
    `${BASE}/profiles/${profileId}/never-say`,
    body
  );
  return unwrap(res.data);
}

export async function upsertBrandLogo(
  profileId: string,
  body: LogoUpsertRequest
): Promise<LogoUpsertResult> {
  const res = await apiClient.post<ApiEnvelope<LogoUpsertResult>>(
    `${BASE}/profiles/${profileId}/logos`,
    body
  );
  return unwrap(res.data);
}

export async function startLinkedInSession(): Promise<LinkedInSessionStart> {
  const res = await apiClient.post<ApiEnvelope<LinkedInSessionStart>>(
    `${BASE}/session/linkedin/start`
  );
  return unwrap(res.data);
}

export async function saveLinkedInSession(storageStateB64: string): Promise<{ saved: boolean }> {
  const res = await apiClient.post<ApiEnvelope<{ saved: boolean }>>(
    `${BASE}/session/linkedin/save`,
    { storage_state_b64: storageStateB64 }
  );
  return unwrap(res.data);
}

export async function revokeLinkedInSession(): Promise<{ revoked: boolean }> {
  const res = await apiClient.post<ApiEnvelope<{ revoked: boolean }>>(
    `${BASE}/session/linkedin/revoke`
  );
  return unwrap(res.data);
}

export async function syncBrandLatest(
  body: CreateBrandImportRequest
): Promise<BrandImportCreated & BrandAnalyzeAccepted> {
  const res = await apiClient.post<ApiEnvelope<BrandImportCreated & BrandAnalyzeAccepted>>(
    `${BASE}/sync`,
    body
  );
  return unwrap(res.data);
}

/** Known pipeline stages for progress UI. */
export const BRAND_ANALYZE_STAGES = [
  { id: 'queued', label: 'Queued' },
  { id: 'collecting', label: 'Collecting sources' },
  { id: 'collecting_website', label: 'Crawling website' },
  { id: 'collecting_uploads', label: 'Ingesting uploads' },
  { id: 'normalize', label: 'Normalize' },
  { id: 'ocr', label: 'OCR' },
  { id: 'vision', label: 'Vision' },
  { id: 'nlp', label: 'Writing / topics' },
  { id: 'merge', label: 'Semantic merge' },
  { id: 'awaiting_validation', label: 'Awaiting validation' },
  { id: 'failed', label: 'Failed' },
] as const;
