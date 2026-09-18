/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { ipcBridge } from '@/common';
import { isElectronDesktop } from '@/renderer/utils/platform';
import { Message } from '@arco-design/web-react';
import JSZip from 'jszip';

export interface ExportParams {
  type: 'skill' | 'assistant' | 'plugin';
  name: string;
  location?: string;
  data?: unknown;
}

export async function exportResourceArchive(params: ExportParams): Promise<void> {
  const { type, name, location, data } = params;
  try {
    if (isElectronDesktop() && ipcBridge.market?.exportResource) {
      const res = await ipcBridge.market.exportResource.invoke({
        type,
        name,
        location,
        data,
      });
      if (res.canceled) {
        return;
      }
      if (res.success) {
        Message.success(`成功导出归档包${res.filePath ? `：${res.filePath}` : ''}`);
      } else {
        Message.error(res.error || '导出失败');
      }
      return;
    }

    // WebUI fallback
    const zip = new JSZip();
    if (type === 'assistant') {
      zip.file('assistant.json', JSON.stringify(data || { name, id: name }, null, 2));
    } else if (type === 'plugin') {
      const serverObj = data as any;
      const config = {
        mcpServers: {
          [serverObj?.name || name]: {
            command: serverObj?.transport?.command,
            args: serverObj?.transport?.args,
            env: serverObj?.transport?.env,
            url: serverObj?.transport?.url,
          },
        },
      };
      zip.file('mcp.json', JSON.stringify(config, null, 2));
    } else {
      zip.file('SKILL.md', `---\nname: ${name}\ndescription: ${name}\n---\n\n# ${name}\n`);
    }

    const blob = await zip.generateAsync({ type: 'blob' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${name.replace(/[\/:*?"<>|]/g, '_')}.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    Message.success('已开始下载归档包');
  } catch (err: any) {
    Message.error(err.message || '导出失败');
  }
}
