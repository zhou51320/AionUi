/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import AssistantSettings from '@/renderer/pages/settings/AssistantSettings';

const AgentModalContent: React.FC = () => {
  return (
    <div className='flex flex-col h-full w-full'>
      <AssistantSettings />
    </div>
  );
};

export default AgentModalContent;
