async (page) => {
  await page.goto('http://127.0.0.1:8000/predict/');
  await page.evaluate(() => {
    sessionStorage.removeItem('overlaySeen');
    const loading = document.getElementById('loading');
    if (!loading) return;
    const markSeen = () => {
      if (window.getComputedStyle(loading).display !== 'none') {
        sessionStorage.setItem('overlaySeen', '1');
      }
    };
    if (!window.__loadingObserverAttached) {
      window.__loadingObserverAttached = true;
      const observer = new MutationObserver(markSeen);
      observer.observe(loading, { attributes: true, attributeFilter: ['style', 'class'] });
      window.addEventListener('beforeunload', markSeen);
      loading.addEventListener('transitionstart', markSeen);
    }
  });
  const link = page.locator('a[href="/operation/"], a[href="http://127.0.0.1:8000/operation/"]').first();
  await link.waitFor({ state: 'visible' });
  await Promise.all([
    page.waitForURL(url => url.pathname === '/operation/' || url.pathname === '/operation/heatmap/'),
    link.click(),
  ]);
  const result = await page.evaluate(() => ({
    overlaySeen: sessionStorage.getItem('overlaySeen'),
    refreshStripVisible: !!document.querySelector('#dispatchRefreshCountdown'),
    rowCount: document.querySelectorAll('#dispatchTableBody tr').length,
    hasMap: !!document.querySelector('#dispatchMap'),
  }));
  return { url: page.url(), title: await page.title(), ...result };
}
