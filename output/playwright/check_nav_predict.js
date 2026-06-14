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
  await Promise.all([
    page.waitForURL('**/predict/'),
    page.evaluate(() => {
      const link = Array.from(document.querySelectorAll('a')).find(a => a.href.endsWith('/predict/') && (a.offsetWidth || a.offsetHeight || a.getClientRects().length));
      if (!link) throw new Error('predict link not found');
      link.click();
    }),
  ]);
  const result = await page.evaluate(() => ({
    overlaySeen: sessionStorage.getItem('overlaySeen'),
    pageLoadingText: document.body.innerText.includes('正在接入最新预测批次与历史回溯结果') || document.body.innerText.includes('正在加载预测摘要'),
    refreshStripVisible: !!document.querySelector('#predictionRefreshCountdown'),
  }));
  return { url: page.url(), title: await page.title(), ...result };
}
