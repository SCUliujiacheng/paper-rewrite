import type { Workbench } from '../useWorkbench';
import { Diff } from './Diff';
import { Issues } from './ContentChecks';

export function ManualReview({ work }: { work: Workbench }) {
  const { manualRevision, t } = work;
  if (!manualRevision) return null;
  return <>
    <section className="manual-review" aria-labelledby="manual-review-title">
      <h3 id="manual-review-title">{t.manualReviewTitle}</h3>
      <p className="muted">{t.manualReviewNote}</p>
      <Diff original={work.source} output={work.output} label={t.outputDiff} />
      {manualRevision.audit ? <Issues audit={manualRevision.audit} t={t} locale={work.locale} /> : <p className="needs-recheck" role="status">{t.needsRecheck}</p>}
    </section>
    <h3 className="generation-record-label">{t.originalGeneration}</h3>
  </>;
}
