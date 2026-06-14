"use strict";
const electronModule = require("electron");
const { app } = electronModule;
const chromiumSwitches = [
  "--disable-field-trial-config",
  "--disable-background-networking",
  "--disable-background-timer-throttling",
  "--disable-backgrounding-occluded-windows",
  "--disable-back-forward-cache",
  "--disable-breakpad",
  "--disable-client-side-phishing-detection",
  "--disable-component-extensions-with-background-pages",
  "--disable-component-update",
  "--no-default-browser-check",
  "--disable-default-apps",
  "--disable-dev-shm-usage",
  "--disable-edgeupdater",
  "--disable-extensions",
  "--disable-features=AvoidUnnecessaryBeforeUnloadCheckSync,BoundaryEventDispatchTracksNodeRemoval,DestroyProfileOnBrowserClose,DialMediaRouteProvider,GlobalMediaControls,HttpsUpgrades,LensOverlay,MediaRouter,PaintHolding,ThirdPartyStoragePartitioning,Translate,AutoDeElevate,RenderDocument,OptimizationHints,msForceBrowserSignIn,msEdgeUpdateLaunchServicesPreferredVersion",
  "--enable-features=CDPScreenshotNewSurface",
  "--allow-pre-commit-input",
  "--disable-hang-monitor",
  "--disable-ipc-flooding-protection",
  "--disable-popup-blocking",
  "--disable-prompt-on-repost",
  "--disable-renderer-backgrounding",
  "--force-color-profile=srgb",
  "--metrics-recording-only",
  "--no-first-run",
  "--password-store=basic",
  "--use-mock-keychain",
  "--no-service-autorun",
  "--export-tagged-pdf",
  "--disable-search-engine-choice-screen",
  "--unsafely-disable-devtools-self-xss-warnings",
  "--edge-skip-compat-layer-relaunch",
  "--enable-automation",
  "--disable-infobars",
  "--disable-sync"
];
globalThis.__playwright_electron = electronModule;
process.argv.splice(1, process.argv.indexOf("--remote-debugging-port=0"));
for (const arg of chromiumSwitches) {
  const match = arg.match(/--([^=]*)=?(.*)/);
  app.commandLine.appendSwitch(match[1], match[2]);
}
const originalWhenReady = app.whenReady();
const originalEmit = app.emit.bind(app);
let readyEventArgs;
app.emit = (event, ...args) => {
  if (event === "ready") {
    readyEventArgs = args;
    return app.listenerCount("ready") > 0;
  }
  return originalEmit(event, ...args);
};
let isReady = false;
let whenReadyCallback;
const whenReadyPromise = new Promise((f) => whenReadyCallback = f);
app.isReady = () => isReady;
app.whenReady = () => whenReadyPromise;
globalThis.__playwright_run = async () => {
  const event = await originalWhenReady;
  isReady = true;
  whenReadyCallback(event);
  originalEmit("ready", ...readyEventArgs);
};
