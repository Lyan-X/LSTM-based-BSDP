async (page) => {
  await page.goto('http://127.0.0.1:8000/system/login/?next=/system/dashboard/');
  await page.locator('input[name="username"]').fill('bsdp_admin');
  await page.locator('input[name="password"]').fill('BSDP@2026!');
  await page.locator('input[name="role"][value="admin"]').check();
  await Promise.all([
    page.waitForURL('**/system/dashboard/'),
    page.locator('button[type="submit"], button:has-text("µÇÂ¼")').click(),
  ]);
  return { url: page.url(), title: await page.title() };
}
