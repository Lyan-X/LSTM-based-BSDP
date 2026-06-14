async (page) => {
  await page.goto('http://127.0.0.1:8000/system/dashboard/');
  await page.evaluate(() => {
    sessionStorage.removeItem('overlaySeen');
    const loading = document.getElementById('loading');
    if (!loading) return;
    const markSeen = () => {
      const display = window.getComputedStyle(loading).display;
      if (display !== 'none') {
        sessionStorage.setItem('overlaySeen', '1');
      }
    };
    markSeen();
    if (!window.__loadingObserverAttached) {
      window.__loadingObserverAttached = true;
      const observer = new MutationObserver(markSeen);
      observer.observe(loading, { attributes: true, attributeFilter: ['style', 'class'] });
      window.addEventListener('beforeunload', markSeen);
      loading.addEventListener('transitionstart', markSeen);
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
