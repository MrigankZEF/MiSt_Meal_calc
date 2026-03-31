// Playwright test template: open the demo and exercise toggle + calculate flow
// Requires Playwright to be installed; this is a template to run locally.

const { test, expect } = require('@playwright/test');

test('toggle and totals flow', async ({ page }) => {
  await page.goto('http://127.0.0.1:9000/');
  // wait for initial search results to render
  await page.waitForSelector('#results');
  // pick first Select button if present
  const selectBtn = await page.$('button:has-text("Select")');
  if (selectBtn) {
    await selectBtn.click();
    // choose Add to meal
    await page.click('#addBtn');
    // open meal list and set amount
    await page.fill('input[id^="amt"]', '200');
    // calculate
    await page.click('button:has-text("Calculate meal")');
    // wait for total
    await page.waitForSelector('.card');
    // switch to per 100g
    await page.selectOption('#displayMode', '100g');
    // verify chips update
    const co2Chip = await page.textContent('#chip_co2');
    expect(co2Chip).toContain('CO2:');
  }
});
