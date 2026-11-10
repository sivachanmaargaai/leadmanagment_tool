import { test, expect } from "@playwright/test";

const challenge = "c".repeat(43);
const grant = "g".repeat(43);

async function mockRecovery(page, { disabled = false, throttleResend = false } = {}) {
  const calls = [];
  let sends = 0;
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const body = request.postDataJSON();
    calls.push({ path, body });
    if (path === "/api/auth/refresh" || path === "/api/auth/me") return route.fulfill({ status: 401, json: { detail: "Sign in to continue" } });
    if (path === "/api/auth/forgot-password" && ++sends > 1 && throttleResend) return route.fulfill({ status: 429, headers: { "Retry-After": "120" }, json: { detail: "Please wait before requesting another code" } });
    if (path === "/api/auth/forgot-password") return route.fulfill(disabled
      ? { status: 503, json: { detail: "Password recovery email is not configured. Contact your workspace Owner" } }
      : { status: 202, json: { message: "If an active account matches that email, a password reset code will be sent.", challengeId: challenge, expiresInMinutes: 10, resendAfterSeconds: 60 } });
    if (path === "/api/auth/verify-reset-otp") return route.fulfill(body.code === "012345"
      ? { json: { resetToken: grant, expiresInMinutes: 5 } }
      : { status: 400, json: { detail: "Code is invalid, expired or already used. Request a new code if needed" } });
    if (path === "/api/auth/reset-password") return route.fulfill({ status: 204, body: "" });
    throw new Error(`Unexpected recovery request: ${path}`);
  });
  return calls;
}

for (const viewport of [{ width: 390, height: 844 }, { width: 820, height: 1180 }, { width: 1440, height: 900 }]) {
  test(`email OTP recovery completes without overflow at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const calls = await mockRecovery(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Forgot password?" }).click();
    await page.getByLabel("Email address").fill("owner@example.test");
    await page.getByRole("button", { name: "Send reset code", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Enter your reset code" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Resend in/ })).toBeDisabled();
    await page.getByLabel("Reset code").fill("999999");
    await page.getByRole("button", { name: "Verify code" }).click();
    await expect(page.getByRole("alert")).toContainText("Code is invalid");
    await page.getByLabel("Reset code").fill("012345");
    await page.getByRole("button", { name: "Verify code" }).click();
    await expect(page.getByRole("heading", { name: "Choose a new password" })).toBeVisible();
    await page.getByLabel("New password", { exact: true }).fill("FixtureOnly123!");
    await page.getByLabel("Confirm new password").fill("Different123!");
    await page.getByRole("button", { name: "Reset password", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("Passwords do not match");
    expect(calls.filter((call) => call.path.endsWith("/reset-password"))).toHaveLength(0);
    await page.getByLabel("Confirm new password").fill("FixtureOnly123!");
    await page.getByRole("button", { name: "Reset password", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("Password reset. Sign in with your new password.");
    expect(calls.find((call) => call.path.endsWith("/reset-password")).body).toEqual({ token: grant, newPassword: "FixtureOnly123!" });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const storage = await page.evaluate(() => JSON.stringify([localStorage, sessionStorage]));
    expect(storage).not.toContain(grant);
    expect(storage).not.toContain(challenge);
    expect(page.url()).not.toContain(grant);
    expect(errors).toEqual([]);
  });
}

test("unconfigured recovery shows an error and stays on the email screen", async ({ page }) => {
  await mockRecovery(page, { disabled: true });
  await page.goto("/");
  await page.getByRole("button", { name: "Forgot password?" }).click();
  await page.getByLabel("Email address").fill("owner@example.test");
  await page.getByRole("button", { name: "Send reset code", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("not configured");
  await expect(page.getByRole("heading", { name: "Forgot your password?" })).toBeVisible();
});

test("resend cooldown prevents duplicate sends and change-email clears code", async ({ page }) => {
  const calls = await mockRecovery(page);
  await page.clock.install();
  await page.goto("/");
  await page.getByRole("button", { name: "Forgot password?" }).click();
  await page.getByLabel("Email address").fill("owner@example.test");
  await page.getByRole("button", { name: "Send reset code", exact: true }).click();
  await expect(page.getByLabel("Reset code")).toBeVisible();
  await page.clock.fastForward(61000);
  await page.getByRole("button", { name: "Resend code", exact: true }).click();
  await expect(page.getByRole("button", { name: /Resend in/ })).toBeDisabled();
  expect(calls.filter((call) => call.path.endsWith("/forgot-password"))).toHaveLength(2);
  await page.getByLabel("Reset code").fill("012345");
  await page.getByRole("button", { name: "Change email" }).click();
  await expect(page.getByLabel("Reset code")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Send reset code", exact: true })).toBeDisabled();
});

test("server resend throttling preserves the current challenge and uses Retry-After", async ({ page }) => {
  await mockRecovery(page, { throttleResend: true });
  await page.clock.install();
  await page.goto("/");
  await page.getByRole("button", { name: "Forgot password?" }).click();
  await page.getByLabel("Email address").fill("owner@example.test");
  await page.getByRole("button", { name: "Send reset code", exact: true }).click();
  await expect(page.getByLabel("Reset code")).toBeVisible();
  await page.clock.fastForward(61000);
  await page.getByRole("button", { name: "Resend code", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Please wait");
  await expect(page.getByRole("button", { name: /Resend in 1[12][0-9]s/ })).toBeDisabled();
  await page.getByLabel("Reset code").fill("012345");
  await page.getByRole("button", { name: "Verify code" }).click();
  await expect(page.getByRole("heading", { name: "Choose a new password" })).toBeVisible();
});
