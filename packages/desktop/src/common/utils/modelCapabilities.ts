/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import type {
  IProvider,
  ModelImageInputCapability,
  ModelOpenAiApiMode,
  ModelSettings,
  ModelThoughtLevel,
  ModelType,
} from '@/common/config/storage';

/**
 * Capability matching regex patterns
 */
export const CAPABILITY_PATTERNS: Record<ModelType, RegExp> = {
  text: /gpt|claude|gemini|qwen|llama|mistral|deepseek/i,
  vision: /4o|claude-3|gemini-.*-pro|gemini-.*-flash|gemini-2\.0|qwen-vl|llava|vision/i,
  function_calling: /gpt-4|claude-3|gemini|qwen|deepseek/i,
  image_generation: /flux|diffusion|stabilityai|sd-|dall|cogview|janus|midjourney|mj-|imagen/i,
  web_search: /search|perplexity/i,
  reasoning: /o1-|reasoning|think/i,
  embedding: /(?:^text-|embed|bge-|e5-|LLM2Vec|retrieval|uae-|gte-|jina-clip|jina-embeddings|voyage-)/i,
  rerank: /(?:rerank|re-rank|re-ranker|re-ranking|retrieval|retriever)/i,
  excludeFromPrimary: /dall-e|flux|stable-diffusion|midjourney|flash-image|image|embed|rerank/i,
};

/**
 * Explicit exclusion lists (blacklist) for capabilities
 */
export const CAPABILITY_EXCLUSIONS: Record<ModelType, RegExp[]> = {
  text: [],
  vision: [/embed|rerank|dall-e|flux|stable-diffusion/i],
  function_calling: [
    /aqa(?:-[\w-]+)?/i,
    /imagen(?:-[\w-]+)?/i,
    /o1-mini/i,
    /o1-preview/i,
    /gemini-1(?:\\.[\w-]+)?/i,
    /dall-e/i,
    /embed/i,
    /rerank/i,
  ],
  image_generation: [],
  web_search: [],
  reasoning: [],
  embedding: [],
  rerank: [],
  excludeFromPrimary: [],
};

/**
 * Get the lowercase, normalized base model name for matching.
 */
export const getBaseModelName = (modelName: string): string => {
  return modelName
    .toLowerCase()
    .replace(/[^a-z0-9./-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
};

export type ModelOpenAiApiModeChoice = ModelOpenAiApiMode | 'auto';
export type ModelImageInputChoice = ModelImageInputCapability | 'auto';
export type ModelContextLimitChoice = number | 'auto';
export type ModelThoughtLevelChoice = 'auto' | 'off' | 'low' | 'medium' | 'high' | 'xhigh';

/** Auto-detect whether a model supports reasoning/thought level settings. */
export const detectModelThoughtSupport = (modelName: string): boolean => {
  const normalized = getBaseModelName(modelName);
  return /o1|o3|r1|reasoning|reasoner|thinking|think|deepseek|qwen3|qwen-3|qwq|claude-3-7|gemini-2/i.test(normalized);
};

/** Auto-detect default context window (in tokens) based on model name. */
export const detectModelContextLimit = (modelName: string): number => {
  const normalized = getBaseModelName(modelName);
  if (/gemini-1\.5|gemini-2/i.test(normalized)) return 1_000_000;
  if (/claude-3/i.test(normalized)) return 200_000;
  if (/deepseek/i.test(normalized)) return 64_000;
  if (/gpt-4o|gpt-4-turbo|o1|o3/i.test(normalized)) return 128_000;
  if (/qwen-2\.5|qwen-max|qwen-plus/i.test(normalized)) return 128_000;
  if (/llama-3\.[123]/i.test(normalized)) return 128_000;
  if (/gpt-4/i.test(normalized)) return 8_192;
  if (/gpt-3\.5/i.test(normalized)) return 16_385;
  return 128_000;
};

/** Whether a provider/model protocol can select an OpenAI wire API. */
export const supportsOpenAiApiMode = (platform: string, modelProtocol = 'openai'): boolean => {
  if (platform === 'new-api') return modelProtocol === 'openai';
  return !['anthropic', 'bedrock', 'gemini', 'gemini-vertex-ai'].includes(platform);
};

/** Apply explicit settings to models while keeping automatic values absent on the wire. */
export const updateModelSettings = (
  current: Record<string, ModelSettings> | undefined,
  modelIds: string[],
  imageInput: ModelImageInputChoice,
  openAiApiMode: ModelOpenAiApiModeChoice,
  contextLimit?: ModelContextLimitChoice,
  thoughtLevel?: ModelThoughtLevelChoice,
  thoughtLevels?: ModelThoughtLevelChoice[]
): Record<string, ModelSettings> => {
  const next = { ...current };

  for (const modelId of modelIds) {
    const isAutoLimit =
      contextLimit === undefined || contextLimit === 'auto' || (typeof contextLimit === 'number' && contextLimit <= 0);
    // `undefined` means that the user left reasoning capability detection on
    // automatic. An explicitly supplied empty array is different: it means
    // the user intentionally disabled all reasoning levels and must survive a
    // round-trip through the settings editor.
    const hasThoughtLevels = Array.isArray(thoughtLevels);
    const isAutoThought = (thoughtLevel === undefined || thoughtLevel === 'auto') && !hasThoughtLevels;
    if (imageInput === 'auto' && openAiApiMode === 'auto' && isAutoLimit && isAutoThought) {
      delete next[modelId];
      continue;
    }

    const settings: ModelSettings = {};
    if (imageInput !== 'auto') settings.image_input = imageInput;
    if (openAiApiMode !== 'auto') settings.openai_api_mode = openAiApiMode;
    if (!isAutoLimit && typeof contextLimit === 'number') settings.context_limit = contextLimit;
    // Keep the default separate from the supported-level list. In particular,
    // an explicit `auto` default must survive saving a non-empty list; omitting
    // it makes the AionCore factory choose its fallback level on the next
    // conversation.
    if (hasThoughtLevels && thoughtLevel !== undefined) {
      settings.thought_level = thoughtLevel;
    } else if (!isAutoThought && thoughtLevel && thoughtLevel !== 'auto') {
      settings.thought_level = thoughtLevel;
    }
    if (hasThoughtLevels) settings.thought_levels = thoughtLevels as ModelThoughtLevel[];
    next[modelId] = settings;
  }

  return next;
};

/**
 * Resolve the list of supported reasoning/thought levels for a model.
 * If explicitly configured in model settings (thought_levels), uses that list.
 * Otherwise, if legacy thought_level is configured, includes it along with 'off'.
 * Models must explicitly opt in through model settings. A name-based guess can
 * expose a selector for providers that do not accept reasoning parameters.
 */
export const resolveModelThoughtLevels = (modelName: string, modelSettings?: ModelSettings): ModelThoughtLevel[] => {
  if (modelSettings?.thought_levels && modelSettings.thought_levels.length > 0) {
    return modelSettings.thought_levels;
  }
  if (modelSettings?.thought_level && modelSettings.thought_level !== 'auto') {
    return ['off', modelSettings.thought_level];
  }
  return [];
};

/**
 * Check whether a specific model within a provider has a given capability.
 * Returns true (supported), false (excluded), or undefined (unknown).
 */
export const hasSpecificModelCapability = (
  _platformModel: IProvider,
  modelName: string,
  type: ModelType
): boolean | undefined => {
  const baseModelName = getBaseModelName(modelName);
  const exclusions = CAPABILITY_EXCLUSIONS[type];
  const pattern = CAPABILITY_PATTERNS[type];

  const isExcluded = exclusions.some((excludePattern) => excludePattern.test(baseModelName));
  if (isExcluded) return false;

  return pattern.test(baseModelName) ? true : undefined;
};
