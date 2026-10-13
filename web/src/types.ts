export type Language = 'zh' | 'en';
export interface Health { model_ready: boolean; model: string; detector_configured: boolean; version: string; default_language: Language }
export interface Issue { code: string; severity: string; before: unknown; after: unknown }
export interface Audit { blocked: boolean; issues: Issue[]; requires_review: true }
export interface Attempt { text: string; audit: Audit | null; error?: string | null }
export interface Segment { id: string | number; original: string; output: string; status: 'rewritten' | 'retained' | 'skipped' | 'failed'; audit: Audit; attempts: Attempt[] }
export interface RewriteReport { source: string; output: string; segments: Segment[]; warnings: string[]; model: string; elapsed_seconds: number; requires_review: true; detector_status: 'not_run'; source_sha256: string; output_sha256: string; status: 'completed' | 'partial' | 'failed' | 'unchanged' }
export interface DetectorReport { detector: string; status: string; measured_at: string | null; model_version?: string; source_sha256: string; output_sha256: string; before: unknown; after: unknown; error?: string | null; [key: string]: unknown }
