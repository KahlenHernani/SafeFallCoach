import { createContext, useContext, useEffect, useMemo, useState } from 'react';

type AccessibilitySettings = {
  fontScale: number;
  highContrast: boolean;
  reducedMotion: boolean;
  simplifiedNavigation: boolean;
  audioGuidance: boolean;
};

type AccessibilityContextValue = {
  settings: AccessibilitySettings;
  setSettings: React.Dispatch<React.SetStateAction<AccessibilitySettings>>;
};

const defaultSettings: AccessibilitySettings = {
  fontScale: 1,
  highContrast: false,
  reducedMotion: false,
  simplifiedNavigation: true,
  audioGuidance: false,
};

const AccessibilityContext = createContext<AccessibilityContextValue | null>(null);

const STORAGE_KEY = 'safefall.accessibility';

function loadSettings(): AccessibilitySettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...defaultSettings, ...JSON.parse(raw) };
  } catch {
    /* ignore unavailable/corrupt storage */
  }
  return defaultSettings;
}

export function AccessibilityProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<AccessibilitySettings>(loadSettings);

  // Persist so choices survive a refresh.
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch {
      /* ignore */
    }
  }, [settings]);

  // Scale the html root font-size so every rem-based size in the UI grows.
  useEffect(() => {
    document.documentElement.style.fontSize = `${16 * settings.fontScale}px`;
  }, [settings.fontScale]);

  const value = useMemo(() => ({ settings, setSettings }), [settings]);
  return <AccessibilityContext.Provider value={value}>{children}</AccessibilityContext.Provider>;
}

export function useAccessibility() {
  const ctx = useContext(AccessibilityContext);
  if (!ctx) throw new Error('useAccessibility must be used inside AccessibilityProvider');
  return ctx;
}
