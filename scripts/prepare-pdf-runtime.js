#!/usr/bin/env node

/**
 * Prepare the offline PDF runtime bundled into Windows packages.
 *
 * The repository intentionally does not commit the Python/Poppler binaries.
 * CI downloads the pinned artifacts, records their SHA-256 values in the
 * manifest, and the packaging step copies the completed runtime into the app.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawnSync } = require('child_process');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const RUNTIME_ROOT = path.join(PROJECT_ROOT, 'resources', 'pdf-runtime');
const TARGET_ROOT = path.join(RUNTIME_ROOT, 'win32-x64');
const MANIFEST_PATH = path.join(RUNTIME_ROOT, 'manifest.json');
const PYTHON_VERSION = '3.8.10';
const POPPLER_VERSION = '23.11.0-0';
const POPPLER_URL =
  process.env.AIONUI_POPPLER_URL ||
  `https://github.com/oschwartz10612/poppler-windows/releases/download/v${POPPLER_VERSION}/Release-${POPPLER_VERSION}.zip`;
const PACKAGE_VERSIONS = {
  pypdf: '5.9.0',
  reportlab: '4.2.5',
  Pillow: '10.4.0',
  pdf2image: '1.17.0',
};

function parseArgs() {
  const args = new Set(process.argv.slice(2));
  const valueAfter = (flag, fallback) => {
    const index = process.argv.indexOf(flag);
    return index >= 0 ? process.argv[index + 1] || fallback : fallback;
  };
  return {
    platform: valueAfter('--platform', 'win32'),
    arch: valueAfter('--arch', 'x64'),
    verifyOnly: args.has('--verify-only'),
  };
}

function sha256(filePath) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(filePath));
  return hash.digest('hex');
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: PROJECT_ROOT,
    stdio: 'inherit',
    // Pass arguments directly on Windows. Using cmd.exe here breaks the
    // Python `-c` extraction snippet by splitting it at spaces/semicolons.
    shell: false,
    env: process.env,
    ...options,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} exited with status ${result.status}`);
}

function findPython() {
  for (const candidate of process.platform === 'win32' ? ['py', 'python', 'python3'] : ['python3', 'python']) {
    const result = spawnSync(candidate, ['--version'], { stdio: 'ignore', shell: false });
    if (result.status === 0) return candidate;
  }
  throw new Error('未找到宿主 Python。Action runner 必须预装 Python 3，才能下载并展开 Win7 PDF 依赖。');
}

function extractZip(zipPath, destination) {
  fs.mkdirSync(destination, { recursive: true });
  const python = findPython();
  const script = 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])';
  run(python, ['-c', script, zipPath, destination]);
}

function download(url, destination) {
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  console.log(`⬇️  ${url}`);
  const curl = spawnSync(
    'curl',
    ['-L', '--fail', '--retry', '3', '--retry-delay', '2', '--connect-timeout', '30', '-o', destination, url],
    { cwd: PROJECT_ROOT, stdio: 'inherit', shell: false, env: process.env }
  );
  if (curl.status !== 0) {
    throw new Error(`下载失败：${url}（curl exit ${curl.status}）。请检查 Action 网络或代理设置。`);
  }
}

function findPopplerBin(root) {
  const queue = [root];
  while (queue.length > 0) {
    const current = queue.shift();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) queue.push(fullPath);
      if (entry.isFile() && entry.name.toLowerCase() === 'pdftoppm.exe') return path.dirname(fullPath);
    }
  }
  return null;
}

function preparePython(targetRoot, wheelDir) {
  const pythonZip = path.join(wheelDir, `python-${PYTHON_VERSION}-embed-amd64.zip`);
  if (!fs.existsSync(pythonZip)) {
    download(`https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip`, pythonZip);
  }
  extractZip(pythonZip, targetRoot);

  const sitePackages = path.join(targetRoot, 'Lib', 'site-packages');
  fs.mkdirSync(sitePackages, { recursive: true });
  const pythonPth = path.join(targetRoot, 'python38._pth');
  if (!fs.existsSync(pythonPth)) throw new Error(`Python embeddable 包缺少 ${pythonPth}`);
  let pth = fs.readFileSync(pythonPth, 'utf8');
  if (!pth.split(/\r?\n/).some((line) => line.trim() === 'Lib/site-packages')) pth += '\nLib/site-packages\n';
  if (!/^import site\s*$/m.test(pth)) pth += 'import site\n';
  fs.writeFileSync(pythonPth, pth);

  const hostPython = findPython();
  const packages = Object.entries(PACKAGE_VERSIONS);
  for (const [name, version] of packages) {
    const wheelSpec = `${name}==${version}`;
    console.log(`📦 下载 ${wheelSpec} (cp38 win_amd64)`);
    run(hostPython, [
      '-m',
      'pip',
      'download',
      '--disable-pip-version-check',
      '--only-binary=:all:',
      '--no-deps',
      '--platform',
      'win_amd64',
      '--python-version',
      '38',
      '--implementation',
      'cp',
      '--abi',
      'cp38',
      '--dest',
      wheelDir,
      wheelSpec,
    ]);
    const wheel = fs
      .readdirSync(wheelDir)
      .filter((entry) => entry.toLowerCase().startsWith(name.toLowerCase().replace('-', '_')) && entry.endsWith('.whl'))
      .sort()
      .at(-1);
    if (!wheel) throw new Error(`pip 未下载 ${wheelSpec} 的 wheel`);
    extractZip(path.join(wheelDir, wheel), sitePackages);
  }
}

function preparePoppler(targetRoot, wheelDir) {
  const popplerZip = path.join(wheelDir, `poppler-${POPPLER_VERSION}.zip`);
  if (!fs.existsSync(popplerZip)) {
    download(POPPLER_URL, popplerZip);
  }
  const extracted = path.join(wheelDir, 'poppler-extracted');
  fs.rmSync(extracted, { recursive: true, force: true });
  extractZip(popplerZip, extracted);
  const bin = findPopplerBin(extracted);
  if (!bin) throw new Error('Poppler 压缩包中未找到 pdftoppm.exe，无法启用 pdf2image。');
  const destination = path.join(targetRoot, 'poppler');
  fs.rmSync(destination, { recursive: true, force: true });
  // Copy the directory that actually contains pdftoppm.exe (not its parent
  // `Library` directory), so AIONUI_PDF_POPPLER points at the executable dir.
  fs.cpSync(bin, destination, { recursive: true });
  return path.relative(targetRoot, destination).replace(/\\/g, '/');
}

function writeManifest(targetRoot, popplerRelative) {
  const pythonExe = path.join(targetRoot, 'python.exe');
  const files = {};
  const collect = (dir, relative = '') => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const fullPath = path.join(dir, entry.name);
      const rel = path.join(relative, entry.name).replace(/\\/g, '/');
      if (entry.isDirectory()) collect(fullPath, rel);
      else if (entry.isFile()) files[rel] = sha256(fullPath);
    }
  };
  collect(targetRoot);
  const manifest = {
    schemaVersion: 1,
    platform: 'win32-x64',
    python: {
      version: PYTHON_VERSION,
      executable: 'python.exe',
      source: `https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip`,
    },
    packages: PACKAGE_VERSIONS,
    poppler: { version: POPPLER_VERSION, source: POPPLER_URL, relativeBin: popplerRelative },
    files,
  };
  fs.writeFileSync(MANIFEST_PATH, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`✅ PDF runtime manifest written: ${path.relative(PROJECT_ROOT, MANIFEST_PATH)}`);
}

function main() {
  const { platform, arch, verifyOnly } = parseArgs();
  if (platform !== 'win32' || arch !== 'x64') {
    console.log(`ℹ️  PDF offline runtime currently targets win32-x64 (requested ${platform}-${arch}); skipped.`);
    return;
  }
  if (verifyOnly) {
    run(process.execPath, [path.join(__dirname, 'verify-pdf-runtime.js')]);
    return;
  }

  fs.mkdirSync(RUNTIME_ROOT, { recursive: true });
  if (fs.existsSync(MANIFEST_PATH) && fs.existsSync(path.join(TARGET_ROOT, 'python.exe'))) {
    run(process.execPath, [path.join(__dirname, 'verify-pdf-runtime.js')]);
    console.log('✅ 已存在完整 PDF runtime，跳过重复下载。');
    return;
  }

  const staging = path.join(RUNTIME_ROOT, '.staging');
  fs.rmSync(staging, { recursive: true, force: true });
  fs.mkdirSync(staging, { recursive: true });
  try {
    preparePython(TARGET_ROOT, staging);
    const popplerRelative = preparePoppler(TARGET_ROOT, staging);
    writeManifest(TARGET_ROOT, popplerRelative);
    run(process.execPath, [path.join(__dirname, 'verify-pdf-runtime.js')]);
  } catch (error) {
    fs.rmSync(TARGET_ROOT, { recursive: true, force: true });
    fs.rmSync(MANIFEST_PATH, { force: true });
    throw error;
  } finally {
    fs.rmSync(staging, { recursive: true, force: true });
  }
}

try {
  main();
} catch (error) {
  console.error(`❌ PDF runtime 准备失败：${error.message}`);
  process.exitCode = 1;
}
