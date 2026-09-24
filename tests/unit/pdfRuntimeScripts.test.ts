import fs from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const repoRoot = path.resolve(__dirname, '../..');
const prepareScript = fs.readFileSync(path.join(repoRoot, 'scripts/prepare-pdf-runtime.js'), 'utf8');
const verifyScript = fs.readFileSync(path.join(repoRoot, 'scripts/verify-pdf-runtime.js'), 'utf8');
const pdfSkill = fs.readFileSync(
  path.join(repoRoot, 'AionCore/crates/aionui-app/assets/builtin-skills/pdf/SKILL.md'),
  'utf8'
);
const renderScript = fs.readFileSync(
  path.join(repoRoot, 'AionCore/crates/aionui-app/assets/builtin-skills/pdf/scripts/pdf_to_png.py'),
  'utf8'
);
const envScript = fs.readFileSync(
  path.join(repoRoot, 'AionCore/crates/aionui-app/assets/builtin-skills/pdf/scripts/check_env.ps1'),
  'utf8'
);

describe('Win7 PDF runtime contract', () => {
  it('bundles typing_extensions and does not require Tesseract', () => {
    expect(prepareScript).toContain("typing_extensions: '4.13.2'");
    expect(verifyScript).toContain("'typing_extensions'");
    expect(verifyScript).toContain('`${name}.py`');
    expect(verifyScript).not.toContain('缺少 Tesseract');
    expect(verifyScript).not.toContain('缺少 OCR 语言包');
  });

  it('documents the Poppler plus vision-model path for scanned PDFs', () => {
    expect(pdfSkill).toContain('send the resulting PNG files as image attachments');
    expect(pdfSkill).toContain('Tesseract is an optional legacy fallback');
  });

  it('keeps the helper scripts compatible with the bundled runtime', () => {
    expect(renderScript).toContain("'pdftoppm.exe' if os.name == 'nt' else 'pdftoppm'");
    expect(renderScript).toContain("'--first-page'");
    expect(envScript).toContain('$env:AIONUI_PDF_RUNTIME');
    expect(envScript).not.toContain('Invoke-WebRequest');
    expect(envScript).not.toContain('Get-FileHash');
  });
});
