import { useCallback, useEffect, useRef, useState } from 'react';
import { readUtf8, request } from './api';
import { defaultLocale, strings } from './i18n';
import type { Audit, DetectorReport, Health, Language, ManualRevision, RewriteReport } from './types';

export function useWorkbench() {
  const [locale, setLocale] = useState<Language>(defaultLocale);
  const [language, setLanguage] = useState<Language>(defaultLocale);
  const [source, setSource] = useState('');
  const [terms, setTerms] = useState('');
  const [candidates, setCandidates] = useState(2);
  const [health, setHealth] = useState<Health | null>(null);
  const [connectionError, setConnectionError] = useState(false);
  const [report, setReport] = useState<RewriteReport | null>(null);
  const [manualOutput, setManualOutput] = useState<string | null>(null);
  const [manualAudit, setManualAudit] = useState<Audit | null>(null);
  const [detectorReport, setDetectorReport] = useState<DetectorReport | null>(null);
  const [imported, setImported] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState<'rewrite' | 'detector' | 'import' | 'check' | null>(null);
  const [error, setError] = useState('');
  const active = useRef<AbortController | null>(null);
  const revision = useRef(0);
  const localeRef = useRef(locale); localeRef.current = locale;
  const t = strings[locale];

  useEffect(() => { document.documentElement.lang = locale; }, [locale]);
  const refreshHealth = useCallback(async (signal?: AbortSignal) => {
    try { setHealth(await request<Health>('/api/health', undefined, signal)); setConnectionError(false); }
    catch { if (!signal?.aborted) { setHealth(null); setConnectionError(true); } }
  }, []);
  useEffect(() => { const controller = new AbortController(); void refreshHealth(controller.signal); return () => { controller.abort(); active.current?.abort(); }; }, [refreshHealth]);

  function cancel() { active.current?.abort(); active.current = null; revision.current++; setBusy(null); }
  function invalidate() { cancel(); setReport(null); setManualOutput(null); setManualAudit(null); setDetectorReport(null); setImported(false); setConsent(false); setError(''); }
  function changeSource(value: string) { invalidate(); setSource(value); }
  function changeTerms(value: string) { invalidate(); setTerms(value); }
  function changeLanguage(value: Language) { invalidate(); setLanguage(value); }
  function changeCandidates(value: number) { invalidate(); setCandidates(value); }
  function changeOutput(value: string) {
    if (!report) return;
    if (Array.from(value).length > 12000) { setError(t.manualOutputLimit); return; }
    cancel(); setManualOutput(value === report.output ? null : value); setManualAudit(null);
    setDetectorReport(null); setImported(false); setConsent(false); setError('');
  }
  const output = manualOutput ?? report?.output ?? '';
  const manualRevision: ManualRevision | null = manualOutput === null ? null : { output: manualOutput, audit: manualAudit, status: manualAudit ? 'checked' : 'needs_recheck' };
  const tooLong = Array.from(source).length > 12000;

  async function run<T>(kind: 'rewrite' | 'detector' | 'import' | 'check', action: (signal: AbortSignal) => Promise<T>, accept: (value: T) => void) {
    cancel(); const current = revision.current; const controller = new AbortController(); active.current = controller;
    setBusy(kind); setError('');
    try { const value = await action(controller.signal); if (current === revision.current && !controller.signal.aborted) accept(value); }
    catch (failure) { if (current === revision.current && !controller.signal.aborted) setError(failure instanceof Error ? failure.message : strings[localeRef.current].requestFailed); }
    finally { if (current === revision.current) { setBusy(null); active.current = null; } }
  }
  async function recheckDraft() {
    if (!report || manualOutput === null || !output.trim() || busy) return;
    setManualAudit(null);
    await run('check', signal => request<Audit>('/api/check', { source, candidate: output, protected_terms: terms.split(/\r?\n/).map(term => term.trim()).filter(Boolean) }, signal), value => {
      if (!value || typeof value.blocked !== 'boolean' || !Array.isArray(value.issues) || value.requires_review !== true) throw new Error(t.invalidResponse);
      setManualAudit(value);
    });
  }

  async function rewrite() {
    if (!source.trim() || tooLong || busy) return;
    invalidate();
    await run('rewrite', signal => request<RewriteReport>('/api/rewrite', { text: source, language, candidates, protected_terms: terms.split(/\r?\n/).map(term => term.trim()).filter(Boolean) }, signal), value => {
      if (typeof value.output !== 'string' || !Array.isArray(value.segments) || value.source !== source) throw new Error(t.invalidResponse);
      setReport(value);
    });
  }
  async function detect() {
    if (!report || !output.trim() || !consent || !health?.detector_configured || busy) return;
    setDetectorReport(null); setImported(false);
    await run('detector', signal => request<DetectorReport>('/api/detect', { source, candidate: output, consent: true }, signal), value => setDetectorReport(value));
  }
  async function importSource(file?: File) {
    if (!file) return;
    invalidate(); const current = revision.current;
    if (!/\.(txt|md)$/i.test(file.name)) { setError(t.fileType); return; }
    if (file.size > 102400) { setError(t.importSize); return; }
    try { const text = await readUtf8(file); if (current === revision.current) setSource(text); }
    catch { if (current === revision.current) setError(t.fileEncoding); }
  }
  async function importDetector(file?: File) {
    if (!file || !report || !output.trim() || busy) return;
    if (file.size > 1048576) { setError(t.importReportSize); return; }
    const current = revision.current;
    setError('');
    try {
      const parsed: unknown = JSON.parse(await readUtf8(file));
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error(t.invalidReport);
      const wrapped = 'detector_report' in parsed || 'segments' in parsed;
      const importedReport = wrapped ? 'detector_report' in parsed ? parsed.detector_report : null : parsed;
      if (!importedReport || typeof importedReport !== 'object' || Array.isArray(importedReport)) throw new Error(t.invalidReport);
      if (current !== revision.current) return;
      setDetectorReport(null); setImported(false);
      await run('import', signal => request<DetectorReport>('/api/detector-report', { source, candidate: output, report: importedReport }, signal), value => { setDetectorReport(value); setImported(true); });
    } catch (failure) { if (current === revision.current) setError(failure instanceof Error && failure.message === t.invalidReport ? failure.message : t.invalidReport); }
  }

  return { t, locale, setLocale, language, changeLanguage, source, changeSource, output, changeOutput, manualRevision, recheckDraft, terms, changeTerms, candidates, changeCandidates, health, connectionError, refreshHealth, report, detectorReport, imported, consent, setConsent, busy, error: tooLong ? t.limit : error, tooLong, rewrite, detect, importSource, importDetector, cancel };
}
export type Workbench = ReturnType<typeof useWorkbench>;
