/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import type { ModelThoughtLevel } from '@/common/config/storage';
import { RuntimeSelectorCheckedItem } from '@/renderer/components/agent/runtimeSelectorOptions';
import { iconColors } from '@/renderer/styles/colors';
import { Button, Dropdown, Menu } from '@arco-design/web-react';
import { Brain, Down } from '@icon-park/react';
import classNames from 'classnames';
import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

export interface ReasoningEffortSelectorProps {
  value?: ModelThoughtLevel | string;
  levels: ModelThoughtLevel[];
  onChange: (level: ModelThoughtLevel) => void | Promise<unknown>;
  disabled?: boolean;
  compact?: boolean;
  isMobileHeaderCompact?: boolean;
  className?: string;
}

const ReasoningEffortSelector: React.FC<ReasoningEffortSelectorProps> = ({
  value,
  levels,
  onChange,
  disabled = false,
  compact = false,
  isMobileHeaderCompact = false,
  className,
}) => {
  const { t } = useTranslation();

  const getLevelLabel = useMemo(() => {
    return (lvl: string) => {
      switch (lvl) {
        case 'off':
          return t('agent.thoughtLevel.off', '关闭 (Off)');
        case 'low':
          return t('agent.thoughtLevel.low', '低强度 (Low)');
        case 'medium':
          return t('agent.thoughtLevel.medium', '中强度 (Medium)');
        case 'high':
          return t('agent.thoughtLevel.high', '高强度 (High)');
        case 'xhigh':
          return t('agent.thoughtLevel.xhigh', '高强度 (XHigh)');
        default:
          return lvl;
      }
    };
  }, [t]);

  const getLevelShortLabel = useMemo(() => {
    return (lvl: string) => {
      switch (lvl) {
        case 'off':
          return t('agent.thoughtLevel.offShort', '关');
        case 'low':
          return t('agent.thoughtLevel.lowShort', '低');
        case 'medium':
          return t('agent.thoughtLevel.mediumShort', '中');
        case 'high':
          return t('agent.thoughtLevel.highShort', '高');
        case 'xhigh':
          return t('agent.thoughtLevel.highShort', '高');
        default:
          return lvl;
      }
    };
  }, [t]);

  if (!levels || levels.length === 0) {
    return null;
  }

  // Determine current effective value
  const effectiveValue = (value && levels.includes(value as ModelThoughtLevel))
    ? (value as ModelThoughtLevel)
    : (levels.includes('medium') ? 'medium' : levels[0]);

  const shortLabel = getLevelShortLabel(effectiveValue);
  const fullLabel = getLevelLabel(effectiveValue);
  // Keep the send box compact and stable in Chinese; the dropdown retains the
  // full protocol labels (including Low/Medium/XHigh) for disambiguation.
  const displayLabel = `${t('agent.thoughtLevel.label', '思考')}: ${shortLabel}`;

  return (
    <Dropdown
      trigger='click'
      {...(isMobileHeaderCompact ? { getPopupContainer: () => document.body } : {})}
      droplist={
        <Menu>
          <div className='px-12px py-6px text-12px font-medium text-t-secondary border-b border-color-border'>
            {t('settings.thoughtLevel', '推理强度 / 思考模式')}
          </div>
          {levels.map((lvl) => {
            const isSelected = lvl === effectiveValue;
            return (
              <Menu.Item
                key={lvl}
                className={isSelected ? '!bg-2' : ''}
                onClick={() => onChange(lvl)}
              >
                <RuntimeSelectorCheckedItem selected={isSelected}>
                  {getLevelLabel(lvl)}
                </RuntimeSelectorCheckedItem>
              </Menu.Item>
            );
          })}
        </Menu>
      }
    >
      <Button
        data-testid='reasoning-effort-selector'
        className={classNames(
          'sendbox-model-btn header-model-btn',
          compact && '!max-w-[120px]',
          isMobileHeaderCompact && '!max-w-[140px]',
          className
        )}
        shape='round'
        size='small'
        disabled={disabled}
      >
        <span className='flex items-center gap-6px min-w-0'>
          <Brain theme='outline' size='14' fill={iconColors.secondary} className='shrink-0' />
          <span className={compact ? 'block truncate' : undefined}>{displayLabel}</span>
          <Down theme='outline' size={12} fill={iconColors.secondary} className='shrink-0' />
        </span>
      </Button>
    </Dropdown>
  );
};

export default ReasoningEffortSelector;
