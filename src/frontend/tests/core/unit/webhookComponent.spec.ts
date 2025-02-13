import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to create an api key within a webhook component",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const randomApiKeyDescription =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);

    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("webhook");

    await page.waitForSelector('[data-testid="dataWebhook"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("dataWebhook")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-webhook").click();
      });

    await adjustScreenView(page);

    await page
      .getByTestId("data_webhook_draggable")
      .hover()
      .then(async () => {
        await page.waitForSelector("text=Webhook already added", {
          timeout: 30000,
        });
      });

    await page.getByTestId("btn_copy_str_endpoint").click();
    await page.waitForSelector("text=Endpoint URL copied", { timeout: 30000 });

    await page.getByTestId("generate_token_webhook_button").click();
    await page.waitForSelector("text=Create API Key", { timeout: 30000 });
    await page.getByPlaceholder("My API Key").click();
    await page.getByPlaceholder("My API Key").fill(randomApiKeyDescription);
    await page.getByText("Generate API Key").click();
    await page.waitForSelector(
      "text=Please save this secret key somewhere safe and accessible.",
      { timeout: 30000 },
    );

    await page.getByTestId("btn-copy-api-key").click();
    await page.waitForSelector("text=API Key copied", { timeout: 30000 });

    await page.getByText("Done").click();

    await page.getByTestId("user_menu_button").click();
    await page.getByText("Settings").click();

    await page.getByTestId("sidebar-nav-Langflow API Keys").click();
    await page.waitForSelector(`text=${randomApiKeyDescription}`, {
      timeout: 30000,
    });
  },
);

test(
  "user should be able to poll a webhook",
  { tag: ["@release", "@workspace"] },
  async ({ page, request }) => {
    await page.route("**/api/v1/config", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          webhook_pooling_interval: 1000,
        }),
        headers: {
          "content-type": "application/json",
          ...route.request().headers(),
        },
      });
    });

    const randomApiKeyDescription =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);

    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("webhook");

    await page.waitForSelector('[data-testid="dataWebhook"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("dataWebhook")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-webhook").click();
      });

    await adjustScreenView(page);

    await page
      .getByTestId("data_webhook_draggable")
      .hover()
      .then(async () => {
        await page.waitForSelector("text=Webhook already added", {
          timeout: 30000,
        });
      });

    await page.getByTestId("btn_copy_str_endpoint").click();
    await page.waitForSelector("text=Endpoint URL copied", { timeout: 30000 });

    await page.getByTestId("generate_token_webhook_button").click();
    await page.waitForSelector("text=Create API Key", { timeout: 30000 });
    await page.getByPlaceholder("My API Key").click();
    await page.getByPlaceholder("My API Key").fill(randomApiKeyDescription);
    await page.getByText("Generate API Key").click();
    await page.waitForSelector(
      "text=Please save this secret key somewhere safe and accessible.",
      { timeout: 30000 },
    );

    await page.getByTestId("btn-copy-api-key").click();
    await page.waitForSelector("text=API Key copied", { timeout: 30000 });

    await page.getByText("Done").click();

    await page.getByTestId("title-Webhook").click();
    await page.getByTestId("edit-button-modal").click();

    const curlValue = await page.getByTestId("str_edit_curl").inputValue();

    await page.getByText("Close").last().click();

    // Extract the full URL from the curl command
    const urlMatch = curlValue.match(/"([^"]+)"/);
    const webhookUrl = urlMatch?.[1];
    expect(webhookUrl).toBeTruthy();

    const webhookResponse = await request.post(webhookUrl!, {
      data: { any: "data" },
      headers: {
        "Content-Type": "application/json",
      },
    });
    expect(webhookResponse.ok()).toBeTruthy();
  },
);
