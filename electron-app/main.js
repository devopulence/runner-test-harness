const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

const TEST_RESULTS_DIR = path.join(__dirname, '..', 'test_results', 'aws-ecs');

function loadTestResults() {
  const results = {};

  if (!fs.existsSync(TEST_RESULTS_DIR)) {
    console.error('Test results directory not found:', TEST_RESULTS_DIR);
    return results;
  }

  const dirs = fs.readdirSync(TEST_RESULTS_DIR, { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => d.name);

  for (const dir of dirs) {
    // Parse folder name: {type}_{flavor}_{date}_{time}_{hash}
    const parts = dir.split('_');
    if (parts.length < 3) continue;

    const testType = parts[0];
    const flavor = parts[1];
    const dirPath = path.join(TEST_RESULTS_DIR, dir);

    const files = ['metadata.json', 'kpi.json', 'analysis.json', 'enhanced_report.json',
                   'post_hoc.json', 'test_report.json', 'tracking.json', 'snapshots.json'];

    const data = { testType, flavor, dirName: dir };

    for (const file of files) {
      const filePath = path.join(dirPath, file);
      if (fs.existsSync(filePath)) {
        try {
          const key = file.replace('.json', '');
          data[key] = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
        } catch (e) {
          console.error(`Error reading ${filePath}:`, e.message);
        }
      }
    }

    if (!results[testType]) {
      results[testType] = [];
    }
    results[testType].push(data);
  }

  // Sort each type's results by directory name (chronological)
  for (const type of Object.keys(results)) {
    results[type].sort((a, b) => a.dirName.localeCompare(b.dirName));
  }

  return results;
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  win.loadFile('index.html');
}

ipcMain.handle('get-test-results', () => {
  return loadTestResults();
});

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  app.quit();
});
