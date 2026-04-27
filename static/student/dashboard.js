import QrScanner from '../qr-scanner.min.js';

function updateClock() {
  const now = new Date();
  const options = { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' };
  const currentDate = now.toLocaleDateString(undefined, options);
  const currentTime = now.toLocaleTimeString();

  const dateEl = document.getElementById('currentDate');
  const dateDisplay = document.getElementById('dateDisplay');
  const timeEl = document.getElementById('clock');

  if (dateEl) {
    dateEl.textContent = currentDate;
  }
  if (dateDisplay) {
    dateDisplay.textContent = currentDate;
  }
  if (timeEl) {
    timeEl.textContent = currentTime;
  }
}

let qrScanner = null;
let isScanning = false;
let lastScanTime = 0;
const SCAN_COOLDOWN = 3000;

function updateScannerStatus(message, status = 'idle') {
  const statusBadge = document.getElementById('scannerStatusBadge');
  const statusText = document.getElementById('scannerStatusText');
  const lastScan = document.getElementById('lastScanTime');

  if (statusBadge) {
    statusBadge.textContent = status === 'success' ? 'Active' : status === 'error' ? 'Error' : 'Idle';
    statusBadge.className = `status-badge ${status === 'success' ? 'status-in' : status === 'error' ? 'status-out' : 'status-pending'}`;
  }

  if (statusText) {
    statusText.textContent = message;
  }

  if (lastScan && status === 'success') {
    const now = new Date();
    lastScan.textContent = now.toLocaleTimeString();
  }
}

async function startScanner() {
  const startButton = document.getElementById('startScanner');
  const stopButton = document.getElementById('stopScanner');
  const videoElement = document.getElementById('qrPreview');
  const scanGuide = document.getElementById('scanGuide');

  if (!videoElement || !startButton || !stopButton) {
    return;
  }

  if (isScanning) {
    return;
  }

  try {
    if (!qrScanner) {
      qrScanner = new QrScanner(
        videoElement,
        async (result) => {
          const now = Date.now();
          if (now - lastScanTime < SCAN_COOLDOWN) {
            return;
          }
          if (!isScanning) {
            return;
          }

          lastScanTime = now;
          updateScannerStatus('Recording attendance...', 'loading');
          qrScanner.pause();

          updateScannerStatus(`Scanned: ${result.data}`, 'success');

          setTimeout(() => {
            if (isScanning && qrScanner) {
              qrScanner.start().catch(() => {});
              updateScannerStatus('Position QR code in frame', 'idle');
            }
          }, SCAN_COOLDOWN);
        },
        {
          preferredCamera: 'environment',
          highlightScanRegion: true,
          highlightCodeOutline: true,
          maxScansPerSecond: 5
        }
      );
    }

    isScanning = true;
    lastScanTime = 0;
    await qrScanner.start();
    if (scanGuide) {
      scanGuide.classList.add('active');
      scanGuide.style.opacity = '1';
    }
    updateScannerStatus('Position QR code in frame', 'idle');
    startButton.disabled = true;
    stopButton.disabled = false;
  } catch (error) {
    console.error('Failed to start QR scanner:', error);
    updateScannerStatus('Unable to start scanner', 'error');
    isScanning = false;
  }
}

function stopScanner() {
  const startButton = document.getElementById('startScanner');
  const stopButton = document.getElementById('stopScanner');
  const scanGuide = document.getElementById('scanGuide');

  if (!isScanning || !qrScanner) {
    return;
  }

  qrScanner.stop();
  isScanning = false;
  if (scanGuide) {
    scanGuide.classList.remove('active');
    scanGuide.style.opacity = '0';
  }
  updateScannerStatus('Scanner stopped', 'idle');
  if (startButton) {
    startButton.disabled = false;
  }
  if (stopButton) {
    stopButton.disabled = true;
  }
}

function initializeDashboard() {
  updateClock();
  setInterval(updateClock, 1000);

  const startButton = document.getElementById('startScanner');
  const stopButton = document.getElementById('stopScanner');

  if (startButton) {
    startButton.addEventListener('click', startScanner);
  }
  if (stopButton) {
    stopButton.addEventListener('click', stopScanner);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeDashboard);
} else {
  initializeDashboard();
}
