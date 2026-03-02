import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  // Log in before each test
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: /demo trader/i }).click();
    await expect(page).toHaveURL('/');
  });

  test('displays dashboard header', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible();
  });

  test('displays portfolio stats cards', async ({ page }) => {
    // Check for stat cards
    await expect(page.getByText(/total p&l|total pnl/i)).toBeVisible();
    await expect(page.getByText(/open positions/i)).toBeVisible();
    await expect(page.getByText(/win rate/i)).toBeVisible();
  });

  test('header contains search input', async ({ page }) => {
    await expect(page.getByPlaceholder(/search ticker/i)).toBeVisible();
  });

  test('header contains theme toggle', async ({ page }) => {
    // Theme toggle button should be visible
    const themeButton = page.locator('button').filter({ has: page.locator('svg') }).nth(-2);
    await expect(themeButton).toBeVisible();
  });

  test('user menu shows user info', async ({ page }) => {
    // User name should be visible in header
    await expect(page.getByText(/demo trader/i)).toBeVisible();
  });
});
