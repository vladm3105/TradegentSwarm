import { test, expect } from '@playwright/test';

test.describe('Chat Panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.removeItem('tradegent-chat-storage');
    });

    // Go to the app
    await page.goto('/');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Check if we need to login (redirected to /login)
    if (page.url().includes('/login')) {
      // If Auth0 is configured, click "Show email login" first
      const showEmailLogin = page.locator('button:has-text("Show email login")');
      if (await showEmailLogin.isVisible({ timeout: 2000 }).catch(() => false)) {
        await showEmailLogin.click();
      }

      // Fill the admin credentials (from .env.local)
      await page.fill('#email', 'admin@tradegent.local');
      await page.fill('#password', 'TradegentAdmin2024!');

      // Click Sign In button
      await page.click('button[type="submit"]:has-text("Sign In")');

      // Wait for login to complete (should leave /login)
      await expect(page).not.toHaveURL(/\/login/, { timeout: 15000 });
    }

    // Ensure we're on a page with the sidebar (logged in)
    await expect(page.locator('text=Dashboard').first()).toBeVisible({ timeout: 10000 });
  });

  test('should send message and receive response', async ({ page }) => {
    // Open the chat panel - click the chat button
    const chatButton = page.locator('button').filter({ hasText: /agent|chat/i }).first();
    if (await chatButton.isVisible()) {
      await chatButton.click();
    }

    // Wait for chat panel to be visible (right-side panel with input)
    const chatPanel = page.locator('aside.fixed.right-0');
    await expect(chatPanel).toBeVisible({ timeout: 5000 });

    // Type a message
    const input = page.locator('input[placeholder="Ask anything..."]');
    await expect(input).toBeVisible();
    await input.fill('Hello');

    // Submit by pressing Enter
    await input.press('Enter');

    // Wait for user message to appear
    const userMessage = chatPanel.locator('text=Hello').first();
    await expect(userMessage).toBeVisible({ timeout: 5000 });

    // Wait for assistant response (should NOT stay at "Thinking...")
    // The response should complete within 30 seconds
    const thinkingIndicator = chatPanel.locator('text=Thinking...');

    // Initially it should show "Thinking..."
    await expect(thinkingIndicator).toBeVisible({ timeout: 5000 });

    // Then it should disappear and be replaced with actual content
    await expect(thinkingIndicator).not.toBeVisible({ timeout: 30000 });

    // Verify there's an assistant message with actual content (not empty)
    const assistantMessages = chatPanel.locator('[class*="bg-muted"]').filter({
      hasNot: page.locator('text=Hello'), // Not the user's message
    });

    // Should have at least one assistant message with content
    const messageCount = await assistantMessages.count();
    expect(messageCount).toBeGreaterThan(0);
  });
});
