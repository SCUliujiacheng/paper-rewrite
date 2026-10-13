import { useState } from 'react';
import { ContentChecks } from './components/ContentChecks';
import { DetectorPanel } from './components/DetectorPanel';
import { Editors } from './components/Editors';
import { ManualReview } from './components/ManualReview';
import { Toolbar } from './components/Toolbar';
import { useWorkbench } from './useWorkbench';
import './styles/tokens.css';
import './styles/workbench.css';
import './styles/review.css';

export default function App() {
  const work = useWorkbench(); const { t } = work;
  const [tab, setTab] = useState<'contents' | 'detector'>('contents');
  return <>
    <header className="app-header"><div className="header-inner"><span className="brand">{t.brand}</span><div className="header-tools"><div className="locale-switch"><button className={work.locale === 'zh' ? 'selected' : ''} onClick={() => work.setLocale('zh')} aria-pressed={work.locale === 'zh'}>中文</button><span>/</span><button className={work.locale === 'en' ? 'selected' : ''} onClick={() => work.setLocale('en')} aria-pressed={work.locale === 'en'}>English</button></div><span className="connection" role="status">{t.localModel} · {work.health?.model_ready ? t.ready : work.connectionError || work.health ? t.disconnected : t.connecting}</span></div></div></header>
    <main className="workbench"><div className="intro"><h1>{t.title}</h1><p>{t.subtitle}</p></div>
      {(work.connectionError || work.health && !work.health.model_ready) && <div className="connection-warning" role="alert"><span>{t.modelUnavailable}</span><button onClick={() => void work.refreshHealth()}>{t.recheck}</button></div>}
      {work.error && <div className="error-banner" role="alert">{work.error}</div>}
      <Toolbar work={work} /><Editors work={work} onReview={() => setTab('contents')} />
      <section className="review-panel" aria-labelledby="review-title"><h2 id="review-title">{t.reviewTitle}</h2><div className="review-tabs" role="tablist" aria-label={t.reviewTitle}><button id="contents-tab" role="tab" aria-selected={tab === 'contents'} aria-controls="contents-panel" tabIndex={tab === 'contents' ? 0 : -1} onClick={() => setTab('contents')} onKeyDown={event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { setTab('detector'); document.getElementById('detector-tab')?.focus(); } }}>{t.contents}</button><button id="detector-tab" role="tab" aria-selected={tab === 'detector'} aria-controls="detector-panel" tabIndex={tab === 'detector' ? 0 : -1} onClick={() => setTab('detector')} onKeyDown={event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { setTab('contents'); document.getElementById('contents-tab')?.focus(); } }}>{t.detector}</button></div>
        <div id={`${tab}-panel`} role="tabpanel" aria-labelledby={`${tab}-tab`}>{tab === 'contents' ? <><ManualReview work={work} /><ContentChecks report={work.report} t={t} locale={work.locale} /></> : <DetectorPanel work={work} />}</div>
      </section>
      <footer className="page-footer"><span id="limits">{t.paragraphLimit}</span><span>{t.reviewNotice}</span></footer>
    </main>
  </>;
}
