#!/usr/bin/env node

/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const { execSync } = require('child_process');

const ELECTRON_WIN7_VERSION = 'v37.2.2';
const ELECTRON_WIN7_REPO = 'e3kskoy7wqk/Electron-for-windows-7';
const DOWNLOAD_URL = `https://github.com/${ELECTRON_WIN7_REPO}/releases/download/${ELECTRON_WIN7_VERSION}/dist.zip`;

/**
 * Downloads a file with redirect following.
 */
function downloadFile(url, destPath) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(destPath);
    const request = (targetUrl) => {
      https
        .get(targetUrl, (response) => {
          if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
            return request(response.headers.location);
          }
          if (response.statusCode !== 200) {
            return reject(new Error(`Failed to download ${targetUrl}: HTTP ${response.statusCode}`));
          }
          response.pipe(file);
          file.on('finish', () => {
            file.close(resolve);
          });
        })
        .on('error', (err) => {
          fs.unlink(destPath, () => {});
          reject(err);
        });
    };
    request(url);
  });
}

/**
 * Ensures the Win7 Electron dist directory is available and extracted.
 * Returns the absolute path to the extracted Electron dist.
 */
async function ensureWin7Electron(customDir) {
  const rootDir = path.resolve(__dirname, '..');
  const targetDir = customDir
    ? path.resolve(customDir)
    : path.resolve(rootDir, '.cache', 'electron-win7', ELECTRON_WIN7_VERSION);

  const electronExe = path.join(targetDir, 'electron.exe');
  if (fs.existsSync(electronExe)) {
    console.log(`✅ Win7 Electron distribution found at: ${targetDir}`);
    return targetDir;
  }

  console.log(`⬇️  Win7 Electron not found. Downloading from ${DOWNLOAD_URL}...`);
  fs.mkdirSync(path.dirname(targetDir), { recursive: true });

  const tempZip = path.join(path.dirname(targetDir), `dist-${ELECTRON_WIN7_VERSION}.zip`);
  await downloadFile(DOWNLOAD_URL, tempZip);
  console.log(`📦 Download complete. Extracting to ${targetDir}...`);

  fs.mkdirSync(targetDir, { recursive: true });

  if (process.platform === 'win32') {
    execSync(`powershell -NoProfile -Command "Expand-Archive -Path '${tempZip}' -DestinationPath '${targetDir}' -Force"`, {
      stdio: 'inherit',
    });
  } else {
    execSync(`unzip -q -o "${tempZip}" -d "${targetDir}"`, { stdio: 'inherit' });
  }

  // Cleanup temp zip
  try {
    fs.unlinkSync(tempZip);
  } catch {}

  if (!fs.existsSync(electronExe)) {
    throw new Error(`Extraction failed: electron.exe not found in ${targetDir}`);
  }

  console.log(`✅ Win7 Electron prepared at: ${targetDir}`);
  return targetDir;
}

if (require.main === module) {
  const custom = process.argv[2];
  ensureWin7Electron(custom)
    .then((dir) => {
      console.log(`Ready: ${dir}`);
    })
    .catch((err) => {
      console.error('Error preparing Win7 Electron:', err);
      process.exit(1);
    });
}

module.exports = {
  ensureWin7Electron,
  ELECTRON_WIN7_VERSION,
};
