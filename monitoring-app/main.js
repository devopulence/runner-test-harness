const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

const MONITORING_DIR = path.join(__dirname, '..', 'monitoring_data');

function loadMonitoringData(dateStr) {
  const dayDir = path.join(MONITORING_DIR, dateStr);
  const data = { date: dateStr };

  const files = {
    workflow_runs: 'workflow_runs.json',
    jobs: 'jobs.json',
    collection_log: 'collection_log.json',
    computed_metrics: 'computed_metrics.json',
  };

  for (const [key, filename] of Object.entries(files)) {
    const filePath = path.join(dayDir, filename);
    if (fs.existsSync(filePath)) {
      try {
        data[key] = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      } catch (e) {
        console.error(`Error reading ${filePath}:`, e.message);
        data[key] = [];
      }
    } else {
      data[key] = key === 'computed_metrics' ? null : [];
    }
  }

  return data;
}

function getAvailableDates() {
  if (!fs.existsSync(MONITORING_DIR)) return [];

  return fs.readdirSync(MONITORING_DIR, { withFileTypes: true })
    .filter(d => d.isDirectory() && /^\d{4}-\d{2}-\d{2}$/.test(d.name))
    .map(d => d.name)
    .sort()
    .reverse();
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1500,
    height: 1000,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadFile('index.html');
}

ipcMain.handle('get-available-dates', () => {
  return getAvailableDates();
});

ipcMain.handle('get-monitoring-data', (event, dateStr) => {
  return loadMonitoringData(dateStr);
});

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  app.quit();
});