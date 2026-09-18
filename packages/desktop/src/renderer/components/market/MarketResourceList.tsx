/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Input, Message, Tag, Spin, Empty, Card, Dropdown, Menu } from '@arco-design/web-react';
import { Download, Refresh, Search, FolderCode, Lightning, Toolkit, User, Down } from '@icon-park/react';
import { useTranslation } from 'react-i18next';
import { ipcBridge } from '@/common';
import { getSelfHostedBaseUrl, getSelfHostedToken } from '@/common/config/selfHosted';

export interface MarketFileItem {
  id: number;
  filename: string;
  category: 'assistant' | 'skill' | 'plugin' | 'mcp' | string;
  description: string;
  file_size: number;
  download_count: number;
  created_at: string;
}

interface MarketResourceListProps {
  category: 'assistant' | 'skill' | 'plugin' | 'mcp' | 'all';
  onInstalled?: () => void;
  className?: string;
}

function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

export const MarketResourceList: React.FC<MarketResourceListProps> = ({
  category,
  onInstalled,
  className = '',
}) => {
  const { t } = useTranslation();
  const [files, setFiles] = useState<MarketFileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    try {
      const baseUrl = getSelfHostedBaseUrl();
      const token = getSelfHostedToken();
      const query = category && category !== 'all' ? `?category=${encodeURIComponent(category)}` : '';
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(`${baseUrl}/api/market/files${query}`, { headers });
      if (res.ok) {
        const json = await res.json();
        if (json.code === 0 && Array.isArray(json.data)) {
          setFiles(json.data);
        } else {
          setFiles([]);
        }
      } else {
        setFiles([]);
      }
    } catch (err) {
      console.error('Failed to fetch market files:', err);
      setFiles([]);
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    void fetchFiles();
  }, [fetchFiles]);

  const filteredFiles = useMemo(() => {
    if (!searchQuery.trim()) return files;
    const q = searchQuery.toLowerCase();
    return files.filter(
      (f) =>
        f.filename.toLowerCase().includes(q) ||
        (f.description && f.description.toLowerCase().includes(q))
    );
  }, [files, searchQuery]);

  const handleInstall = async (item: MarketFileItem) => {
    setDownloadingId(item.id);
    try {
      const baseUrl = getSelfHostedBaseUrl();
      const token = getSelfHostedToken();
      const downloadUrl = `${baseUrl}/api/market/download/${item.id}?token=${encodeURIComponent(token || '')}`;

      const isElectron = typeof window !== 'undefined' && Boolean((window as unknown as { electronAPI?: unknown }).electronAPI);

      if (isElectron && ipcBridge.market?.installResource) {
        const result = await ipcBridge.market.installResource.invoke({
          id: item.id,
          filename: item.filename,
          category: item.category || category,
          downloadUrl,
          token: token || undefined,
        });

        if (result.success) {
          Message.success(result.message || t('market.installSuccess', { defaultValue: `安装成功: ${item.filename}` }));
          onInstalled?.();
        } else {
          Message.error(result.message || t('market.installFailed', { defaultValue: '安装失败' }));
        }
      } else {
        // Fallback for pure browser environment
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = item.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        Message.success(t('market.downloadStarted', { defaultValue: `开始下载: ${item.filename}` }));
        onInstalled?.();
      }
    } catch (err: unknown) {
      console.error('Install failed:', err);
      const errMsg = err instanceof Error ? err.message : String(err);
      Message.error(errMsg || t('market.installFailed', { defaultValue: '安装失败' }));
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDownloadOnly = (item: MarketFileItem) => {
    try {
      const baseUrl = getSelfHostedBaseUrl();
      const token = getSelfHostedToken();
      const downloadUrl = `${baseUrl}/api/market/download/${item.id}?token=${encodeURIComponent(token || '')}`;

      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = item.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      Message.success(t('market.downloadStarted', { defaultValue: `开始下载: ${item.filename}` }));
    } catch (err: unknown) {
      console.error('Download failed:', err);
      Message.error(t('market.downloadFailed', { defaultValue: '下载失败' }));
    }
  };

  const getCategoryIcon = (cat: string) => {
    switch (cat) {
      case 'assistant':
        return <User theme='outline' size={16} />;
      case 'skill':
        return <Lightning theme='outline' size={16} />;
      case 'plugin':
      case 'mcp':
        return <Toolkit theme='outline' size={16} />;
      default:
        return <FolderCode theme='outline' size={16} />;
    }
  };

  const getCategoryLabel = (cat: string) => {
    switch (cat) {
      case 'assistant':
        return t('settings.assistants', { defaultValue: '助手' });
      case 'skill':
        return t('settings.skills', { defaultValue: '技能' });
      case 'plugin':
      case 'mcp':
        return t('settings.tools', { defaultValue: '工具插件' });
      default:
        return cat;
    }
  };

  return (
    <div className={`flex flex-col gap-16px w-full h-full ${className}`}>
      {/* Search and Action Bar */}
      <div className='flex items-center justify-between gap-12px'>
        <Input
          prefix={<Search />}
          placeholder={t('market.searchPlaceholder', { defaultValue: '搜索市场资源...' })}
          value={searchQuery}
          onChange={setSearchQuery}
          allowClear
          className='max-w-320px'
        />
        <Button
          type='secondary'
          icon={<Refresh />}
          loading={loading}
          onClick={fetchFiles}
        >
          {t('common.refresh', { defaultValue: '刷新' })}
        </Button>
      </div>

      {/* Content Area */}
      <Spin loading={loading} className='w-full flex-1'>
        {filteredFiles.length === 0 ? (
          <div className='flex flex-col items-center justify-center py-60px bg-fill-1 rd-12px border border-border-2 border-dashed'>
            <Empty description={t('market.noResources', { defaultValue: '暂无服务器上传的资源' })} />
          </div>
        ) : (
          <div className='grid grid-cols-1 md:grid-cols-2 gap-12px'>
            {filteredFiles.map((item) => (
              <Card
                key={item.id}
                className='rd-12px border border-border-2 hover:border-primary-5 transition-all shadow-sm'
                bodyStyle={{ padding: '16px' }}
              >
                <div className='flex items-start justify-between gap-8px mb-8px'>
                  <div className='flex items-center gap-8px min-w-0 flex-1'>
                    <div className='flex items-center justify-center w-32px h-32px rd-8px bg-primary-1 text-primary-6 shrink-0'>
                      {getCategoryIcon(item.category)}
                    </div>
                    <div className='min-w-0 flex-1'>
                      <div className='font-semibold text-14px text-t-primary truncate' title={item.filename}>
                        {item.filename}
                      </div>
                      <div className='text-11px text-t-tertiary mt-2px'>
                        {item.created_at || 'Recently added'}
                      </div>
                    </div>
                  </div>
                  <Tag color='arcoblue' size='small' className='shrink-0'>
                    {getCategoryLabel(item.category)}
                  </Tag>
                </div>

                <p className='text-12px text-t-secondary line-clamp-2 min-h-36px mb-12px leading-relaxed'>
                  {item.description || t('market.noDescription', { defaultValue: '暂无描述信息' })}
                </p>

                <div className='flex items-center justify-between pt-8px border-t border-border-1 text-12px text-t-tertiary'>
                  <div className='flex items-center gap-12px'>
                    <span>{formatBytes(item.file_size)}</span>
                    <span>{t('market.downloadCount', { count: item.download_count, defaultValue: `下载: ${item.download_count}` })}</span>
                  </div>
                  <div className='flex items-center gap-6px'>
                    <Button
                      type='primary'
                      size='small'
                      icon={<Download />}
                      loading={downloadingId === item.id}
                      onClick={() => handleInstall(item)}
                      className='rd-6px'
                    >
                      {downloadingId === item.id
                        ? t('market.installing', { defaultValue: '正在安装...' })
                        : t('market.install', { defaultValue: '安装' })}
                    </Button>
                    <Dropdown
                      position='br'
                      droplist={
                        <Menu>
                          <Menu.Item key='download' onClick={() => handleDownloadOnly(item)}>
                            <div className='flex items-center gap-6px text-12px'>
                              <Download theme='outline' size={14} />
                              <span>{t('market.downloadSource', { defaultValue: '仅下载源文件' })}</span>
                            </div>
                          </Menu.Item>
                        </Menu>
                      }
                    >
                      <Button
                        type='secondary'
                        size='small'
                        icon={<Down />}
                        className='rd-6px px-4px'
                      />
                    </Dropdown>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </Spin>
    </div>
  );
};

export default MarketResourceList;
