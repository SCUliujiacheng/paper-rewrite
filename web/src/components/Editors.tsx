import { download } from '../api';
import type { Workbench } from '../useWorkbench';

export function Editors({ work }: { work: Workbench }) {
  const { t, report } = work;
  function exportReport() { if (report) download(JSON.stringify({ ...report, detector_report: work.detectorReport, detector_report_origin: work.detectorReport ? work.imported ? 'user_supplied' : 'external_api' : 'not_run' }, null, 2), 'rewrite-report.json', 'application/json;charset=utf-8'); }
  return <>
    <div className="editors">
      <div className="editor-column">
        <label className="editor-label" htmlFor="source">{t.source}</label>
        <textarea id="source" className="draft-editor" value={work.source} placeholder={t.sourcePlaceholder} onChange={event => work.changeSource(event.target.value)} spellCheck={false} aria-describedby="limits" />
        <div className="source-meta"><span>{Array.from(work.source).length} / 12000 {t.chars}</span></div>
        <label className="terms-label" htmlFor="terms">{t.protectedTerms}</label>
        <textarea id="terms" className="terms-editor" value={work.terms} placeholder="BM25" onChange={event => work.changeTerms(event.target.value)} spellCheck={false} />
      </div>
      <div className="editor-column output-column">
        <label className="editor-label" htmlFor="output">{t.output}</label>
        <textarea id="output" className="draft-editor" value={report?.output ?? ''} placeholder={t.outputPlaceholder} readOnly spellCheck={false} />
        {report && <div className="export-row"><span>{t.downloadReview}</span><div><button onClick={() => download(report.output, 'rewrite.txt', 'text/plain;charset=utf-8')}>{t.exportTxt}</button><button onClick={exportReport}>{t.exportJson}</button></div></div>}
      </div>
    </div>
    <div className="action-row">
      {work.busy === 'rewrite' ? <><span role="status" className="working">{t.running}</span><button onClick={work.cancel}>{t.cancel}</button></> : <button className="primary" disabled={!work.source.trim() || work.tooLong || !!work.busy || !work.health?.model_ready} onClick={() => void work.rewrite()}>{t.rewrite}</button>}
      <span>{t.localOnly}</span>
    </div>
  </>;
}
