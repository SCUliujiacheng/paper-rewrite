import { useRef } from 'react';
import type { Workbench } from '../useWorkbench';

export function DetectorPanel({ work }: { work: Workbench }) {
  const file = useRef<HTMLInputElement>(null); const { t, detectorReport: report } = work;
  return <div className="detector-panel">
    {!report && <p className="detector-status">{t.notRun}</p>}
    <p className="muted">{t.detectorNote}</p>
    {!work.health?.detector_configured && <p className="muted">{t.detectorUnavailable}</p>}
    <label className="consent"><input type="checkbox" checked={work.consent} disabled={!!work.busy} onChange={event => work.setConsent(event.target.checked)} /><span>{t.consent}</span></label>
    <div className="detector-actions">
      <button disabled={!work.report || !work.consent || !work.health?.detector_configured || !!work.busy} onClick={() => void work.detect()}>{t.runDetector}</button>
      <button disabled={!work.report || !!work.busy} onClick={() => file.current?.click()}>{t.importReport}</button>
      <input ref={file} className="visually-hidden" type="file" accept=".json,application/json" aria-label={t.importReportFile} onChange={event => { void work.importDetector(event.target.files?.[0]); event.target.value = ''; }} />
      {(work.busy === 'detector' || work.busy === 'import') && <><span role="status">{t.detecting}</span><button onClick={work.cancel}>{t.cancel}</button></>}
    </div>
    {report && <div className="detector-report">
      <div className="detector-report-heading"><strong>{report.detector}</strong><span>{report.status === 'completed' ? t.detectorCompleted : report.status === 'error' ? t.processError : report.status === 'not_configured' ? t.detectorUnavailable : t.notRun}</span>{work.imported && <span className="user-report">{t.importedReport}</span>}</div>
      {report.error && <p className="detector-error" role="alert">{t.processError}: {report.error}</p>}
      <dl><div><dt>{t.measuredAt}</dt><dd>{report.measured_at || '—'}</dd></div><div><dt>{t.detectorVersion}</dt><dd>{report.model_version || '—'}</dd></div></dl>
      {report.status === 'completed' && <div className="raw-scores"><div><h3>{t.before}</h3><pre>{JSON.stringify(report.before, null, 2)}</pre></div><div><h3>{t.after}</h3><pre>{JSON.stringify(report.after, null, 2)}</pre></div></div>}
      <details><summary>{t.rawReport}</summary><pre>{JSON.stringify(report, null, 2)}</pre></details>
    </div>}
  </div>;
}
