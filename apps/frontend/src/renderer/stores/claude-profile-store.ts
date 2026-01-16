import { create } from 'zustand';
import type { IFlowProfile, IFlowProfileSettings } from '../../shared/types';

interface IFlowProfileState {
  profiles: IFlowProfile[];
  activeProfileId: string;
  isLoading: boolean;
  isSwitching: boolean;

  // Actions
  setProfiles: (settings: IFlowProfileSettings) => void;
  setActiveProfile: (profileId: string) => void;
  addProfile: (profile: IFlowProfile) => void;
  updateProfile: (profile: IFlowProfile) => void;
  removeProfile: (profileId: string) => void;
  setLoading: (loading: boolean) => void;
  setSwitching: (switching: boolean) => void;
}

export const useIFlowProfileStore = create<IFlowProfileState>((set) => ({
  profiles: [],
  activeProfileId: 'default',
  isLoading: false,
  isSwitching: false,

  setProfiles: (settings: IFlowProfileSettings) => {
    set({
      profiles: settings.profiles,
      activeProfileId: settings.activeProfileId
    });
  },

  setActiveProfile: (profileId: string) => {
    set({ activeProfileId: profileId });
  },

  addProfile: (profile: IFlowProfile) => {
    set((state) => ({
      profiles: [...state.profiles, profile]
    }));
  },

  updateProfile: (profile: IFlowProfile) => {
    set((state) => ({
      profiles: state.profiles.map((p) =>
        p.id === profile.id ? profile : p
      )
    }));
  },

  removeProfile: (profileId: string) => {
    set((state) => ({
      profiles: state.profiles.filter((p) => p.id !== profileId)
    }));
  },

  setLoading: (loading: boolean) => {
    set({ isLoading: loading });
  },

  setSwitching: (switching: boolean) => {
    set({ isSwitching: switching });
  },
}));

/**
 * Load Claude profiles from the main process
 */
export async function loadIFlowProfiles(): Promise<void> {
  const store = useIFlowProfileStore.getState();
  store.setLoading(true);

  try {
    const result = await window.electronAPI.getIFlowProfiles();
    if (result.success && result.data) {
      store.setProfiles(result.data);
    }
  } catch (error) {
    console.error('[IFlowProfileStore] Error loading profiles:', error);
  } finally {
    store.setLoading(false);
  }
}

/**
 * Switch to a different Claude profile in a terminal
 */
export async function switchTerminalToProfile(
  terminalId: string,
  profileId: string
): Promise<boolean> {
  const store = useIFlowProfileStore.getState();
  store.setSwitching(true);

  try {
    const result = await window.electronAPI.switchIFlowProfile(terminalId, profileId);
    if (result.success) {
      store.setActiveProfile(profileId);
      return true;
    }
    return false;
  } catch (error) {
    console.error('[IFlowProfileStore] Error switching profile:', error);
    return false;
  } finally {
    store.setSwitching(false);
  }
}
