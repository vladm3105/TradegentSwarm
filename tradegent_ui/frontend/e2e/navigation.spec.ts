import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  // Log in before each test
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: /demo trader/i }).click();
    await expect(page).toHaveURL('/');
  });

  test('sidebar contains all navigation links', async ({ page }) => {
    // Check for main navigation items in sidebar
    await expect(page.getByRole('link', { name: /dashboard/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /analysis/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /trades/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /watchlist/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /charts/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /scanner/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /settings/i })).toBeVisible();
  });

  test('navigates to analysis page', async ({ page }) => {
    await page.getByRole('link', { name: /analysis/i }).click();
    await expect(page).toHaveURL('/analysis');
    await expect(page.getByRole('heading', { name: /analysis/i })).toBeVisible();
  });

  test('navigates to trades page', async ({ page }) => {
    await page.getByRole('link', { name: /trades/i }).click();
    await expect(page).toHaveURL('/trades');
    await expect(page.getByRole('heading', { name: /trades|journal/i })).toBeVisible();
  });

  test('navigates to watchlist page', async ({ page }) => {
    await page.getByRole('link', { name: /watchlist/i }).click();
    await expect(page).toHaveURL('/watchlist');
    await expect(page.getByRole('heading', { name: /watchlist/i })).toBeVisible();
  });

  test('navigates to charts page', async ({ page }) => {
    await page.getByRole('link', { name: /charts/i }).click();
    await expect(page).toHaveURL('/charts');
    await expect(page.getByRole('heading', { name: /charts/i })).toBeVisible();
  });

  test('navigates to scanner page', async ({ page }) => {
    await page.getByRole('link', { name: /scanner/i }).click();
    await expect(page).toHaveURL('/scanner');
    await expect(page.getByRole('heading', { name: /scanner/i })).toBeVisible();
  });

  test('navigates to settings page', async ({ page }) => {
    await page.getByRole('link', { name: /settings/i }).click();
    await expect(page).toHaveURL('/settings');
    await expect(page.getByRole('heading', { name: /settings/i })).toBeVisible();
  });
});
