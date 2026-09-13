import { test, expect } from "@playwright/test";

// Runs against the compose stack in replay mode (LLM_MODE=replay, no API key needed).
// See specs/001-denial-recovery/tasks.md T123 and quickstart.md §2.

test("hero case demo: remit to submitted appeal", async ({ page }) => {
  // 1. Reset demo.
  await page.goto("/");
  await expect(page.getByText("Demo date: 2026-09-12")).toBeVisible();
  await expect(page.getByText("AI: replay")).toBeVisible();

  page.on("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Reset demo" }).click();

  // 2. Simulate incoming remit; assert the A9 step 1 texts.
  await page.getByRole("button", { name: "Simulate incoming remit" }).click();
  await expect(page.getByText("Northstar Health · CO-50 Medical necessity · $4,800")).toBeVisible({
    timeout: 10_000,
  });
  await expect(page.getByText("1 paid claim, no action")).toBeVisible();
  await expect(page.getByText("1 other denial lane: not handled in this demo")).toBeVisible();

  // 3. Open the case and assert 6 passed identity checks.
  await page.getByText("Northstar Health · CO-50 Medical necessity · $4,800").click();
  await expect(page).toHaveURL(/\/cases\/case-100028/);
  await page.getByRole("tab", { name: "Identity" }).click();
  await expect(page.getByText("Passed")).toHaveCount(6, { timeout: 15_000 });

  // 4. Evidence tab.
  await page.getByRole("tab", { name: "Evidence" }).click();
  await expect(page.getByText("1 record excluded (outside 6-month lookback)")).toBeVisible();
  await expect(page.getByText("MedicationRequest: 0 found")).toBeVisible();

  // 5. Matrix tab.
  await page.getByRole("tab", { name: "Matrix" }).click();
  await expect(page.getByText("Policy NST-IMG-2026-04 v2026.04")).toBeVisible({ timeout: 20_000 });

  // 6. Packet tab.
  await page.getByRole("tab", { name: "Packet" }).click();
  await expect(page.getByText("Ready for review")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Evidence completeness: 3/3 policy criteria satisfied")).toBeVisible();
  await expect(page.getByText(/Appeal deadline: October 19, 2026/)).toBeVisible();
  await expect(page.getByText("Expected recovery: $4,800")).toBeVisible();

  // 7. Approve as billing-approver-01, then assert the confirmation and tracking.
  await expect(page.getByRole("button", { name: /Persona: billing-approver-01/ })).toBeVisible();
  await page.getByRole("button", { name: "Approve and submit" }).click();
  await expect(
    page.getByText("Submitted · Northstar confirmation NST-APL-80126 · expected resolution 14 days")
  ).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("In review")).toBeVisible({ timeout: 45_000 });
});
