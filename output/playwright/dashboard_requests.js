async (page) => {
  const requests = [];
  const handler = request => {
    if (request.url().includes('/system/api/dashboard/')) {
      requests.push({
        at: Date.now(),
        url: request.url(),
        method: request.method(),
      });
    }
  };
  page.on('request', handler);
  await page.goto('http://127.0.0.1:8000/system/dashboard/');
  await page.waitForTimeout(16000);
  page.off('request', handler);
  const origin = requests.length ? requests[0].at : Date.now();
  return requests.map(item => ({ msFromFirst: item.at - origin, url: item.url, method: item.method }));
}
