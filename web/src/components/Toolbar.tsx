import { useRef } from 'react';
import { examples } from '../i18n';
import type { Language } from '../types';
import type { Workbench } from '../useWorkbench';
import { Icon } from './Icon';

export function Toolbar({ work }: { work: Workbench }) {
  const file = useRef<HTMLInputElement>(null); const { t } = work;
  return <div className="toolbar">
    <div className="toolbar-group">
      <button onClick={() => file.current?.click()}><Icon name="file" />{t.importText}</button>
      <input ref={file} className="visually-hidden" type="file" accept=".txt,.md,text/plain,text/markdown" aria-label={t.importTextFile} onChange={event => { void work.importSource(event.target.files?.[0]); event.target.value = ''; }} />
      <button onClick={() => work.changeSource(examples[work.language])}><Icon name="folder" />{t.example}</button>
      <button onClick={() => work.changeSource('')}><Icon name="trash" />{t.clear}</button>
    </div>
    <div className="toolbar-group selectors">
      <select aria-label={t.textLanguage} value={work.language} onChange={event => work.changeLanguage(event.target.value as Language)}><option value="zh">中文</option><option value="en">English</option></select>
      <select aria-label={t.candidates} value={work.candidates} onChange={event => work.changeCandidates(Number(event.target.value))}>{[1, 2, 3].map(count => <option key={count} value={count}>{t.candidates} {count}</option>)}</select>
    </div>
  </div>;
}
