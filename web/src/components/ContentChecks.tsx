import type { Copy } from '../i18n';
import { reportCopy } from '../report-copy';
import type { Audit, Language, RewriteReport } from '../types';
import { Diff } from './Diff';

function literal(value: unknown) { return typeof value === 'string' ? value : JSON.stringify(value); }
export function Issues({ audit, t, locale }: { audit: Audit; t: Copy; locale: Language }) {
  return audit.issues.length ? <ul className="issues">{audit.issues.map((issue, index) => <li key={index}><strong>{reportCopy(locale, 'issues', issue.code)}</strong><span className="severity">{reportCopy(locale, 'severity', issue.severity)}</span><div><span>{literal(issue.before)}</span><span aria-hidden="true"> → </span><span>{literal(issue.after)}</span></div></li>)}</ul> : <p className="muted audit-note">{t.noIssues}</p>;
}

export function ContentChecks({ report, t, locale }: { report: RewriteReport | null; t: Copy; locale: Language }) {
  if (!report) return <p className="empty-state">{t.emptyAudit}</p>;
  const status = report.status === 'completed' ? t.completed : report.status === 'partial' ? t.partial : report.status === 'unchanged' ? t.unchanged : t.reportFailed;
  return <div className="content-checks">
    <div className="report-summary"><strong>{status}</strong><span>{report.model} · {t.elapsed} {report.elapsed_seconds.toFixed(1)} {t.seconds}</span></div>
    {report.warnings.length > 0 && <ul className="warnings">{report.warnings.map((warning, index) => <li key={index}>{reportCopy(locale, 'warnings', warning)}</li>)}</ul>}
    {report.segments.map((segment, index) => <article className="segment" key={segment.id}>
      <div className="segment-heading"><strong>{t.paragraph} {index + 1}</strong><span className={`segment-status ${segment.status}`}>{t[segment.status]}</span>{(segment.audit.blocked || segment.status === 'retained' && segment.audit.issues.length > 0) && <span className="risk-label">{segment.status === 'retained' ? reportCopy(locale, 'context', 'rejected_candidate') : t.blocked}</span>}</div>
      <Diff original={segment.original} output={segment.output} label={t.outputDiff} />
      <Issues audit={segment.audit} t={t} locale={locale} />
      {segment.attempts.length > 0 && <details><summary>{t.attempts}</summary>{segment.attempts.map((attempt, attemptIndex) => <div className="attempt" key={attemptIndex}><p>{attempt.text}</p>{attempt.error && <p className="error-text">{reportCopy(locale, 'errors', attempt.error)}</p>}{attempt.audit && <Issues audit={attempt.audit} t={t} locale={locale} />}</div>)}</details>}
    </article>)}
  </div>;
}
