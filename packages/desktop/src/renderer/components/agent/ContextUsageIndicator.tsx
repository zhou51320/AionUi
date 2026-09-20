/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { Popover } from '@arco-design/web-react';
import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { TokenUsageCost, TokenUsageData } from '@/common/config/storage';
import { formatCurrency, formatNumber } from '@/renderer/services/i18n/format';

export interface ContextCacheStats {
  block_count?: number;
  original_total_size?: number;
  compressed_total_size?: number;
  saved_size?: number;
}

interface ContextUsageIndicatorProps {
  tokenUsage: TokenUsageData | null;
  /**
   * Agent-reported context window size.
   */
  context_limit: number;
  cacheStats?: ContextCacheStats | null;
  className?: string;
  size?: number;
}

const ContextUsageIndicator: React.FC<ContextUsageIndicatorProps> = ({
  tokenUsage,
  context_limit,
  cacheStats,
  className = '',
  size = 32,
}) => {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const [pinned, setPinned] = useState(false);
  const [popoverVisible, setPopoverVisible] = useState(false);

  const hasWindow = context_limit > 0;

  const { percentage, displayTotal, displayLimit, tierColor } = useMemo(() => {
    if (!tokenUsage) {
      return {
        percentage: 0,
        displayTotal: '0',
        displayLimit: hasWindow ? formatTokenCount(context_limit, locale, true) : '0',
        tierColor: '#3B82F6',
      };
    }

    const total = tokenUsage.total_tokens;
    if (!hasWindow) {
      return {
        percentage: 0,
        displayTotal: formatTokenCount(total, locale),
        displayLimit: '0',
        tierColor: '#3B82F6',
      };
    }

    const pct = (total / context_limit) * 100;
    let color = '#3B82F6';
    if (pct >= 95) {
      color = '#EF4444';
    } else if (pct >= 80) {
      color = '#F59E0B';
    }

    return {
      percentage: pct,
      displayTotal: formatTokenCount(total, locale),
      displayLimit: formatTokenCount(context_limit, locale, true),
      tierColor: color,
    };
  }, [tokenUsage, context_limit, hasWindow, locale]);

  // Ring geometry: 20x20 outer box, 16px circle diameter (radius 8), 2px stroke
  const strokeWidth = 2;
  const radius = 8;
  const circumference = 2 * Math.PI * radius;
  const clampedPercentage = Math.min(100, Math.max(0, percentage));
  const strokeDashoffset = circumference - (clampedPercentage / 100) * circumference;

  // Center text (9px, max 99% to avoid overflow)
  const centerText = useMemo(() => {
    if (!hasWindow) return '•';
    if (percentage >= 99.5) return '99%';
    if (percentage > 0 && percentage < 1) return '<1%';
    return `${Math.round(percentage)}%`;
  }, [hasWindow, percentage]);

  const breakdown = tokenUsage?.breakdown;

  // Layer 2: Expanded Card (ContextCard) - 280px wide
  const popoverCard = (
    <div
      className='w-280px p-12px select-none text-12px'
      style={{
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
        borderRadius: 8,
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Section 1: Context Window */}
      <div className='mb-8px'>
        <div className='flex items-center justify-between'>
          <span className='text-12px font-medium text-t-secondary'>
            {t('conversation.contextUsage.contextWindow', '上下文窗口')}
          </span>
          <span className='text-13px font-bold' style={{ color: tierColor }}>
            {hasWindow
              ? `${formatNumber(percentage, locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`
              : t('conversation.contextUsage.unknown', '未知')}
          </span>
        </div>

        {hasWindow && (
          <div className='w-full h-4px bg-fill-2 rounded-full overflow-hidden my-6px'>
            <div
              className='h-full rounded-full transition-all duration-300'
              style={{
                width: `${clampedPercentage}%`,
                backgroundColor: tierColor,
              }}
            />
          </div>
        )}

        <div className='flex items-center justify-between text-11px text-t-secondary mt-4px'>
          <span>{t('conversation.contextUsage.usedAndLimit', '已用 / 上限')}</span>
          <span className='font-medium text-t-primary'>
            {hasWindow ? `${displayTotal} / ${displayLimit}` : displayTotal}
          </span>
        </div>
      </div>

      {/* Section 2: Token Usage */}
      <div className='border-t border-border-2 pt-8px mb-8px'>
        <div className='text-12px font-medium text-t-secondary mb-6px'>
          {t('conversation.contextUsage.tokenUsage', 'Token 用量')}
        </div>
        <div className='space-y-4px text-11px'>
          {breakdown?.input_tokens !== undefined && (
            <div className='flex items-center justify-between'>
              <span className='text-t-secondary'>{t('conversation.contextUsage.input', '输入')}</span>
              <span className='text-t-primary font-medium'>{formatTokenCount(breakdown.input_tokens, locale)}</span>
            </div>
          )}
          {breakdown?.output_tokens !== undefined && (
            <div className='flex items-center justify-between'>
              <span className='text-t-secondary'>{t('conversation.contextUsage.output', '输出')}</span>
              <span className='text-t-primary font-medium'>{formatTokenCount(breakdown.output_tokens, locale)}</span>
            </div>
          )}
          {breakdown?.cached_read_tokens !== undefined && breakdown.cached_read_tokens > 0 && (
            <div className='flex items-center justify-between'>
              <span className='text-t-secondary'>{t('conversation.contextUsage.cachedRead', '缓存读取')}</span>
              <span className='text-t-primary font-medium'>{formatTokenCount(breakdown.cached_read_tokens, locale)}</span>
            </div>
          )}
          {breakdown?.cached_write_tokens !== undefined && breakdown.cached_write_tokens > 0 && (
            <div className='flex items-center justify-between'>
              <span className='text-t-secondary'>{t('conversation.contextUsage.cachedWrite', '缓存写入')}</span>
              <span className='text-t-primary font-medium'>{formatTokenCount(breakdown.cached_write_tokens, locale)}</span>
            </div>
          )}
          {breakdown?.thought_tokens !== undefined && breakdown.thought_tokens > 0 && (
            <div className='flex items-center justify-between'>
              <span className='text-t-secondary'>{t('conversation.contextUsage.thought', '深度思考')}</span>
              <span className='text-t-primary font-medium'>{formatTokenCount(breakdown.thought_tokens, locale)}</span>
            </div>
          )}
          <div className='flex items-center justify-between pt-2px border-t border-border-1'>
            <span className='text-t-primary font-semibold'>{t('conversation.contextUsage.total', '总计')}</span>
            <span className='text-t-primary font-semibold'>{displayTotal}</span>
          </div>
        </div>
      </div>

      {/* Section 3: Compressed Cache & Session Cost */}
      <div className='border-t border-border-2 pt-8px space-y-4px text-11px'>
        <div className='flex items-center justify-between'>
          <span className='text-t-secondary'>{t('conversation.contextUsage.compressedCache', '压缩缓存')}</span>
          <span className='text-t-primary font-medium'>
            {cacheStats && (cacheStats.block_count ?? 0) > 0
              ? t('conversation.contextUsage.compressedStats', '{{count}} 块 / 节省 {{saved}}', {
                  count: cacheStats.block_count,
                  saved: formatTokenCount(Math.round((cacheStats.saved_size ?? 0) / 4), locale),
                })
              : t('conversation.contextUsage.noCompression', '暂无压缩')}
          </span>
        </div>

        {tokenUsage?.cost && (
          <div className='flex items-center justify-between'>
            <span className='text-t-secondary'>{t('conversation.contextUsage.sessionCost', '会话成本')}</span>
            <span className='text-t-primary font-medium'>≈ {formatCostAmount(tokenUsage.cost, locale)}</span>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <Popover
      content={popoverCard}
      position='top'
      trigger={pinned ? 'click' : 'hover'}
      popupVisible={popoverVisible}
      onVisibleChange={(visible) => {
        if (!pinned) {
          setPopoverVisible(visible);
        }
      }}
      className='context-usage-popover'
    >
      <div
        className={`context-usage-indicator cursor-pointer flex items-center justify-center select-none transition-transform hover:scale-105 active:scale-95 ${className}`}
        style={{ width: size, height: size }}
        title={t('conversation.contextUsage.title', '上下文占用情况 (点击固定)')}
        onClick={(e) => {
          e.stopPropagation();
          const nextPinned = !pinned;
          setPinned(nextPinned);
          setPopoverVisible(nextPinned ? true : false);
        }}
      >
        <svg width={20} height={20} viewBox='0 0 20 20' className='overflow-visible'>
          {/* Background Ring */}
          <circle
            cx={10}
            cy={10}
            r={radius}
            fill='none'
            stroke='var(--color-fill-3, #E5E7EB)'
            strokeWidth={strokeWidth}
          />
          {/* Progress Ring (rotated -90deg starting from top) */}
          {hasWindow && (
            <circle
              cx={10}
              cy={10}
              r={radius}
              fill='none'
              stroke={tierColor}
              strokeWidth={strokeWidth}
              strokeLinecap='round'
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              style={{
                transformOrigin: '10px 10px',
                transform: 'rotate(-90deg)',
                transition: 'stroke-dashoffset 0.3s ease, stroke 0.3s ease',
              }}
            />
          )}
          {/* Center Percentage Label */}
          <text
            x={10}
            y={10.5}
            textAnchor='middle'
            dominantBaseline='central'
            fontSize='9'
            fontWeight='600'
            fill='var(--color-text-1, #374151)'
            style={{ pointerEvents: 'none' }}
          >
            {centerText}
          </text>
        </svg>
      </div>
    </Popover>
  );
};

/**
 * Smallest amount that four fraction digits can still render honestly. Below
 * it, rounding to 4dp yields 0, and the currency's own minimum fraction digits
 * (2 for USD) then print it as "$0.00".
 */
const SUB_UNIT_PRECISION_FLOOR = 0.0001;

/**
 * Format an agent-reported cumulative session cost in the app language,
 * e.g. "$0.42" (en-US) or "0,42 $" (de-DE).
 *
 * Four fraction digits suit an ordinary session cost, but a single cheap turn
 * can bill fractions of a cent, and at that size `maximumFractionDigits: 4`
 * rounds to zero and renders "$0.00" — indistinguishable from free. Amounts
 * below the floor therefore switch to significant digits, which keeps the
 * charge visible ("$0.00003") without turning "$1,234.5678" into "$1,200" the
 * way significant digits would if applied across the whole range.
 *
 * Falls back to "0.4200 USD" when the currency code is not renderable.
 */
export function formatCostAmount(cost: TokenUsageCost, locale?: string): string {
  const isVisibleAtFourDigits = cost.amount === 0 || Math.abs(cost.amount) >= SUB_UNIT_PRECISION_FLOOR;
  const options: Intl.NumberFormatOptions = isVisibleAtFourDigits
    ? { maximumFractionDigits: 4 }
    : { maximumSignificantDigits: 2 };
  return formatCurrency(cost.amount, cost.currency, locale, options);
}

/**
 * Format the context-usage percentage in the app language, e.g. "4.8%" (en-US)
 * or "4,8 %" (fr-FR).
 */
export function formatPercentage(value: number, locale?: string): string {
  return formatNumber(value / 100, locale, {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

/**
 * Format a token count as a compact "12.6K" / "1.2M" string.
 *
 * The K/M suffixes stay as-is — `Intl` compact notation is unusable here
 * (de-DE renders 12600 as "12.600", indistinguishable from a grouped integer) —
 * but the decimal separator follows the app language, so the popover does not
 * mix "0,42 $" with "12.6K".
 *
 * @param count token count
 * @param locale app language (`i18n.language`)
 * @param hideZeroDecimals drop a trailing zero decimal (1.0M → 1M), default false
 */
export function formatTokenCount(count: number, locale?: string, hideZeroDecimals = false): string {
  const withSuffix = (value: number, suffix: string): string => {
    // Keep the original rounding rule: a value that renders as "x.0" at one
    // decimal collapses to the floored integer.
    if (hideZeroDecimals && value.toFixed(1).endsWith('.0')) {
      return `${formatNumber(Math.floor(value), locale, { maximumFractionDigits: 0 })}${suffix}`;
    }
    return `${formatNumber(value, locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}${suffix}`;
  };

  if (count >= 1_000_000) return withSuffix(count / 1_000_000, 'M');
  if (count >= 1_000) return withSuffix(count / 1_000, 'K');
  return formatNumber(count, locale, { maximumFractionDigits: 0 });
}

export default ContextUsageIndicator;
