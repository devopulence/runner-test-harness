const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  getAvailableDates: () => ipcRenderer.invoke('get-available-dates'),
  getMonitoringData: (date) => ipcRenderer.invoke('get-monitoring-data', date),
});
