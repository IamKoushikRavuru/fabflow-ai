import { useState } from 'react';
import { SettingsService, type FabSettings } from '@/services/SettingsService';
import { useLiveSync } from '@/context/LiveSyncContext';
import { GlassCard } from '@/components/shared/GlassCard';
import { Button } from '@/components/ui/button';
import { 
  DollarSign, 
  Radio, 
  Building2, 
  Save, 
  RotateCcw, 
  CheckCircle2, 
  Cpu
} from 'lucide-react';

export default function SettingsPage() {
  const [settings, setSettings] = useState<FabSettings>(() => SettingsService.getSettings());
  const [savedSuccess, setSavedSuccess] = useState(false);
  const { setIntervalSeconds } = useLiveSync();

  const handleSave = () => {
    SettingsService.saveSettings(settings);
    setIntervalSeconds(settings.syncIntervalSeconds);
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  const handleReset = () => {
    const defaults = SettingsService.resetToDefaults();
    setSettings(defaults);
    setIntervalSeconds(defaults.syncIntervalSeconds);
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  return (
    <div className="flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-5xl mx-auto">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Fab & Solver Settings</h1>
          <p className="text-muted-foreground text-sm">
            Configure Google OR-Tools CP-SAT multi-objective weights, live telemetry intervals, and SLA penalty rates.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={handleReset}
            className="flex items-center gap-2 border-white/10 hover:bg-white/5 text-xs font-semibold py-2 px-4 rounded-xl cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset Defaults
          </Button>
          <Button
            variant="glow"
            onClick={handleSave}
            className="flex items-center gap-2 text-xs font-bold py-2 px-5 rounded-xl cursor-pointer"
          >
            <Save className="w-4 h-4" />
            Save Changes
          </Button>
        </div>
      </div>

      {/* Saved Toast Banner */}
      {savedSuccess && (
        <div className="flex items-center gap-2 p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm font-medium animate-in fade-in slide-in-from-top-2 duration-300">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          Settings successfully updated and applied to active CP-SAT solver pipeline!
        </div>
      )}

      {/* 1. CP-SAT Solver Multi-Objective Weights */}
      <GlassCard className="p-6 space-y-6">
        <div className="flex items-center gap-3 pb-3 border-b border-white/10">
          <div className="p-2 rounded-lg bg-primary/10 text-primary">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">Google OR-Tools CP-SAT Solver Config</h2>
            <p className="text-xs text-muted-foreground">Adjust timeout thresholds and multi-objective optimization weightings</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Wall-clock limit */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="font-medium text-foreground">Solver Wall-Clock Limit:</span>
              <span className="font-mono text-primary font-bold">{settings.solverTimeLimitSeconds} seconds</span>
            </div>
            <input
              type="range"
              min="5"
              max="60"
              step="1"
              value={settings.solverTimeLimitSeconds}
              onChange={(e) => setSettings({ ...settings, solverTimeLimitSeconds: Number(e.target.value) })}
              className="w-full accent-primary"
            />
            <span className="text-[11px] text-muted-foreground block">
              Max solve duration before returning best feasible/optimal branch.
            </span>
          </div>

          {/* Max ops per lot */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span className="font-medium text-foreground">Max Operations Slice per Lot:</span>
              <span className="font-mono text-primary font-bold">{settings.maxOpsPerLot} operations</span>
            </div>
            <input
              type="range"
              min="4"
              max="24"
              step="1"
              value={settings.maxOpsPerLot}
              onChange={(e) => setSettings({ ...settings, maxOpsPerLot: Number(e.target.value) })}
              className="w-full accent-primary"
            />
            <span className="text-[11px] text-muted-foreground block">
              Reduces problem size for interactive sub-second responses.
            </span>
          </div>
        </div>

        {/* Weights sliders */}
        <div className="space-y-4 pt-4 border-t border-white/5">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Objective Function Weight Matrix
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-3 rounded-xl bg-white/5 border border-white/5 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Makespan Weight</span>
                <span className="font-mono font-bold text-foreground">{settings.weights.makespan.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min="0"
                max="5"
                step="0.5"
                value={settings.weights.makespan}
                onChange={(e) => setSettings({
                  ...settings,
                  weights: { ...settings.weights, makespan: Number(e.target.value) },
                })}
                className="w-full accent-primary"
              />
            </div>

            <div className="p-3 rounded-xl bg-white/5 border border-white/5 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Idle Time Weight</span>
                <span className="font-mono font-bold text-foreground">{settings.weights.idle_time.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min="0"
                max="5"
                step="0.5"
                value={settings.weights.idle_time}
                onChange={(e) => setSettings({
                  ...settings,
                  weights: { ...settings.weights, idle_time: Number(e.target.value) },
                })}
                className="w-full accent-primary"
              />
            </div>

            <div className="p-3 rounded-xl bg-white/5 border border-white/5 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Tardiness Weight</span>
                <span className="font-mono font-bold text-foreground">{settings.weights.weighted_tardiness.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min="0"
                max="5"
                step="0.5"
                value={settings.weights.weighted_tardiness}
                onChange={(e) => setSettings({
                  ...settings,
                  weights: { ...settings.weights, weighted_tardiness: Number(e.target.value) },
                })}
                className="w-full accent-primary"
              />
            </div>

            <div className="p-3 rounded-xl bg-white/5 border border-white/5 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Penalty Cost Weight</span>
                <span className="font-mono font-bold text-foreground">{settings.weights.penalty_cost.toFixed(1)}</span>
              </div>
              <input
                type="range"
                min="0"
                max="5"
                step="0.5"
                value={settings.weights.penalty_cost}
                onChange={(e) => setSettings({
                  ...settings,
                  weights: { ...settings.weights, penalty_cost: Number(e.target.value) },
                })}
                className="w-full accent-primary"
              />
            </div>
          </div>
        </div>

        {/* Constraint Switches */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
          <label className="flex items-center justify-between p-3.5 rounded-xl bg-white/5 border border-white/5 cursor-pointer hover:bg-white/10 transition-colors">
            <div>
              <div className="text-xs font-medium text-foreground">Enforce Maintenance Windows</div>
              <div className="text-[11px] text-muted-foreground">Block tools during scheduled PM periods</div>
            </div>
            <input
              type="checkbox"
              checked={settings.includeMaintenance}
              onChange={(e) => setSettings({ ...settings, includeMaintenance: e.target.checked })}
              className="h-4 w-4 rounded accent-primary cursor-pointer"
            />
          </label>

          <label className="flex items-center justify-between p-3.5 rounded-xl bg-white/5 border border-white/5 cursor-pointer hover:bg-white/10 transition-colors">
            <div>
              <div className="text-xs font-medium text-foreground">Account for Tool Breakdowns</div>
              <div className="text-[11px] text-muted-foreground">Treat historical failures as unavailable intervals</div>
            </div>
            <input
              type="checkbox"
              checked={settings.includeFailures}
              onChange={(e) => setSettings({ ...settings, includeFailures: e.target.checked })}
              className="h-4 w-4 rounded accent-primary cursor-pointer"
            />
          </label>
        </div>
      </GlassCard>

      {/* 2. Financial Penalty Rates & Scrap Values */}
      <GlassCard className="p-6 space-y-6">
        <div className="flex items-center gap-3 pb-3 border-b border-white/10">
          <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
            <DollarSign className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">Financial & SLA Penalty Rates</h2>
            <p className="text-xs text-muted-foreground">Customer contractual penalty rates applied per minute of delay</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Normal Priority Penalty ($/min)</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-xs">$</span>
              <input
                type="number"
                value={settings.normalPenaltyRate}
                onChange={(e) => setSettings({ ...settings, normalPenaltyRate: Number(e.target.value) })}
                className="w-full pl-7 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm font-mono text-foreground focus:outline-none focus:border-primary/50"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Hot Lot Penalty ($/min)</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-rose-400 text-xs">$</span>
              <input
                type="number"
                value={settings.hotLotPenaltyRate}
                onChange={(e) => setSettings({ ...settings, hotLotPenaltyRate: Number(e.target.value) })}
                className="w-full pl-7 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm font-mono text-rose-400 font-bold focus:outline-none focus:border-rose-400/50"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Wafer Scrap Cost ($/wafer)</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-xs">$</span>
              <input
                type="number"
                value={settings.waferScrapCost}
                onChange={(e) => setSettings({ ...settings, waferScrapCost: Number(e.target.value) })}
                className="w-full pl-7 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm font-mono text-foreground focus:outline-none focus:border-primary/50"
              />
            </div>
          </div>
        </div>
      </GlassCard>

      {/* 3. Live Telemetry & API Endpoints */}
      <GlassCard className="p-6 space-y-6">
        <div className="flex items-center gap-3 pb-3 border-b border-white/10">
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
            <Radio className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">Live Telemetry & Connectivity</h2>
            <p className="text-xs text-muted-foreground">Background synchronization polling interval and alert webhooks</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Background Sync Interval</label>
            <select
              value={settings.syncIntervalSeconds}
              onChange={(e) => setSettings({ ...settings, syncIntervalSeconds: Number(e.target.value) })}
              className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-foreground focus:outline-none focus:border-primary/50 cursor-pointer"
            >
              <option value={1} className="bg-background">Every 1 second (Ultra-Fast)</option>
              <option value={2} className="bg-background">Every 2 seconds (High Responsiveness)</option>
              <option value={3} className="bg-background">Every 3 seconds (Recommended)</option>
              <option value={5} className="bg-background">Every 5 seconds (Low Overhead)</option>
              <option value={10} className="bg-background">Every 10 seconds</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">FastAPI REST Backend URL</label>
            <input
              type="text"
              value={settings.apiBaseUrl}
              onChange={(e) => setSettings({ ...settings, apiBaseUrl: e.target.value })}
              className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm font-mono text-foreground focus:outline-none focus:border-primary/50"
            />
          </div>

          <div className="sm:col-span-2 space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Alert Webhook Endpoint (Slack / Teams)</label>
            <input
              type="text"
              value={settings.webhookUrl}
              onChange={(e) => setSettings({ ...settings, webhookUrl: e.target.value })}
              className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm font-mono text-foreground focus:outline-none focus:border-primary/50"
            />
          </div>
        </div>
      </GlassCard>

      {/* 4. Fab Facility Profile */}
      <GlassCard className="p-6 space-y-6">
        <div className="flex items-center gap-3 pb-3 border-b border-white/10">
          <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400">
            <Building2 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">Facility Profile & Active Shift</h2>
            <p className="text-xs text-muted-foreground">Fab identity used on generated production and handover reports</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Facility Designation</label>
            <input
              type="text"
              value={settings.facilityName}
              onChange={(e) => setSettings({ ...settings, facilityName: e.target.value })}
              className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-foreground focus:outline-none focus:border-primary/50"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Active Operational Shift</label>
            <input
              type="text"
              value={settings.activeShift}
              onChange={(e) => setSettings({ ...settings, activeShift: e.target.value })}
              className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-foreground focus:outline-none focus:border-primary/50"
            />
          </div>
        </div>
      </GlassCard>

    </div>
  );
}
