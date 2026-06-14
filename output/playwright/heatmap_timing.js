async (page) => {
  const started = [];
  const finished = [];
  const reqHandler = request => {
    if (request.url().includes('/operation/api/parking-data/')) {
      started.push(Date.now());
    }
  };
  const doneHandler = response => {
    if (response.url().includes('/operation/api/parking-data/')) {
      finished.push(Date.now());
    }
  };
  page.on('request', reqHandler);
  page.on('response', doneHandler);
  const t0 = Date.now();
  await page.goto('http://127.0.0.1:8000/operation/heatmap/');
  const timeline = [];
  for (let i = 0; i < 56; i += 1) {
    timeline.push(await page.evaluate(start => ({
      ms: Date.now() - start,
      countdown: document.querySelector('#dispatchRefreshCountdown')?.textContent?.trim(),
      snapshotTime: document.querySelector('#predictTime')?.textContent?.trim(),
      firstRow: Array.from(document.querySelectorAll('#dispatchTableBody tr')[0]?.querySelectorAll('td') || []).map(td => td.textContent.trim()).slice(0, 4),
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
