import { describe, expect, it } from 'vitest';
import { editionLocale } from '../src/i18n';

describe('edition defaults', () => {
  it('uses either edition and supports an explicit build override', () => {
    expect(editionLocale(undefined, 'zh')).toBe('zh');
    expect(editionLocale(undefined, 'en')).toBe('en');
    expect(editionLocale('zh', 'en')).toBe('zh');
    expect(editionLocale('en', 'zh')).toBe('en');
    expect(editionLocale('bad', 'en')).toBe('en');
    expect(editionLocale(undefined, 'bad')).toBe('zh');
  });
});
