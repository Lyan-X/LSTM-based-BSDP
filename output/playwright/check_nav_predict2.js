async (page) => {
  await page.goto('http://127.0.0.1:8000/system/dashboard/');
  await page.evaluate(() => {
    sessionStorage.removeItem('overlaySeen');
    const origShow = window.BSDPUI && window.BSDPUI.showLoading;
    if (origShow && !window.__overlayPatched) {
      window.__overlayPatched = true;
      window.BSDPUI.showLoading = function (...args) {
        sessionStorage.setItem('overlaySeen', '1');
        return origShow.apply(this, args);
      };
    }
  });
  const link = page.locator('a[href="/predict/"], a[href="http://127.0.0.1:8000/predict/"]').first();
  await link.waitFor({ state: 'visible' });
  await Promise.all([
    page.waitForURL('**/predict/'),
    link.click(),
  ]);
  const result = await page.evaluate(() => ({
    overlaySeen: sessionStorage.getItem('overlaySeen'),
    refreshStripVisible: !!document.querySelector('#predictionRefreshCountdown'),
  }));
  return { url: page.url(), title: await page.title(), ...result };
}
