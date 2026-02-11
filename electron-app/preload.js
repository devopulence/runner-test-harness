const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  getTestResults: () => ipcRenderer.invoke('get-test-results')
});
