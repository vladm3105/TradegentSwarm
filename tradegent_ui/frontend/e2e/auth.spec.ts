import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('redirects unauthenticated users to login', async ({ page }) => {
    await page.goto('/');
    // Should redirect to login page
    await expect(page).toHaveURL(/\/login/);
  });

  test('shows login form', async ({ page }) => {
    await page.goto('/login');

    // Check for login form elements
    await expect(page.getByRole('heading', { name: /Welcome to Tradegent/i })).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
  });

  test('shows demo account buttons', async ({ page }) => {
    await page.goto('/login');

    await expect(page.getByRole('button', { name: /demo trader/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /admin user/i })).toBeVisible();
  });

  test('shows error for invalid credentials', async ({ page }) => {
    await page.goto('/login');

    await page.getByLabel(/email/i).fill('invalid@example.com');
    await page.getByLabel(/password/i).fill('wrongpassword');
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page.getByText(/invalid email or password/i)).toBeVisible();
  });

  test('logs in with demo trader credentials', async ({ page }) => {
    await page.goto('/login');

    await page.getByLabel(/email/i).fill('demo@tradegent.local');
    await page.getByLabel(/password/i).fill('demo123');
    await page.getByRole('button', { name: /sign in/i }).click();

    // Should redirect to dashboard
    await expect(page).toHaveURL('/');
    // Dashboard should have the title
    await expect(page.getByText(/Dashboard|Portfolio/i)).toBeVisible();
  });

  test('demo trader button logs in directly', async ({ page }) => {
    await page.goto('/login');

    await page.getByRole('button', { name: /demo trader/i }).click();

    // Should redirect to dashboard
    await expect(page).toHaveURL('/');
  });
});
