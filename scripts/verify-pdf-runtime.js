#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const RUNTIME_ROOT = path.join(PROJECT_ROOT, 'resources', 'pdf-runtime');
const TARGET_ROOT = path.join(RUNTIME_ROOT, 'win32-x64');
const MANIFEST_PATH = path.join(RUNTIME_ROOT, 'manifest.json');

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function fail(message) {
  throw new Error(`PDF runtime 校验失败：${message}`);
}

function main() {
  if (!fs.existsSync(MANIFEST_PATH)) fail(`缺少 ${MANIFEST_PATH}`);
  const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
  if (manifest.platform !== 'win32-x64') fail(`不支持的平台 ${manifest.platform}`);
  if (manifest.python?.version !== '3.8.10') fail(`Python 版本不是 3.8.10`);

  const pythonExe = path.join(TARGET_ROOT, manifest.python.executable || 'python.exe');
  if (!fs.existsSync(pythonExe)) fail('缺少 python.exe');
  const required = ['pypdf', 'reportlab', 'PIL', 'pdf2image', 'typing_extensions'];
  for (const packageName of required) {
    const candidates = packageName === 'PIL' ? ['PIL', 'Pillow'] : [packageName];
    if (!candidates.some((name) => fs.existsSync(path.join(TARGET_ROOT, 'Lib', 'site-packages', name)))) {
      fail(`缺少 Python 包 ${packageName}`);
    }
  }
  const popplerBin = path.join(TARGET_ROOT, manifest.poppler.relativeBin, 'pdftoppm.exe');
  if (!fs.existsSync(popplerBin)) fail(`缺少 Poppler: ${popplerBin}`);
  // Tesseract is optional; scanned PDFs use Poppler rendering plus the vision model.

  for (const [relative, expected] of Object.entries(manifest.files || {})) {
    const fullPath = path.join(TARGET_ROOT, relative);
    if (!fs.existsSync(fullPath)) fail(`manifest 引用的文件不存在: ${relative}`);
    const actual = sha256(fullPath);
    if (actual !== expected) fail(`SHA-256 不匹配: ${relative}`);
  }
  console.log(
    `✅ PDF runtime 校验通过：Python ${manifest.python.version}，${Object.keys(manifest.packages || {}).length} 个包，Poppler ${manifest.poppler.version}`
  );
}

try {
  main();
} catch (error) {
  console.error(`❌ ${error.message}`);
  process.exitCode = 1;
}
