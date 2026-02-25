-- ═══════════════════════════════════════════════════════════════════════════
-- Setup T-7/T-2/T+1 Earnings Schedules
-- Run this after adding stocks with earnings dates to automatically create
-- pre-earnings and post-earnings analysis schedules.
-- ═══════════════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════════════════
-- T-7: Pre-earnings analysis (7 days before)
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO nexus.schedules (
    name,
    description,
    task_type,
    target_ticker,
    analysis_type,
    frequency,
    days_before_earnings,
    priority,
    is_enabled
)
SELECT
    ticker || '_T7',
    'Pre-earnings analysis 7 days before ' || ticker || ' earnings',
    'analyze_stock',
    ticker,
    'earnings',
    'pre_earnings',
    7,
    8,
    true
FROM nexus.stocks
WHERE next_earnings_date IS NOT NULL
  AND is_enabled = true
ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════
-- T-2: Pre-earnings update (2 days before)
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO nexus.schedules (
    name, description, task_type, target_ticker, analysis_type,
    frequency, days_before_earnings, priority, is_enabled
)
SELECT
    ticker || '_T2',
    'Pre-earnings update 2 days before ' || ticker || ' earnings',
    'analyze_stock',
    ticker,
    'earnings',
    'pre_earnings',
    2,
    9,
    true
FROM nexus.stocks
WHERE next_earnings_date IS NOT NULL
  AND is_enabled = true
ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════
-- T+1: Post-earnings review (1 day after)
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO nexus.schedules (
    name, description, task_type, target_ticker, analysis_type,
    frequency, days_after_earnings, priority, is_enabled
)
SELECT
    ticker || '_T1_POST',
    'Post-earnings review 1 day after ' || ticker || ' earnings',
    'postmortem',
    ticker,
    'earnings',
    'post_earnings',
    1,
    7,
    true
FROM nexus.stocks
WHERE next_earnings_date IS NOT NULL
  AND is_enabled = true
ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════
-- Show created schedules
-- ═══════════════════════════════════════════════════════════════════════════
SELECT
    name,
    target_ticker,
    frequency,
    COALESCE(days_before_earnings::text, '') ||
    COALESCE(days_after_earnings::text, '') AS days,
    priority
FROM nexus.schedules
WHERE frequency IN ('pre_earnings', 'post_earnings')
ORDER BY target_ticker, name;
