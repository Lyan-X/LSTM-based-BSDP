async (page) => {
  const started = [];
  const finished = [];
  const reqHandler = request => {
    if (request.url().includes('/system/api/dashboard/')) {
      started.push(Date.now());
    }
  };
  const doneHandler = response => {
    if (response.url().includes('/system/api/dashboard/')) {
      finished.push(Date.now());
    }
  };
  page.on('request', reqHandler);
  page.on('response', doneHandler);
  const t0 = Date.now();
  await page.goto('http://127.0.0.1:8000/system/dashboard/');
  const timeline = [];
  for (let i = 0; i < 72; i += 1) {
    timeline.push(await page.evaluate(start => ({
      ms: Date.now() - start,
      countdown: document.querySelector('#dashboardRefreshCountdown')?.textContent?.trim(),
      generatedAt: document.querySelector('#dashboardGeneratedAt')?.textContent?.trim(),
      markerFirst12: Array.from(document.querySelectorAll('.station-marker')).map(el => Number(el.textContent.trim())).filter(n => !Number.isNaN(n)).slice(0, 12),
    }), t0));
    await page.waitForTimeout(250);
  }
  page.off('request', reqHandler);
  page.off('response', doneHandler);
  return {
    started: started.map(v => v - t0),
    finished: finished.map(v => v - t0),
    timeline,
  };
}
