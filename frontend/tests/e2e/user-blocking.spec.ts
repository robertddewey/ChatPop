import { test, expect } from '@playwright/test';

/**
 * E2E Test: User Blocking Flow
 *
 * This test simulates the complete user blocking flow:
 * 1. Host creates a chat room
 * 2. Regular user joins the chat
 * 3. Host blocks the user via long-press menu
 * 4. Blocked user receives WebSocket eviction event
 * 5. Blocked user is redirected to home page
 * 6. Blocked user cannot rejoin the chat
 */
test.describe('User Blocking Flow', () => {
  let chatCode: string;

  test('Host can block a user and user is immediately evicted', async ({ browser }) => {
    // Create two browser contexts (simulating two different users)
    const hostContext = await browser.newContext();
    const userContext = await browser.newContext();

    const hostPage = await hostContext.newPage();
    const userPage = await userContext.newPage();

    try {
      // Step 1: Host creates a chat room
      await hostPage.goto('/');
      await expect(hostPage.getByRole('heading', { name: /ChatPop/i })).toBeVisible();

      // Click "Create a ChatPop" button
      await hostPage.getByRole('button', { name: /Create a ChatPop/i }).click();

      // Fill in chat creation form
      await hostPage.getByLabel(/Chat Name/i).fill('E2E Blocking Test Chat');
      await hostPage.getByLabel(/Description/i).fill('Testing user blocking functionality');

      // Submit the form
      await hostPage.getByRole('button', { name: /Create Chat/i }).click();

      // Wait for redirect to chat page and extract chat code from URL
      await hostPage.waitForURL(/\/chat\/[A-Z0-9]+/);
      const hostUrl = hostPage.url();
      chatCode = hostUrl.split('/chat/')[1];
      console.log('Chat created with code:', chatCode);

      // Host should see the join modal
      await expect(hostPage.getByRole('dialog')).toBeVisible();

      // Host joins with username "HostUser"
      await hostPage.getByPlaceholder(/Enter username/i).fill('HostUser');
      await hostPage.getByRole('button', { name: /Join Chat/i }).click();

      // Wait for host to join successfully
      await expect(hostPage.getByPlaceholder(/Type a message/i)).toBeVisible();
      console.log('Host joined chat as HostUser');

      // Step 2: Regular user joins the chat
      await userPage.goto(`/chat/${chatCode}`);

      // User should see the join modal
      await expect(userPage.getByRole('dialog')).toBeVisible();

      // User joins with username "RegularUser"
      await userPage.getByPlaceholder(/Enter username/i).fill('RegularUser');
      await userPage.getByRole('button', { name: /Join Chat/i }).click();

      // Wait for user to join successfully
      await expect(userPage.getByPlaceholder(/Type a message/i)).toBeVisible();
      console.log('Regular user joined chat as RegularUser');

      // Step 3: Regular user sends a message
      await userPage.getByPlaceholder(/Type a message/i).fill('Hello from RegularUser!');
      await userPage.getByPlaceholder(/Type a message/i).press('Enter');

      // Wait for message to appear in chat
      await expect(userPage.getByText('Hello from RegularUser!')).toBeVisible();
      console.log('Regular user sent message');

      // Wait for message to appear on host's screen
      await expect(hostPage.getByText('Hello from RegularUser!')).toBeVisible();
      console.log('Host sees RegularUser message');

      // Step 4: Host long-presses (or right-clicks on desktop) the message to block user
      const messageElement = hostPage.getByText('Hello from RegularUser!');

      // Long press simulation (or right-click for desktop)
      // On mobile, this would be a long press; on desktop, we'll use a click with modifier
      await messageElement.click({ button: 'right' });

      // Wait for action modal to appear
      await expect(hostPage.getByText(/Chat Block/i)).toBeVisible();
      console.log('Host opened message actions modal');

      // Click "Chat Block" button
      await hostPage.getByText(/Chat Block/i).click();

      // Confirm the block action in the confirmation dialog
      await expect(hostPage.getByText(/Are you sure you want to block/i)).toBeVisible();
      await hostPage.getByRole('button', { name: /Block/i }).click();

      console.log('Host clicked Block button');

      // Step 5: Blocked user receives WebSocket eviction event and is redirected
      // Wait for user to be redirected to home page
      await userPage.waitForURL('/', { timeout: 10000 });
      console.log('Blocked user redirected to home page');

      // Verify user is on home page
      await expect(userPage.getByRole('heading', { name: /ChatPop/i })).toBeVisible();

      // Step 6: Blocked user tries to rejoin the chat (should be prevented)
      await userPage.goto(`/chat/${chatCode}`);

      // User should see join modal again
      await expect(userPage.getByRole('dialog')).toBeVisible();

      // Try to rejoin with same username
      await userPage.getByPlaceholder(/Enter username/i).fill('RegularUser');
      await userPage.getByRole('button', { name: /Join Chat/i }).click();

      // Should see an error message indicating user is blocked
      // Note: The exact error message depends on implementation
      // Wait for error (could be alert, toast, or inline error message)
      await expect(userPage.getByText(/blocked|banned|removed/i)).toBeVisible({ timeout: 5000 });
      console.log('Blocked user cannot rejoin chat');

    } finally {
      // Cleanup: Close contexts
      await hostContext.close();
      await userContext.close();
    }
  });

  test('Blocked user sees alert message before redirect', async ({ browser }) => {
    // This test focuses on verifying the alert message shown to blocked user
    const hostContext = await browser.newContext();
    const userContext = await browser.newContext();

    const hostPage = await hostContext.newPage();
    const userPage = await userContext.newPage();

    // Set up dialog handler to capture alert message
    let alertMessage = '';
    userPage.on('dialog', async (dialog) => {
      console.log('Alert type:', dialog.type());
      console.log('Alert message:', dialog.message());
      alertMessage = dialog.message();
      await dialog.accept();
    });

    try {
      // Reuse the chat from previous test if possible, or create new one
      // For simplicity, we'll create a new chat

      // Host creates chat
      await hostPage.goto('/');
      await hostPage.getByRole('button', { name: /Create a ChatPop/i }).click();
      await hostPage.getByLabel(/Chat Name/i).fill('Alert Test Chat');
      await hostPage.getByRole('button', { name: /Create Chat/i }).click();
      await hostPage.waitForURL(/\/chat\/[A-Z0-9]+/);

      const chatUrl = hostPage.url();
      chatCode = chatUrl.split('/chat/')[1];

      // Host joins
      await hostPage.getByPlaceholder(/Enter username/i).fill('HostUser2');
      await hostPage.getByRole('button', { name: /Join Chat/i }).click();
      await expect(hostPage.getByPlaceholder(/Type a message/i)).toBeVisible();

      // User joins
      await userPage.goto(`/chat/${chatCode}`);
      await userPage.getByPlaceholder(/Enter username/i).fill('BlockedUser');
      await userPage.getByRole('button', { name: /Join Chat/i }).click();
      await expect(userPage.getByPlaceholder(/Type a message/i)).toBeVisible();

      // User sends message
      await userPage.getByPlaceholder(/Type a message/i).fill('Test message');
      await userPage.getByPlaceholder(/Type a message/i).press('Enter');
      await expect(hostPage.getByText('Test message')).toBeVisible();

      // Host blocks user
      await hostPage.getByText('Test message').click({ button: 'right' });
      await hostPage.getByText(/Chat Block/i).click();
      await hostPage.getByRole('button', { name: /Block/i }).click();

      // Wait for user to be redirected
      await userPage.waitForURL('/', { timeout: 10000 });

      // Verify alert was shown
      expect(alertMessage).toContain('removed');
      console.log('Alert message verified:', alertMessage);

    } finally {
      await hostContext.close();
      await userContext.close();
    }
  });
});
