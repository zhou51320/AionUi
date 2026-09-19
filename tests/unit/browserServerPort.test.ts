import { describe, expect, it } from 'vitest';
import {
  buildMcpSpawnCommand,
  resolveBridgeToken,
  resolveBrowserUrl,
} from '../../packages/desktop/src/process/resources/builtinMcp/browserServerPort';

describe('builtin browser MCP launch configuration', () => {
  it('rejects a missing or invalid CDP port instead of guessing a browser', () => {
    expect(resolveBrowserUrl({ env: {} })).toBeNull();
    expect(resolveBrowserUrl({ env: { AIONUI_CDP_ACTIVE_PORT: '0' } })).toBeNull();
    expect(resolveBrowserUrl({ env: { AIONUI_CDP_ACTIVE_PORT: '65536' } })).toBeNull();
    expect(resolveBrowserUrl({ env: { AIONUI_CDP_ACTIVE_PORT: '9230' } })).toBe('http://127.0.0.1:9230');
  });

  it('requires a non-empty bridge token', () => {
    expect(resolveBridgeToken({ env: {} })).toBeNull();
    expect(resolveBridgeToken({ env: { AIONUI_CDP_BRIDGE_TOKEN: '  ' } })).toBeNull();
    expect(resolveBridgeToken({ env: { AIONUI_CDP_BRIDGE_TOKEN: 'token-1' } })).toBe('token-1');
  });

  it('routes Windows npx.cmd through cmd.exe without shell concatenation', () => {
    expect(
      buildMcpSpawnCommand({
        platform: 'win32',
        version: '0.16.0',
        browserUrl: 'http://127.0.0.1:9230',
      })
    ).toEqual({
      command: 'cmd.exe',
      args: ['/c', 'npx', '-y', 'chrome-devtools-mcp@0.16.0', '--browser-url', 'http://127.0.0.1:9230'],
    });
  });

  it('uses the direct npx command on Unix', () => {
    expect(
      buildMcpSpawnCommand({
        platform: 'linux',
        version: '0.16.0',
        browserUrl: 'http://127.0.0.1:9230',
      })
    ).toEqual({
      command: 'npx',
      args: ['-y', 'chrome-devtools-mcp@0.16.0', '--browser-url', 'http://127.0.0.1:9230'],
    });
  });
});
