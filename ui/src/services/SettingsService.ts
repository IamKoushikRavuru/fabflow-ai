export interface FabSettings {
  // Solver settings
  solverTimeLimitSeconds: number;
  maxOpsPerLot: number;
  horizonMinutes: number;
  weights: {
    makespan: number;
    idle_time: number;
    weighted_tardiness: number;
    penalty_cost: number;
  };
  includeMaintenance: boolean;
  includeFailures: boolean;

  // Financial rates
  normalPenaltyRate: number;
  hotLotPenaltyRate: number;
  waferScrapCost: number;

  // Telemetry & API
  syncIntervalSeconds: number;
  apiBaseUrl: string;
  webhookUrl: string;

  // Facility & Organization
  facilityName: string;
  activeShift: string;
}

export const DEFAULT_SETTINGS: FabSettings = {
  solverTimeLimitSeconds: 15,
  maxOpsPerLot: 8,
  horizonMinutes: 6000,
  weights: {
    makespan: 1.0,
    idle_time: 0.5,
    weighted_tardiness: 2.0,
    penalty_cost: 3.0,
  },
  includeMaintenance: true,
  includeFailures: false,

  normalPenaltyRate: 10.0,
  hotLotPenaltyRate: 100.0,
  waferScrapCost: 350.0,

  syncIntervalSeconds: 3,
  apiBaseUrl: 'http://localhost:8000/api',
  webhookUrl: 'https://hooks.slack.com/services/fabflow/alerts',

  facilityName: 'Fab 12 — Hsinchu 300mm Pilot Line',
  activeShift: 'Shift A (07:00 - 19:00)',
};

const STORAGE_KEY = 'fabflow_system_settings';

export class SettingsService {
  static getSettings(): FabSettings {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return DEFAULT_SETTINGS;
    try {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(saved) };
    } catch {
      return DEFAULT_SETTINGS;
    }
  }

  static saveSettings(settings: FabSettings): void {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    localStorage.setItem('fabflow_sync_interval', String(settings.syncIntervalSeconds));
  }

  static resetToDefaults(): FabSettings {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.setItem('fabflow_sync_interval', String(DEFAULT_SETTINGS.syncIntervalSeconds));
    return DEFAULT_SETTINGS;
  }
}
