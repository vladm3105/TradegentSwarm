import { describe, it, expect } from 'vitest';
import { cn, formatCurrency, formatPercent, formatCompact, generateId } from '@/lib/utils';

describe('cn (className merger)', () => {
  it('merges class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('handles conditional classes', () => {
    expect(cn('foo', false && 'bar', 'baz')).toBe('foo baz');
    expect(cn('foo', true && 'bar', 'baz')).toBe('foo bar baz');
  });

  it('handles undefined and null', () => {
    expect(cn('foo', undefined, null, 'bar')).toBe('foo bar');
  });

  it('deduplicates tailwind classes', () => {
    expect(cn('p-4 m-2', 'p-6')).toBe('m-2 p-6');
  });
});

describe('formatCurrency', () => {
  it('formats positive numbers with dollar sign', () => {
    expect(formatCurrency(1234.56)).toBe('$1,234.56');
  });

  it('formats negative numbers', () => {
    expect(formatCurrency(-1234.56)).toBe('-$1,234.56');
  });

  it('formats zero', () => {
    expect(formatCurrency(0)).toBe('$0.00');
  });

  it('handles large numbers', () => {
    expect(formatCurrency(1234567.89)).toBe('$1,234,567.89');
  });
});

describe('formatPercent', () => {
  it('formats positive percentages', () => {
    expect(formatPercent(12.34)).toBe('+12.34%');
  });

  it('formats negative percentages', () => {
    expect(formatPercent(-5.67)).toBe('-5.67%');
  });

  it('formats zero', () => {
    expect(formatPercent(0)).toBe('0.00%');
  });
});

describe('formatCompact', () => {
  it('formats thousands with K suffix', () => {
    expect(formatCompact(1500)).toBe('1.5K');
  });

  it('formats millions with M suffix', () => {
    expect(formatCompact(1500000)).toBe('1.5M');
  });

  it('formats billions with B suffix', () => {
    expect(formatCompact(1500000000)).toBe('1.5B');
  });

  it('returns plain number for small values', () => {
    expect(formatCompact(500)).toBe('500');
  });
});

describe('generateId', () => {
  it('generates unique IDs', () => {
    const id1 = generateId();
    const id2 = generateId();
    expect(id1).not.toBe(id2);
  });

  it('generates string IDs', () => {
    const id = generateId();
    expect(typeof id).toBe('string');
    expect(id.length).toBeGreaterThan(0);
  });
});
