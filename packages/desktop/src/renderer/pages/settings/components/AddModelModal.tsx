import type { IProvider } from '@/common/config/storage';
import {
  type ModelImageInputChoice,
  type ModelOpenAiApiModeChoice,
  type ModelThoughtLevelChoice,
  detectModelContextLimit,
  detectModelThoughtSupport,
  supportsOpenAiApiMode,
  updateModelSettings,
} from '@/common/utils/modelCapabilities';
import ModalHOC from '@/renderer/utils/ui/ModalHOC';
import AionModal from '@/renderer/components/base/AionModal';
import { Checkbox, InputNumber, Radio, Select } from '@arco-design/web-react';
import { PreviewOpen } from '@icon-park/react';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import useModeModeList from '@renderer/hooks/agent/useModeModeList';
import {
  isNewApiPlatform,
  NEW_API_PROTOCOL_OPTIONS,
  detectNewApiProtocol,
} from '@/renderer/utils/model/modelPlatforms';

const AddModelModal = ModalHOC<{ data?: IProvider; model?: string; onSubmit: (model: IProvider) => void }>(
  ({ modalProps, data, model: editingModel, onSubmit, modalCtrl }) => {
    const { t } = useTranslation();
    const [models, setModels] = useState<string[]>([]);
    const [modelProtocol, setModelProtocol] = useState<string>('openai');
    const [imageInput, setImageInput] = useState<ModelImageInputChoice>('auto');
    const [openAiApiMode, setOpenAiApiMode] = useState<ModelOpenAiApiModeChoice>('auto');
    const [thoughtLevels, setThoughtLevels] = useState<ModelThoughtLevelChoice[]>([]);
    const [thoughtLevelsConfigured, setThoughtLevelsConfigured] = useState(false);
    const [thoughtLevel, setThoughtLevel] = useState<ModelThoughtLevelChoice>('auto');
    const [contextMode, setContextMode] = useState<'auto' | 'custom'>('auto');
    const [customContextLimit, setCustomContextLimit] = useState<number | undefined>(undefined);
    const isNewApi = isNewApiPlatform(data?.platform ?? '');
    const isEditing = Boolean(editingModel);
    const { data: modelList, isLoading } = useModeModeList(data?.platform, data?.base_url, data?.api_key);
    const existingModels = data?.models || [];
    const showOpenAiApiMode = supportsOpenAiApiMode(data?.platform ?? '', modelProtocol);

    const activeModelName = editingModel || (models.length > 0 ? models[models.length - 1] : '');
    const isReasoningCapable = useMemo(() => {
      return activeModelName ? detectModelThoughtSupport(activeModelName) : false;
    }, [activeModelName]);
    const detectedContextLimit = useMemo(() => {
      return activeModelName ? detectModelContextLimit(activeModelName) : 128000;
    }, [activeModelName]);

    const optionsList = useMemo(() => {
      // 处理新的数据格式，可能包含 fix_base_url
      const fetchedModels = Array.isArray(modelList) ? modelList : modelList?.models || [];
      if (!fetchedModels || !data?.models) return fetchedModels;
      return fetchedModels.map((item) => {
        return { ...item, disabled: data.models.includes(item.value) };
      });
    }, [modelList, data?.models]);

    useEffect(() => {
      if (!modalProps.visible) return;

      setModels([]);
      const settings = editingModel ? data?.model_settings?.[editingModel] : undefined;
      setImageInput(settings?.image_input ?? 'auto');
      setOpenAiApiMode(settings?.openai_api_mode ?? 'auto');

      const savedThoughtLevels = settings?.thought_levels;
      if (savedThoughtLevels && savedThoughtLevels.length > 0) {
        setThoughtLevels(savedThoughtLevels as ModelThoughtLevelChoice[]);
        setThoughtLevelsConfigured(true);
      } else if (Array.isArray(savedThoughtLevels)) {
        setThoughtLevels([]);
        setThoughtLevelsConfigured(true);
      } else if (settings?.thought_level && settings.thought_level !== 'auto') {
        setThoughtLevels([settings.thought_level as ModelThoughtLevelChoice]);
        setThoughtLevelsConfigured(true);
      } else if (editingModel && detectModelThoughtSupport(editingModel)) {
        setThoughtLevels([]);
        setThoughtLevelsConfigured(false);
      } else {
        setThoughtLevels([]);
        setThoughtLevelsConfigured(false);
      }
      setThoughtLevel(settings?.thought_level ?? 'auto');
      setModelProtocol(editingModel ? (data?.model_protocols?.[editingModel] ?? 'openai') : 'openai');

      if (settings?.context_limit && settings.context_limit > 0) {
        setContextMode('custom');
        setCustomContextLimit(settings.context_limit);
      } else {
        setContextMode('auto');
        setCustomContextLimit(undefined);
      }
    }, [data, editingModel, modalProps.visible]);

    const handleConfirm = useCallback(() => {
      if (!data || (!editingModel && !models.length)) return;
      const targetModels = editingModel ? [editingModel] : models;
      const effectiveContextLimit = contextMode === 'auto' ? 'auto' : (customContextLimit ?? 'auto');

      const updatedData: IProvider = {
        ...data,
        models: editingModel ? existingModels : [...existingModels, ...models],
        model_settings: updateModelSettings(
          data.model_settings,
          targetModels,
          imageInput,
          showOpenAiApiMode ? openAiApiMode : 'auto',
          effectiveContextLimit,
          thoughtLevel,
          thoughtLevelsConfigured ? thoughtLevels : undefined
        ),
      };

      // new-api 平台：为每个选中的模型添加协议配置 / new-api platform: add protocol config for every selected model
      if (isNewApi) {
        updatedData.model_protocols = {
          ...data?.model_protocols,
          ...Object.fromEntries(targetModels.map((model) => [model, modelProtocol])),
        };
      }

      onSubmit(updatedData);
      modalCtrl.close();
    }, [
      data,
      editingModel,
      existingModels,
      imageInput,
      isNewApi,
      modelProtocol,
      models,
      onSubmit,
      openAiApiMode,
      modalCtrl,
      showOpenAiApiMode,
      contextMode,
      customContextLimit,
      thoughtLevel,
      thoughtLevels,
      thoughtLevelsConfigured,
    ]);

    return (
      <AionModal
        variant='standard'
        visible={modalProps.visible}
        onCancel={modalCtrl.close}
        header={{ title: t(isEditing ? 'settings.configureModel' : 'settings.addModel'), showClose: true }}
        onOk={handleConfirm}
        okText={t('common.confirm')}
        cancelText={t('common.cancel')}
        okButtonProps={{ disabled: !isEditing && !models.length }}
      >
        <div className='flex flex-col gap-16px'>
          {isEditing ? (
            <div className='space-y-8px'>
              <div className='text-13px font-500 text-t-secondary'>{t('settings.modelName')}</div>
              <div className='text-14px text-t-primary'>{editingModel}</div>
            </div>
          ) : (
            <div className='space-y-8px'>
              <div className='text-13px font-500 text-t-secondary'>{t('settings.addModelPlaceholder')}</div>
              <Select
                mode='multiple'
                showSearch
                options={optionsList}
                loading={isLoading}
                onChange={(value: string[]) => {
                  setModels(value);
                  // new-api 平台：以最后选中的模型推断协议 / new-api: infer protocol from the last picked model
                  if (isNewApi && value.length > 0) setModelProtocol(detectNewApiProtocol(value[value.length - 1]));
                }}
                value={models}
                allowCreate
                placeholder={t('settings.addModelPlaceholder')}
              />
            </div>
          )}

          {/* New API 协议选择 / New API Protocol Selection */}
          {isNewApi && (
            <div className='space-y-8px'>
              <div className='text-13px font-500 text-t-secondary'>{t('settings.modelProtocol')}</div>
              <Select
                value={modelProtocol}
                onChange={setModelProtocol}
                options={NEW_API_PROTOCOL_OPTIONS}
                triggerProps={{ getPopupContainer: (node) => node.parentElement || document.body }}
              />
              <div className='text-11px text-t-secondary leading-4'>{t('settings.modelProtocolTip')}</div>
            </div>
          )}

          <div className='space-y-8px'>
            <div className='flex items-center gap-5px text-13px font-500 text-t-secondary'>
              <PreviewOpen theme='outline' size='14' />
              <span>{t('settings.imageInput')}</span>
            </div>
            <Select
              value={imageInput}
              onChange={(value) => setImageInput(value as ModelImageInputChoice)}
              options={[
                { label: t('settings.imageInputAuto'), value: 'auto' },
                { label: t('settings.imageInputSupported'), value: 'supported' },
                { label: t('settings.imageInputUnsupported'), value: 'unsupported' },
              ]}
            />
            <div className='text-11px text-t-secondary leading-4'>{t('settings.imageInputTip')}</div>
          </div>

          <div className='space-y-8px'>
            <div className='flex items-center justify-between text-13px font-500 text-t-secondary'>
              <span>{t('settings.contextLimit')}</span>
              <Radio.Group
                type='button'
                size='mini'
                value={contextMode}
                onChange={(val) => setContextMode(val)}
              >
                <Radio value='auto'>
                  {t('settings.contextLimitAuto')} ({detectedContextLimit >= 1000000 ? `${(detectedContextLimit / 1000000).toFixed(1)}M` : `${Math.round(detectedContextLimit / 1000)}k`})
                </Radio>
                <Radio value='custom'>{t('settings.contextLimitCustom')}</Radio>
              </Radio.Group>
            </div>
            {contextMode === 'custom' ? (
              <InputNumber
                placeholder={t('settings.contextLimitPlaceholder')}
                value={customContextLimit ?? detectedContextLimit}
                min={1024}
                max={10000000}
                step={1024}
                onChange={(val) => setCustomContextLimit(val)}
                suffix='Tokens'
              />
            ) : (
              <div className='px-12px py-6px rounded bg-bg-2 border border-border-1 text-12px text-t-primary flex items-center justify-between'>
                <span>{detectedContextLimit.toLocaleString()} Tokens</span>
                <span className='text-11px text-t-secondary'>{t('settings.contextLimitAuto')}</span>
              </div>
            )}
            <div className='text-11px text-t-secondary leading-4'>{t('settings.contextLimitTip')}</div>
          </div>

          {showOpenAiApiMode && (
            <div className='space-y-8px'>
              <div className='text-13px font-500 text-t-secondary'>{t('settings.openAiApiMode')}</div>
              <Select
                value={openAiApiMode}
                onChange={(value) => setOpenAiApiMode(value as ModelOpenAiApiModeChoice)}
                options={[
                  { label: t('settings.modelSettingAuto'), value: 'auto' },
                  { label: t('settings.openAiApiModeChatCompletions'), value: 'chat_completions' },
                  { label: t('settings.openAiApiModeResponses'), value: 'responses' },
                ]}
              />
              <div className='text-11px text-t-secondary leading-4'>{t('settings.openAiApiModeTip')}</div>
            </div>
          )}

          <div className='space-y-8px'>
            <div className='text-13px font-500 text-t-secondary'>
              {t('settings.thoughtLevel', '推理强度 / 思考模式 (Reasoning Effort)')}
            </div>
            <div className='space-y-6px'>
              <div className='text-12px text-t-secondary'>
                {t('settings.supportedThoughtLevels', '勾选该模型支持的思考强度 (聊天时可在输入框随时切换):')}
              </div>
              <Checkbox.Group
                options={[
                  { label: t('agent.thoughtLevel.off', '关闭 (Off)'), value: 'off' },
                  { label: t('agent.thoughtLevel.low', '低强度 (Low)'), value: 'low' },
                  { label: t('agent.thoughtLevel.medium', '中强度 (Medium)'), value: 'medium' },
                  { label: t('agent.thoughtLevel.high', '高强度 (High)'), value: 'high' },
                ]}
                value={thoughtLevels}
                onChange={(vals) => {
                  const nextLevels = vals as ModelThoughtLevelChoice[];
                  setThoughtLevels(nextLevels);
                  setThoughtLevelsConfigured(true);
                  if (thoughtLevel !== 'auto' && !nextLevels.includes(thoughtLevel)) {
                    setThoughtLevel('auto');
                  }
                }}
              />
            </div>
            {thoughtLevels.length > 0 && (
              <div className='space-y-6px pt-4px'>
                <div className='text-12px text-t-secondary'>
                  {t('settings.defaultThoughtLevel', '默认思考强度:')}
                </div>
                <Select
                  value={thoughtLevel}
                  onChange={(val) => setThoughtLevel(val as ModelThoughtLevelChoice)}
                  options={[
                    { label: t('settings.modelSettingAuto', '自动 (Auto)'), value: 'auto' },
                    ...thoughtLevels.map((lvl) => ({
                      label: t(`agent.thoughtLevel.${lvl}`, lvl),
                      value: lvl,
                    })),
                  ]}
                />
              </div>
            )}
            <div className='text-11px text-t-secondary leading-4'>
              {isReasoningCapable
                ? t('settings.thoughtLevelSupportedTip', '该模型支持深度推理。勾选支持的强度后，在聊天输入框下方即可随时切换本次发送的推理强度。')
                : t('settings.thoughtLevelGeneralTip', '仅适用于支持思考/推理的模型 (如 o1/o3/DeepSeek-R1 等)。勾选后可在输入框下方随时切换。')}
            </div>
          </div>

          {!isEditing && models.length > 1 && (
            <div className='text-11px text-t-secondary leading-4'>{t('settings.modelSettingsApplyToSelected')}</div>
          )}
        </div>
      </AionModal>
    );
  }
);

export default AddModelModal;
