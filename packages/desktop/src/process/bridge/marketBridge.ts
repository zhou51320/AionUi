/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { app, dialog } from 'electron';
import fs from 'fs';
import path from 'path';
import yauzl from 'yauzl';
import JSZip from 'jszip';
import { ipcBridge } from '@/common';

function extractZip(zipFilePath: string, targetDir: string): Promise<string[]> {
  return new Promise((resolve, reject) => {
    const extractedFiles: string[] = [];
    yauzl.open(zipFilePath, { lazyEntries: true }, (err, zipfile) => {
      if (err || !zipfile) return reject(err || new Error('Failed to open zip archive'));
      zipfile.readEntry();
      zipfile.on('entry', (entry) => {
        const normalized = entry.fileName.replace(/\\/g, '/');
        if (normalized.includes('..')) {
          zipfile.readEntry();
          return;
        }
        const fullPath = path.join(targetDir, normalized);
        if (normalized.endsWith('/')) {
          fs.mkdirSync(fullPath, { recursive: true });
          zipfile.readEntry();
        } else {
          fs.mkdirSync(path.dirname(fullPath), { recursive: true });
          zipfile.openReadStream(entry, (streamErr, readStream) => {
            if (streamErr || !readStream) return reject(streamErr || new Error('Failed to read entry'));
            const writeStream = fs.createWriteStream(fullPath);
            readStream.pipe(writeStream);
            writeStream.on('finish', () => {
              extractedFiles.push(fullPath);
              zipfile.readEntry();
            });
            writeStream.on('error', reject);
          });
        }
      });
      zipfile.on('end', () => resolve(extractedFiles));
      zipfile.on('error', reject);
    });
  });
}

async function downloadToTemp(downloadUrl: string, filename: string, token?: string): Promise<string> {
  const tempDir = path.join(app.getPath('temp'), 'aionui-market');
  await fs.promises.mkdir(tempDir, { recursive: true });
  const ext = path.extname(filename) || '.zip';
  const base = path.basename(filename, ext);
  const destPath = path.join(tempDir, `${base}_${Date.now()}${ext}`);

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(downloadUrl, { headers });
  if (!response.ok) {
    throw new Error(`下载失败，服务端返回 HTTP ${response.status}`);
  }

  const buffer = Buffer.from(await response.arrayBuffer());
  await fs.promises.writeFile(destPath, buffer);
  return destPath;
}

export function initMarketBridge(): void {
  ipcBridge.market.installResource.provider(async ({ filename, category, downloadUrl, token }) => {
    let tempFilePath = '';
    try {
      tempFilePath = await downloadToTemp(downloadUrl, filename, token);
      const isZip = tempFilePath.endsWith('.zip');
      const isJson = tempFilePath.endsWith('.json');

      if (category === 'skill') {
        // Skill: AionCore's /api/skills/import natively handles .zip and directory paths
        const result = await ipcBridge.fs.importSkills.invoke({ skill_path: tempFilePath });
        if (result.failed && result.failed.length > 0 && (!result.skill_names || result.skill_names.length === 0)) {
          throw new Error(`技能导入失败: ${result.failed[0]?.code || '格式不正确'}`);
        }
        const name = result.skill_name || result.skill_names?.[0] || filename;
        return {
          success: true,
          message: `技能「${name}」已成功安装！`,
          data: result,
        };
      } else if (category === 'assistant') {
        // Assistant
        let assistantData: unknown = null;
        if (isJson) {
          const raw = await fs.promises.readFile(tempFilePath, 'utf-8');
          assistantData = JSON.parse(raw);
        } else if (isZip) {
          const extractDir = path.join(app.getPath('temp'), `aion_asst_${Date.now()}`);
          await fs.promises.mkdir(extractDir, { recursive: true });
          const files = await extractZip(tempFilePath, extractDir);
          const jsonFile = files.find((f) => f.endsWith('.json'));
          if (jsonFile) {
            const raw = await fs.promises.readFile(jsonFile, 'utf-8');
            assistantData = JSON.parse(raw);
          }
          try {
            await fs.promises.rm(extractDir, { recursive: true, force: true });
          } catch {}
        }

        if (!assistantData) {
          throw new Error('未在助手中找到有效的 JSON 配置文件');
        }

        // Import into assistants
        const dataObj = assistantData as Record<string, unknown>;
        if (Array.isArray(assistantData)) {
          await ipcBridge.assistants.import.invoke({ assistants: assistantData });
        } else if (Array.isArray(dataObj.assistants)) {
          await ipcBridge.assistants.import.invoke({ assistants: dataObj.assistants as any });
        } else if (typeof dataObj.name === 'string') {
          try {
            await ipcBridge.assistants.import.invoke({ assistants: [dataObj as any] });
          } catch {
            await ipcBridge.assistants.create.invoke(dataObj as any);
          }
        } else {
          throw new Error('助手配置文件缺少 name 字段或 assistants 列表');
        }

        return {
          success: true,
          message: `智能体助手「${(dataObj.name as string) || filename}」安装成功！`,
          data: assistantData,
        };
      } else if (category === 'mcp' || category === 'plugin') {
        // MCP / Plugin
        if (isJson) {
          const raw = await fs.promises.readFile(tempFilePath, 'utf-8');
          const json = JSON.parse(raw);
          let serversToImport: any[] = [];

          if (json.mcpServers && typeof json.mcpServers === 'object') {
            serversToImport = Object.entries(json.mcpServers).map(([name, val]: [string, any]) => ({
              name,
              description: val.description || name,
              transport: val.url
                ? { type: 'sse', url: val.url, headers: val.headers || {} }
                : {
                    type: 'stdio',
                    command: val.command || 'node',
                    args: val.args || [],
                    env: val.env || {},
                  },
              original_json: JSON.stringify(val),
              builtin: false,
              enabled: true,
            }));
          } else if (Array.isArray(json)) {
            serversToImport = json;
          } else if (json.name) {
            serversToImport = [json];
          }

          if (serversToImport.length === 0) {
            throw new Error('未在 JSON 中识别到有效的 MCP 服务配置');
          }

          const imported = await ipcBridge.mcpService.importServers.invoke({ servers: serversToImport });
          return {
            success: true,
            message: `MCP 服务插件「${filename}」安装成功！`,
            data: imported,
          };
        } else if (isZip) {
          const baseName = path.parse(filename).name;
          const targetDir = path.join(app.getPath('userData'), 'mcp-servers', baseName);
          await fs.promises.mkdir(targetDir, { recursive: true });
          const files = await extractZip(tempFilePath, targetDir);

          const mcpJsonPath = path.join(targetDir, 'mcp.json');
          const pkgJsonPath = path.join(targetDir, 'package.json');
          let serverName = baseName;
          let transport: any = null;

          if (fs.existsSync(mcpJsonPath)) {
            const mcpConf = JSON.parse(await fs.promises.readFile(mcpJsonPath, 'utf-8'));
            if (mcpConf.mcpServers) {
              const entries = Object.entries(mcpConf.mcpServers);
              if (entries.length > 0) {
                const [n, c]: [string, any] = entries[0];
                serverName = n;
                transport = c.url
                  ? { type: 'sse', url: c.url, headers: c.headers || {} }
                  : {
                      type: 'stdio',
                      command: c.command,
                      args: (c.args || []).map((arg: string) =>
                        arg.startsWith('./') || !path.isAbsolute(arg) ? path.resolve(targetDir, arg) : arg
                      ),
                      env: c.env || {},
                    };
              }
            } else if (mcpConf.command) {
              serverName = mcpConf.name || baseName;
              transport = {
                type: 'stdio',
                command: mcpConf.command,
                args: (mcpConf.args || []).map((arg: string) =>
                  arg.startsWith('./') || !path.isAbsolute(arg) ? path.resolve(targetDir, arg) : arg
                ),
                env: mcpConf.env || {},
              };
            }
          } else if (fs.existsSync(pkgJsonPath)) {
            const pkg = JSON.parse(await fs.promises.readFile(pkgJsonPath, 'utf-8'));
            serverName = pkg.name || baseName;
            const mainFile = path.join(targetDir, pkg.main || 'index.js');
            const isWin = process.platform === 'win32';
            transport = {
              type: 'stdio',
              command: isWin ? process.execPath : 'node',
              args: [mainFile],
              env: isWin ? { ELECTRON_RUN_AS_NODE: '1' } : {},
            };
          }

          if (transport) {
            await ipcBridge.mcpService.importServers.invoke({
              servers: [
                {
                  name: serverName,
                  description: `Market MCP Server: ${serverName}`,
                  transport,
                  original_json: undefined,
                  builtin: false,
                },
              ],
            });
          }

          return {
            success: true,
            message: `MCP 插件「${serverName}」安装解压完成！`,
            data: { targetDir, filesCount: files.length },
          };
        } else {
          throw new Error('不支持的 MCP 文件格式');
        }
      } else {
        throw new Error(`未知的资源分类: ${category}`);
      }
    } finally {
      if (tempFilePath && fs.existsSync(tempFilePath)) {
        try {
          await fs.promises.unlink(tempFilePath);
        } catch {}
      }
    }
  });

  // Export resource archive
  ipcBridge.market.exportResource.provider(async (params) => {
    const { type, name, location, data } = params;
    try {
      const zip = new JSZip();

      if (type === 'skill') {
        let resolvedLoc = location;
        if (!resolvedLoc || !fs.existsSync(resolvedLoc)) {
          const home = app.getPath('home');
          const cand1 = path.join(home, '.aionui', 'skills', name);
          const cand2 = path.join(app.getPath('userData'), 'skills', name);
          if (fs.existsSync(cand1)) resolvedLoc = cand1;
          else if (fs.existsSync(cand2)) resolvedLoc = cand2;
        }

        if (resolvedLoc && fs.existsSync(resolvedLoc)) {
          const stat = await fs.promises.stat(resolvedLoc);
          if (stat.isDirectory()) {
            await addDirectoryToZip(zip, resolvedLoc);
          } else if (stat.isFile()) {
            const fileData = await fs.promises.readFile(resolvedLoc);
            zip.file(path.basename(resolvedLoc), fileData);
          }
        } else {
          zip.file('SKILL.md', `---\nname: ${name}\ndescription: ${name}\n---\n\n# ${name}\n`);
        }
      } else if (type === 'assistant') {
        const assistantData = data || { name, id: name };
        zip.file('assistant.json', JSON.stringify(assistantData, null, 2));
      } else if (type === 'plugin') {
        const mcpDir = path.join(app.getPath('userData'), 'mcp-servers', name);
        if (fs.existsSync(mcpDir)) {
          await addDirectoryToZip(zip, mcpDir);
        }
        const serverObj = data as any;
        if (serverObj) {
          const config = {
            mcpServers: {
              [serverObj.name || name]: {
                command: serverObj.transport?.command,
                args: serverObj.transport?.args,
                env: serverObj.transport?.env,
                url: serverObj.transport?.url,
              },
            },
          };
          zip.file('mcp.json', JSON.stringify(config, null, 2));
        }
      }

      const zipBuffer = await zip.generateAsync({ type: 'nodebuffer' });
      const safeName = (name || type).replace(/[\\/:*?"<>|]/g, '_');

      const { canceled, filePath } = await dialog.showSaveDialog({
        title: `导出 ${type === 'skill' ? '技能' : type === 'assistant' ? '助手' : '插件'} 归档包`,
        defaultPath: `${safeName}.zip`,
        filters: [{ name: 'ZIP Archive', extensions: ['zip'] }],
      });

      if (canceled || !filePath) {
        return { success: false, canceled: true };
      }

      await fs.promises.writeFile(filePath, zipBuffer);
      return { success: true, filePath };
    } catch (err: any) {
      return { success: false, error: err.message || String(err) };
    }
  });
}

async function addDirectoryToZip(zip: JSZip, dirPath: string, zipPrefix = ''): Promise<void> {
  const entries = await fs.promises.readdir(dirPath, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    const relZipPath = zipPrefix ? `${zipPrefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) {
      const folderZip = zip.folder(entry.name);
      if (folderZip) {
        await addDirectoryToZip(folderZip, fullPath, relZipPath);
      }
    } else if (entry.isFile()) {
      const fileData = await fs.promises.readFile(fullPath);
      zip.file(entry.name, fileData);
    }
  }
}
