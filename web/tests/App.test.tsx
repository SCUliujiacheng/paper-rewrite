import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';

const health = { model_ready: true, model: 'local-test', detector_configured: true, version: '0.1.0', default_language: 'zh' };
const rewrite = { source: '原文 5 次。', output: '重复了 5 次。', segments: [{ id: 0, original: '原文 5 次。', output: '重复了 5 次。', status: 'rewritten', audit: { blocked: false, issues: [], requires_review: true }, attempts: [] }], warnings: [], model: 'local-test', elapsed_seconds: 0.2, requires_review: true, detector_status: 'not_run', source_sha256: 'abc', output_sha256: 'def', status: 'completed' };
const detector = { detector: 'GPTZero', status: 'completed', measured_at: '2026-10-14T00:00:00Z', model_version: 'v2', source_sha256: 'abc', output_sha256: 'def', before: { score: 0.5 }, after: { score: 0.2 } };
let calls: { url: string; body: Record<string, unknown>; signal?: AbortSignal | null }[];
let rewriteResponse: unknown;
let rewriteStatus: number;
let pending: boolean;
let detectorResponse: unknown;
beforeEach(() => {
  calls = []; rewriteResponse = rewrite; rewriteStatus = 200; pending = false; detectorResponse = detector;
  vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    calls.push({ url, body, signal: init?.signal });
    if (url === '/api/rewrite' && pending) return new Promise<Response>((_resolve, reject) => init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))));
    if (url === '/api/detector-report' && (!body.report || body.report.detector !== 'GPTZero')) return new Response(JSON.stringify({ detail: 'invalid_or_mismatched_detector_report' }), { status: 422 });
    const data = url === '/api/health' ? health : url === '/api/rewrite' ? rewriteResponse : detectorResponse;
    return new Response(JSON.stringify(data), { status: url === '/api/rewrite' ? rewriteStatus : 200, headers: { 'Content-Type': 'application/json' } });
  });
});
async function generate() {
  fireEvent.change(screen.getByLabelText('原文'), { target: { value: '原文 5 次。' } });
  await userEvent.click(screen.getByRole('button', { name: '开始改写' }));
  await waitFor(() => expect(screen.getByLabelText('改写稿')).toHaveValue('重复了 5 次。'));
}
async function detect() {
  await userEvent.click(screen.getByRole('tab', { name: '检测结果' }));
  await userEvent.click(screen.getByRole('checkbox'));
  await userEvent.click(screen.getByRole('button', { name: '运行外部检测' }));
  await screen.findByText('GPTZero');
}

describe('workbench behavior', () => {
  it('prevents blank generation and represents detector as not run', async () => {
    render(<App />);
    expect(screen.getByRole('button', { name: '开始改写' })).toBeDisabled();
    await userEvent.click(screen.getByRole('tab', { name: '检测结果' }));
    expect(screen.getByText('未检测')).toBeInTheDocument();
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
  });
  it('sends language, candidates and protected terms while displaying a reviewable output', async () => {
    render(<App />);
    fireEvent.change(screen.getByLabelText('保留原样的术语（每行一个）'), { target: { value: 'BM25\n DOI \n' } });
    fireEvent.change(screen.getByLabelText('候选数'), { target: { value: '3' } });
    fireEvent.change(screen.getByLabelText('文本语言'), { target: { value: 'en' } });
    await generate();
    expect(calls.find(call => call.url === '/api/rewrite')?.body).toEqual({ text: '原文 5 次。', language: 'en', candidates: 3, protected_terms: ['BM25', 'DOI'] });
    expect(screen.getByLabelText('改写稿')).not.toHaveAttribute('readonly');
    expect(screen.getByText('已改写')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '导出 TXT' })).toBeEnabled();
  });
  it('renders hostile generated text literally, never as DOM', async () => {
    rewriteResponse = { ...rewrite, output: '<img src=x onerror=alert(1)>', segments: [{ ...rewrite.segments[0], output: '<script>alert(1)</script>' }] };
    render(<App />);
    fireEvent.change(screen.getByLabelText('原文'), { target: { value: '原文 5 次。' } });
    await userEvent.click(screen.getByRole('button', { name: '开始改写' }));
    await waitFor(() => expect(screen.getByLabelText('改写稿')).toHaveValue('<img src=x onerror=alert(1)>'));
    expect(document.querySelector('img')).toBeNull();
    expect(document.querySelector('script')).toBeNull();
  });
  it('requires explicit consent and never automatically runs an external detector', async () => {
    render(<App />); await generate();
    expect(calls.some(call => call.url === '/api/detect')).toBe(false);
    await userEvent.click(screen.getByRole('tab', { name: '检测结果' }));
    expect(screen.getByRole('button', { name: '运行外部检测' })).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(screen.getByRole('button', { name: '运行外部检测' }));
    await screen.findByText('GPTZero');
    expect(calls.find(call => call.url === '/api/detect')?.body).toEqual({ source: '原文 5 次。', candidate: '重复了 5 次。', consent: true });
    expect(screen.getByText('{ "score": 0.2 }', { exact: true })).toBeInTheDocument();
    expect(screen.queryByText('20%')).not.toBeInTheDocument();
  });
  it('invalidates output and detector state immediately when source changes', async () => {
    render(<App />); await generate(); await detect();
    fireEvent.change(screen.getByLabelText('原文'), { target: { value: '新的原文' } });
    expect(screen.getByLabelText('改写稿')).toHaveValue('');
    expect(screen.queryByText('GPTZero')).not.toBeInTheDocument();
    expect(screen.getByText('未检测')).toBeInTheDocument();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
  });
  it('imports UTF-8 source and resets previous results', async () => {
    render(<App />); await generate();
    const file = new File(['导入的中文稿件。'], '稿件.md', { type: 'text/markdown' });
    fireEvent.change(screen.getByLabelText('导入文本文件'), { target: { files: [file] } });
    await waitFor(() => expect(screen.getByLabelText('原文')).toHaveValue('导入的中文稿件。'));
    expect(screen.getByLabelText('改写稿')).toHaveValue('');
  });
  it('rejects oversized text without generating', async () => {
    render(<App />);
    fireEvent.change(screen.getByLabelText('原文'), { target: { value: '字'.repeat(12001) } });
    expect(screen.getByRole('button', { name: '开始改写' })).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent('12000');
  });
  it('shows service errors without fabricated output', async () => {
    rewriteResponse = { detail: 'Local model unavailable' }; rewriteStatus = 503;
    render(<App />);
    fireEvent.change(screen.getByLabelText('原文'), { target: { value: '原文' } });
    await userEvent.click(screen.getByRole('button', { name: '开始改写' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Local model unavailable');
    expect(screen.getByLabelText('改写稿')).toHaveValue('');
  });
  it('cancels a running request through AbortController', async () => {
    pending = true; render(<App />);
    fireEvent.change(screen.getByLabelText('原文'), { target: { value: '原文' } });
    await userEvent.click(screen.getByRole('button', { name: '开始改写' }));
    await userEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(calls.find(call => call.url === '/api/rewrite')?.signal?.aborted).toBe(true);
    expect(screen.getByRole('button', { name: '开始改写' })).toBeEnabled();
    expect(screen.getByLabelText('改写稿')).toHaveValue('');
  });
  it('toggles UI language independently from document language', async () => {
    render(<App />);
    fireEvent.change(screen.getByLabelText('原文'), { target: { value: '保留内容' } });
    await userEvent.click(screen.getByRole('button', { name: 'English' }));
    expect(screen.getByRole('heading', { name: 'Rewrite & review' })).toBeInTheDocument();
    expect(screen.getByLabelText('Source')).toHaveValue('保留内容');
    expect(screen.getByLabelText('Text language')).toHaveValue('zh');
    expect(document.documentElement.lang).toBe('en');
  });
  it('shows retained output, audit issues and candidate diagnostics honestly', async () => {
    rewriteResponse = { ...rewrite, output: rewrite.source, status: 'unchanged', warnings: ['Review numeric relation'], segments: [{ ...rewrite.segments[0], output: rewrite.source, status: 'retained', audit: { blocked: true, issues: [{ code: 'number_changed', severity: 'error', before: '5', after: '6' }], requires_review: true }, attempts: [{ text: '重复了 6 次。', audit: { blocked: true, issues: [], requires_review: true } }] }] };
    render(<App />);
    fireEvent.change(screen.getByLabelText('原文'), { target: { value: rewrite.source } });
    await userEvent.click(screen.getByRole('button', { name: '开始改写' }));
    expect(await screen.findByText('保留原文')).toBeInTheDocument();
    expect(screen.getByText('number_changed')).toBeInTheDocument();
    expect(screen.getByText('Review numeric relation')).toBeInTheDocument();
    expect(screen.getByText('候选记录')).toBeInTheDocument();
  });
  it('imports detector JSON through the hash-checking endpoint and labels user origin', async () => {
    render(<App />); await generate();
    await userEvent.click(screen.getByRole('tab', { name: '检测结果' }));
    const file = new File([JSON.stringify(detector)], 'report.json', { type: 'application/json' });
    fireEvent.change(screen.getByLabelText('导入检测报告文件'), { target: { files: [file] } });
    expect(await screen.findByText('用户导入的报告')).toBeInTheDocument();
    expect(calls.find(call => call.url === '/api/detector-report')?.body).toEqual({ source: rewrite.source, candidate: rewrite.output, report: detector });
  });
  it('clears both editors and disables export', async () => {
    render(<App />); await generate();
    await userEvent.click(screen.getByRole('button', { name: '清空' }));
    expect(screen.getByLabelText('原文')).toHaveValue('');
    expect(screen.getByLabelText('改写稿')).toHaveValue('');
    expect(screen.queryByRole('button', { name: '导出 TXT' })).not.toBeInTheDocument();
  });
  it('exports the actual draft and review metadata as text and JSON artifacts', async () => {
    const blobs: Blob[] = [];
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: (blob: Blob) => { blobs.push(blob); return 'blob:review-test'; }, revokeObjectURL: () => {} }));
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    render(<App />); await generate();
    await userEvent.click(screen.getByRole('button', { name: '导出 TXT' }));
    await userEvent.click(screen.getByRole('button', { name: '导出 JSON' }));
    const read = (blob: Blob) => new Promise<string>(resolve => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob); });
    expect(await read(blobs[0])).toBe('重复了 5 次。');
    const exported = JSON.parse(await read(blobs[1]));
    expect(exported.output).toBe('重复了 5 次。');
    expect(exported.requires_review).toBe(true);
    expect(exported.detector_report_origin).toBe('not_run');
    expect(exported.source_sha256).toBe('abc');
  });
  it('rejects unsupported imported source and removes the old result', async () => {
    render(<App />); await generate();
    fireEvent.change(screen.getByLabelText('导入文本文件'), { target: { files: [new File(['wrong file'], 'document.pdf')] } });
    expect(await screen.findByRole('alert')).toHaveTextContent('.txt');
    expect(screen.getByLabelText('改写稿')).toHaveValue('');
  });
  it('rejects malformed imported detector reports', async () => {
    render(<App />); await generate();
    await userEvent.click(screen.getByRole('tab', { name: '检测结果' }));
    fireEvent.change(screen.getByLabelText('导入检测报告文件'), { target: { files: [new File(['[]'], 'report.json')] } });
    expect(await screen.findByRole('alert')).toHaveTextContent('JSON');
    expect(screen.getByText('未检测')).toBeInTheDocument();
    expect(calls.some(call => call.url === '/api/detector-report')).toBe(false);
  });
  it('aborts in-flight generation when imported source replaces the current text', async () => {
    pending = true; render(<App />);
    fireEvent.change(screen.getByLabelText('原文'), { target: { value: '旧的原文' } });
    await userEvent.click(screen.getByRole('button', { name: '开始改写' }));
    fireEvent.change(screen.getByLabelText('导入文本文件'), { target: { files: [new File(['新的导入文本'], 'draft.txt')] } });
    await waitFor(() => expect(screen.getByLabelText('原文')).toHaveValue('新的导入文本'));
    expect(calls.find(call => call.url === '/api/rewrite')?.signal?.aborted).toBe(true);
    expect(screen.getByLabelText('改写稿')).toHaveValue('');
  });
  it('preserves a failed paragraph when a model error has no candidate audit', async () => {
    rewriteResponse = { ...rewrite, status: 'failed', output: rewrite.source, segments: [{ ...rewrite.segments[0], status: 'failed', output: rewrite.source, attempts: [{ text: '', audit: null, error: 'model_unavailable' }] }] };
    render(<App />);
    fireEvent.change(screen.getByLabelText('原文'), { target: { value: rewrite.source } });
    await userEvent.click(screen.getByRole('button', { name: '开始改写' }));
    expect(await screen.findByText('改写失败')).toBeInTheDocument();
    expect(screen.getByLabelText('改写稿')).toHaveValue('原文 5 次。');
    await userEvent.click(screen.getByText('候选记录'));
    expect(screen.getByText('model_unavailable')).toBeInTheDocument();
  });
  it('shows a detector failure without presenting empty measurements as results', async () => {
    detectorResponse = { ...detector, status: 'error', error: 'rate_limited', before: null, after: null };
    render(<App />); await generate(); await detect();
    expect(screen.getByRole('alert')).toHaveTextContent('rate_limited');
    expect(screen.queryByRole('heading', { name: '改写前' })).not.toBeInTheDocument();
  });
  it('round-trips its exported full report through detector hash validation as user supplied', async () => {
    const blobs: Blob[] = [];
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: (blob: Blob) => { blobs.push(blob); return 'blob:round-trip'; }, revokeObjectURL: () => {} }));
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    render(<App />); await generate(); await detect();
    await userEvent.click(screen.getByRole('button', { name: '导出 JSON' }));
    const exported = await new Promise<string>(resolve => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blobs[0]); });
    expect(JSON.parse(exported).detector_report_origin).toBe('external_api');
    fireEvent.change(screen.getByLabelText('导入检测报告文件'), { target: { files: [new File([exported], 'rewrite-report.json')] } });
    expect(await screen.findByText('用户导入的报告')).toBeInTheDocument();
    expect(calls.find(call => call.url === '/api/detector-report')?.body).toEqual({ source: rewrite.source, candidate: rewrite.output, report: detector });
  });
  it.each([['missing', undefined], ['null', null], ['array', []], ['string', 'not a report']])('rejects a full report wrapper with %s embedded detector data', async (_name, value) => {
    render(<App />); await generate();
    await userEvent.click(screen.getByRole('tab', { name: '检测结果' }));
    const wrapper = { ...rewrite, detector_report: value, detector_report_origin: 'external_api' };
    fireEvent.change(screen.getByLabelText('导入检测报告文件'), { target: { files: [new File([JSON.stringify(wrapper)], 'rewrite-report.json')] } });
    expect(await screen.findByRole('alert')).toHaveTextContent('JSON');
    expect(calls.some(call => call.url === '/api/detector-report')).toBe(false);
  });
  it('keeps a visible fictional notice beside the example workflow without generating results', async () => {
    render(<App />);
    expect(screen.getByRole('note')).toHaveTextContent('示例为虚构文本，不代表真实研究结果。');
    await userEvent.click(screen.getByRole('button', { name: '载入示例' }));
    expect((screen.getByLabelText('原文') as HTMLTextAreaElement).value).toContain('82.4%');
    expect(screen.getByRole('note')).toHaveTextContent('示例为虚构文本，不代表真实研究结果。');
    expect(screen.getByLabelText('改写稿')).toHaveValue('');
    expect(calls.some(call => call.url === '/api/rewrite' || call.url === '/api/detect')).toBe(false);
    await userEvent.click(screen.getByRole('button', { name: '清空' }));
    expect(screen.getByRole('note')).toHaveTextContent('示例为虚构文本，不代表真实研究结果。');
  });
  it('shows the fictional example notice in English', async () => {
    render(<App />);
    await userEvent.click(screen.getByRole('button', { name: 'English' }));
    expect(screen.getByRole('note')).toHaveTextContent('The example is fictional and does not represent real research findings.');
    expect(screen.queryByText('示例为虚构文本，不代表真实研究结果。')).not.toBeInTheDocument();
  });
});
