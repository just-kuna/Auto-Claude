/**
 * Mock implementation for Claude profile management operations
 */

export const claudeProfileMock = {
  getIFlowProfiles: async () => ({
    success: true,
    data: {
      profiles: [],
      activeProfileId: 'default'
    }
  }),

  saveIFlowProfile: async (profile: { id: string; name: string; oauthToken?: string; email?: string; isDefault?: boolean; createdAt?: Date }) => ({
    success: true,
    data: {
      id: profile.id,
      name: profile.name,
      oauthToken: profile.oauthToken,
      email: profile.email,
      isDefault: profile.isDefault ?? false,
      createdAt: profile.createdAt ?? new Date(),
    }
  }),

  deleteIFlowProfile: async () => ({ success: true }),

  renameIFlowProfile: async () => ({ success: true }),

  setActiveIFlowProfile: async () => ({ success: true }),

  switchIFlowProfile: async () => ({ success: true }),

  initializeIFlowProfile: async () => ({ success: true }),

  setIFlowProfileToken: async () => ({ success: true }),

  getAutoSwitchSettings: async () => ({
    success: true,
    data: {
      enabled: false,
      proactiveSwapEnabled: false,
      sessionThreshold: 95,
      weeklyThreshold: 99,
      autoSwitchOnRateLimit: false,
      usageCheckInterval: 30000
    }
  }),

  updateAutoSwitchSettings: async () => ({ success: true }),

  fetchIFlowUsage: async () => ({ success: true }),

  getBestAvailableProfile: async () => ({
    success: true,
    data: null
  }),

  onSDKRateLimit: () => () => {},

  retryWithProfile: async () => ({ success: true }),

  // Usage Monitoring (Proactive Account Switching)
  requestUsageUpdate: async () => ({
    success: true,
    data: null
  }),

  onUsageUpdated: () => () => {},

  onProactiveSwapNotification: () => () => {}
};
