import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import App from '../src/App';

const generated = { source: '实验重复5次。', output: '本实验进行了5次。', status: 'completed', warnings: [], model: 'local-test', elapsed_seconds: 0.1, requires_review: true, detector_status: 'not_run', source_sha256: 'original-source', output_sha256: 'generated-output', segments: [{ id: 0, original: '实验重复5次。', output: '本实验进行了5次。', status: 'rewritten', audit: { blocked: false, issues: [], requires_review: true }, attempts: [] }] };
const cleanAudit = { blocked: false, issues: [], requires_review: true };
const riskAudit = { blocked: true, issues: [{ code: 'numbers', severity: 'error', before: '5次', after: '6次' }], requires_review: true };
const detector = { detector: 'GPTZero', status: 'completed', before: { raw: 1 }, after: { raw: 2 }, measured_at: '2026-10-14T00:00:00Z', source_sha256: 'original-source', output_sha256: 'current-output', model_version: 'v2' };
let calls: { url: string; body: Record<string, unknown>; signal?: AbortSignal | null }[];
let auditResponse: unknown;
let pendingCheck: ((response: Response) => void) | null;
let delayCheck: boolean;
let pendingDetector: ((response: Response) => void) | null;
let delayDetector: boolean;
let checkStatus: number;
beforeEach(() => {
  calls = []; auditResponse = cleanAudit; pendingCheck = null; delayCheck = false; pendingDetector = null; delayDetector = false; checkStatus = 200;
  vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    calls.push({ url, body, signal: init?.signal });
    if (url === '/api/check' && delayCheck) return new Promise<Response>(resolve => { pendingCheck = resolve; });
    if (url === '/api/detect' && delayDetector) return new Promise<Response>(resolve => { pendingDetector = resolve; });
    const data = url === '/api/health' ? { model_ready: true, detector_configured: true, model: 'local-test', version: '0.1.0', default_language: 'zh' } : url === '/api/rewrite' ? generated : url === '/api/check' ? auditResponse : detector;
    return new Response(JSON.stringify(data), { status: url === '/api/check' ? checkStatus : 200, headers: { 'Content-Type': 'application/json' } });
  });
});
async function generate() {
  render(<App />);
  fireEvent.change(screen.getByLabelText('保留原样的术语（每行一个）'), { target: { value: '实验' } });
  fireEvent.change(screen.getByLabelText('原文'), { target: { value: generated.source } });
  await userEvent.click(screen.getByRole('button', { name: '开始改写' }));
  await waitFor(() => expect(screen.getByLabelText('改写稿')).toHaveValue(generated.output));
}
function edit(value: string) { fireEvent.change(screen.getByLabelText('改写稿'), { target: { value } }); }
const read = (blob: Blob) => new Promise<string>(resolve => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(blob); });

it('enables output editing after generation and labels the new draft as needing recheck', async () => {
  await generate();
  expect(screen.getByLabelText('改写稿')).not.toHaveAttribute('readonly');
  edit('用户修改后重复6次。');
  expect(screen.getByText('已由用户修改')).toBeInTheDocument();
  const manual = within(screen.getByRole('region', { name: '人工修订核对' }));
  expect(manual.getByText('文本已修改，请重新核对。')).toBeInTheDocument();
  expect(manual.queryByText(/规则检查未发现问题/)).not.toBeInTheDocument();
  expect(screen.getByText('原始生成记录（不适用于人工修订稿）')).toBeInTheDocument();
});

it('rechecks the edited text with current protected terms and displays the returned risks', async () => {
  auditResponse = riskAudit; await generate(); edit('用户修改后重复6次。');
  await userEvent.click(screen.getByRole('button', { name: '重新核对' }));
  const manual = within(screen.getByRole('region', { name: '人工修订核对' }));
  expect(await manual.findByText('数字或单位发生变化')).toBeInTheDocument();
  expect(calls.find(call => call.url === '/api/check')?.body).toEqual({ source: generated.source, candidate: '用户修改后重复6次。', protected_terms: ['实验'] });
  expect(manual.queryByText('文本已修改，请重新核对。')).not.toBeInTheDocument();
});

it('invalidates the manual audit after another output edit', async () => {
  await generate(); edit('实验又重复5次。');
  await userEvent.click(screen.getByRole('button', { name: '重新核对' }));
  const manual = within(screen.getByRole('region', { name: '人工修订核对' }));
  expect(await manual.findByText(/规则检查未发现问题/)).toBeInTheDocument();
  edit('实验重复6次。');
  expect(manual.getByText('文本已修改，请重新核对。')).toBeInTheDocument();
  expect(manual.queryByText(/规则检查未发现问题/)).not.toBeInTheDocument();
});

it('ignores a late manual audit response for an earlier edit', async () => {
  delayCheck = true; await generate(); edit('实验重复6次。');
  await userEvent.click(screen.getByRole('button', { name: '重新核对' }));
  edit('新的修改重复7次。');
  await act(async () => { pendingCheck?.(new Response(JSON.stringify(riskAudit))); });
  const manual = within(screen.getByRole('region', { name: '人工修订核对' }));
  expect(manual.getByText('文本已修改，请重新核对。')).toBeInTheDocument();
  expect(manual.queryByText('数字或单位发生变化')).not.toBeInTheDocument();
  expect(calls.find(call => call.url === '/api/check')?.signal?.aborted).toBe(true);
});

it('resets detector evidence and consent on edits and detects the current edited output', async () => {
  await generate();
  await userEvent.click(screen.getByRole('tab', { name: '检测结果' }));
  await userEvent.click(screen.getByRole('checkbox'));
  await userEvent.click(screen.getByRole('button', { name: '运行外部检测' }));
  await screen.findByText('GPTZero');
  edit('人工修订5次。');
  expect(screen.queryByText('GPTZero')).not.toBeInTheDocument();
  expect(screen.getByText('未检测')).toBeInTheDocument();
  expect(screen.getByRole('checkbox')).not.toBeChecked();
  await userEvent.click(screen.getByRole('checkbox'));
  await userEvent.click(screen.getByRole('button', { name: '运行外部检测' }));
  await screen.findByText('GPTZero');
  expect(calls.filter(call => call.url === '/api/detect').at(-1)?.body).toEqual({ source: generated.source, candidate: '人工修订5次。', consent: true });
});

it('ignores late detector results after an output edit', async () => {
  delayDetector = true; await generate();
  await userEvent.click(screen.getByRole('tab', { name: '检测结果' }));
  await userEvent.click(screen.getByRole('checkbox'));
  await userEvent.click(screen.getByRole('button', { name: '运行外部检测' }));
  edit('人工修订5次。');
  await act(async () => { pendingDetector?.(new Response(JSON.stringify(detector))); });
  expect(screen.queryByText('GPTZero')).not.toBeInTheDocument();
  expect(screen.getByRole('checkbox')).not.toBeChecked();
  expect(calls.find(call => call.url === '/api/detect')?.signal?.aborted).toBe(true);
});

it('validates an imported detector report against the edited output', async () => {
  await generate(); edit('人工修订5次。');
  await userEvent.click(screen.getByRole('tab', { name: '检测结果' }));
  fireEvent.change(screen.getByLabelText('导入检测报告文件'), { target: { files: [new File([JSON.stringify(detector)], 'report.json')] } });
  await screen.findByText('用户导入的报告');
  expect(calls.find(call => call.url === '/api/detector-report')?.body.candidate).toBe('人工修订5次。');
});

it('exports current manual text and preserves the untouched generated report in JSON', async () => {
  const blobs: Blob[] = [];
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: (blob: Blob) => { blobs.push(blob); return 'blob:manual'; }, revokeObjectURL: () => {} }));
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  await generate(); edit('人工修订5次。');
  await userEvent.click(screen.getByRole('button', { name: '导出 TXT' }));
  await userEvent.click(screen.getByRole('button', { name: '导出 JSON' }));
  expect(await read(blobs[0])).toBe('人工修订5次。');
  const exported = JSON.parse(await read(blobs[1]));
  expect(exported.output).toBe('本实验进行了5次。');
  expect(exported.output_sha256).toBe('generated-output');
  expect(exported.segments).toEqual(generated.segments);
  expect(exported.manual_revision).toEqual({ output: '人工修订5次。', status: 'needs_recheck', audit: null });
  await userEvent.click(screen.getByRole('button', { name: '重新核对' }));
  await waitFor(() => expect(screen.getByRole('region', { name: '人工修订核对' })).toHaveTextContent('规则检查未发现问题'));
  await userEvent.click(screen.getByRole('button', { name: '导出 JSON' }));
  expect(JSON.parse(await read(blobs[2])).manual_revision).toEqual({ output: '人工修订5次。', status: 'checked', audit: cleanAudit });
});

it('clears manual draft and check when source or protected terms change', async () => {
  await generate(); edit('人工修订5次。');
  fireEvent.change(screen.getByLabelText('保留原样的术语（每行一个）'), { target: { value: 'new term' } });
  expect(screen.getByLabelText('改写稿')).toHaveValue('');
  expect(screen.queryByRole('region', { name: '人工修订核对' })).not.toBeInTheDocument();
});

it('rejects manual edits beyond 12000 characters and disables actions for blank output', async () => {
  await generate(); edit('字'.repeat(12001));
  expect(screen.getByLabelText('改写稿')).toHaveValue(generated.output);
  expect(screen.getByRole('alert')).toHaveTextContent('12000');
  edit('');
  expect(screen.getByRole('button', { name: '重新核对' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '导出 TXT' })).toBeDisabled();
  await userEvent.click(screen.getByRole('tab', { name: '检测结果' }));
  await userEvent.click(screen.getByRole('checkbox'));
  expect(screen.getByRole('button', { name: '运行外部检测' })).toBeDisabled();
});

it('presents manual review in English and keeps failed checks pending recheck', async () => {
  checkStatus = 503; auditResponse = { detail: 'check_unavailable' };
  await generate(); edit('User edit.');
  await userEvent.click(screen.getByRole('button', { name: 'English' }));
  expect(screen.getByText('Edited by user')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Recheck' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('check_unavailable');
  expect(screen.getByRole('region', { name: 'Manual revision checks' })).toHaveTextContent('Text changed. Recheck this revision.');
});

it('opens content checks when rechecking from the detector tab', async () => {
  await generate(); edit('人工修订5次。');
  await userEvent.click(screen.getByRole('tab', { name: '检测结果' }));
  await userEvent.click(screen.getByRole('button', { name: '重新核对' }));
  expect(await screen.findByRole('region', { name: '人工修订核对' })).toHaveTextContent('规则检查未发现问题');
  expect(screen.getByRole('tab', { name: '内容检查' })).toHaveAttribute('aria-selected', 'true');
});
