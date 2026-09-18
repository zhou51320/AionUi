import React, { useCallback, useEffect, useState } from 'react';
import { Button, Typography, Radio, Message, Tag } from '@arco-design/web-react';
import { IconDownload, IconRefresh } from '@arco-design/web-react/icon';
import { useTranslation } from 'react-i18next';
import AionModal from '@/renderer/components/base/AionModal';
import { getSelfHostedBaseUrl, getSelfHostedToken } from '@/common/config/selfHosted';

interface AgentHubModalProps {
  visible: boolean;
  onCancel: () => void;
}

interface MarketItem {
  id: number;
  filename: string;
  category: 'assistant' | 'plugin' | 'skill' | string;
  description: string;
  file_size: number;
  download_count: number;
  created_at: string;
}

export const AgentHubModal: React.FC<AgentHubModalProps> = ({ visible, onCancel }) => {
  const { t } = useTranslation();
  const [category, setCategory] = useState<string>('all');
  const [files, setFiles] = useState<MarketItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const fetchFiles = useCallback(async (cat: string) => {
    setLoading(true);
    try {
      const baseUrl = getSelfHostedBaseUrl();
      const token = getSelfHostedToken();
      const query = cat && cat !== 'all' ? `?category=${encodeURIComponent(cat)}` : '';
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const response = await fetch(`${baseUrl}/api/market/files${query}`, { headers });
      if (response.ok) {
        const json = await response.json();
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
  }, []);

  useEffect(() => {
    if (visible) {
      void fetchFiles(category);
    }
  }, [visible, category, fetchFiles]);

  const handleDownload = async (item: MarketItem) => {
    setDownloadingId(item.id);
    try {
      const baseUrl = getSelfHostedBaseUrl();
      const token = getSelfHostedToken();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const response = await fetch(`${baseUrl}/api/market/download/${item.id}`, { headers });

      if (!response.ok) {
        Message.error(t('common.downloadFailed', { defaultValue: '下载失败' }));
        return;
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = item.filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      Message.success(t('common.downloadSuccess', { defaultValue: '文件下载成功' }));
      // Refresh list to update download count
      void fetchFiles(category);
    } catch (err) {
      console.error('Download error:', err);
      Message.error(t('common.downloadFailed', { defaultValue: '下载失败' }));
    } finally {
      setDownloadingId(null);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getCategoryTag = (cat: string) => {
    switch (cat) {
      case 'assistant':
        return <Tag color='blue'>🤖 助手</Tag>;
      case 'plugin':
        return <Tag color='green'>🔌 插件</Tag>;
      case 'skill':
        return <Tag color='purple'>⚡ 技能</Tag>;
      default:
        return <Tag color='gray'>{cat}</Tag>;
    }
  };

  return (
    <AionModal
      variant='standard'
      header={{
        title: t('settings.agentManagement.selfHostedMarket', { defaultValue: '自托管应用市场' }),
        showClose: true,
      }}
      visible={visible}
      onCancel={onCancel}
      footer={null}
      autoFocus={false}
      focusLock={true}
      style={{ width: 880, maxWidth: '96vw' }}
    >
      <div className='flex flex-col gap-16px'>
        <div className='flex items-center justify-between'>
          <Radio.Group
            type='button'
            value={category}
            onChange={(val) => setCategory(val)}
            options={[
              { label: '全部资源', value: 'all' },
              { label: '助手 (Assistant)', value: 'assistant' },
              { label: '插件 (Plugin)', value: 'plugin' },
              { label: '技能 (Skill)', value: 'skill' },
            ]}
          />
          <Button
            size='small'
            icon={<IconRefresh />}
            onClick={() => void fetchFiles(category)}
            loading={loading}
          >
            {t('common.refresh', { defaultValue: '刷新' })}
          </Button>
        </div>

        {loading ? (
          <div className='flex items-center justify-center py-48px'>
            <Typography.Text type='secondary'>
              {t('common.loading', { defaultValue: '正在加载市场资源...' })}
            </Typography.Text>
          </div>
        ) : files.length === 0 ? (
          <div className='flex flex-col items-center justify-center py-48px text-center gap-8px'>
            <Typography.Text type='secondary' className='text-14px'>
              {t('settings.agentManagement.marketEmpty', {
                defaultValue: '暂无可用资源包。管理员可在自托管后台 (/admin) 上传 ZIP 包分发给客户端。',
              })}
            </Typography.Text>
          </div>
        ) : (
          <div className='grid grid-cols-1 gap-12px sm:grid-cols-2 md:grid-cols-3 max-h-[480px] overflow-y-auto p-2px'>
            {files.map((file) => (
              <div
                key={file.id}
                className='flex flex-col justify-between rounded-12px border border-solid border-[var(--color-border-2)] bg-[var(--color-bg-2)] p-12px transition-colors hover:border-[var(--color-border-3)]'
              >
                <div>
                  <div className='flex items-center justify-between mb-8px'>
                    {getCategoryTag(file.category)}
                    <Typography.Text type='secondary' className='text-11px'>
                      {formatFileSize(file.file_size)}
                    </Typography.Text>
                  </div>
                  <Typography.Text bold className='block mb-4px text-13px line-clamp-1'>
                    {file.filename}
                  </Typography.Text>
                  <Typography.Text
                    type='secondary'
                    className='block text-11px line-clamp-2 min-h-32px mb-8px text-t-secondary'
                  >
                    {file.description || '暂无描述'}
                  </Typography.Text>
                </div>

                <div className='flex items-center justify-between pt-8px border-t border-dashed border-[var(--color-border-1)]'>
                  <Typography.Text type='secondary' className='text-11px'>
                    下载 {file.download_count} 次
                  </Typography.Text>
                  <Button
                    type='primary'
                    size='mini'
                    icon={<IconDownload />}
                    loading={downloadingId === file.id}
                    onClick={() => void handleDownload(file)}
                  >
                    {t('common.download', { defaultValue: '下载' })}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AionModal>
  );
};
