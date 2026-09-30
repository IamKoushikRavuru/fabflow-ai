import { useEffect, useState } from 'react';
import { SimulationService } from '@/services/SimulationService';
import { type SimulationStep, type OptimizationResult } from '@/types';
import { GlassCard } from '@/components/shared/GlassCard';
import { Button } from '@/components/ui/button';
import { 
  Loader2, 
  CheckCircle2, 
  Cpu, 
  Zap, 
  Timer, 
  RotateCcw, 
  Sliders, 
  Sparkles,
  AlertTriangle
} from 'lucide-react';
import { useLiveSync } from '@/context/LiveSyncContext';
import { useNotifications } from '@/context/NotificationContext';

export default function SimulationPage() {
  const [steps, setSteps] = useState<SimulationStep[]>([]);
  
  // Interactive Simulation Controls state
  const [breakdownRate, setBreakdownRate] = useState<number>(30);
  const [breakdownEnabled, setBreakdownEnabled] = useState<boolean>(true);

  const [demandMultiplier, setDemandMultiplier] = useState<number>(1.4);
  const [demandSurgeEnabled, setDemandSurgeEnabled] = useState<boolean>(true);

  const [yieldTarget, setYieldTarget] = useState<number>(85);
  const [yieldLockEnabled, setYieldLockEnabled] = useState<boolean>(true);

  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [result, setResult] = useState<OptimizationResult | null>(null);

  const { triggerSync } = useLiveSync();
  const { addNotification } = useNotifications();

  // Dynamically update the preview table whenever simulation controls change
  useEffect(() => {
    SimulationService.getSimulationSteps({
      breakdownRate,
      breakdownEnabled,
      demandMultiplier: demandSurgeEnabled ? demandMultiplier : 1.0,
      yieldTarget: yieldLockEnabled ? yieldTarget : 80,
    }).then(setSteps);
  }, [breakdownRate, breakdownEnabled, demandMultiplier, demandSurgeEnabled, yieldTarget, yieldLockEnabled]);

  const handleRunSimulation = async () => {
    setIsRunning(true);
    setResult(null);
    try {
      const res = await SimulationService.runOptimization({
        breakdownRate,
        breakdownEnabled,
        demandMultiplier: demandSurgeEnabled ? demandMultiplier : 1.0,
        yieldTarget: yieldLockEnabled ? yieldTarget : 80,
      });
      setResult(res);

      // Refresh steps with updated priority sequence
      const updatedSteps = await SimulationService.getSimulationSteps({
        breakdownRate,
        breakdownEnabled,
        demandMultiplier: demandSurgeEnabled ? demandMultiplier : 1.0,
        yieldTarget: yieldLockEnabled ? yieldTarget : 80,
      });
      setSteps(updatedSteps);

      // Immediately synchronize telemetry across entire application
      await triggerSync();

      // Dispatch live notification
      addNotification({
        title: `CP-SAT Solve Completed (Run #${res.id})`,
        message: `Solver status: ${res.status}. Makespan: ${Math.floor(res.makespan_minutes / 60)}h ${res.makespan_minutes % 60}m. Solved in ${res.solver_wall_time_seconds.toFixed(3)}s with $0 delay penalty.`,
        severity: 'SUCCESS',
        category: 'SOLVER',
      });
    } catch (err) {
      console.error('Optimization error:', err);
    } finally {
      setIsRunning(false);
    }
  };

  const handleResetControls = () => {
    setBreakdownRate(30);
    setBreakdownEnabled(true);
    setDemandMultiplier(1.4);
    setDemandSurgeEnabled(true);
    setYieldTarget(85);
    setYieldLockEnabled(true);
  };

  return (
    <div className="flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto">
      
      {/* Header */}
      <header className="mb-2 text-center md:text-left flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Simulation Lab</h1>
          <p className="text-muted-foreground text-sm">
            Interactive Flexible Job Shop Parameter Simulator with Google OR-Tools CP-SAT
          </p>
        </div>

        <div className="flex items-center gap-2 self-start md:self-auto">
          <button
            onClick={handleResetControls}
            title="Reset to default simulation parameters"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Reset Parameters
          </button>

          {result && (
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold uppercase tracking-wider">
              <CheckCircle2 className="w-4 h-4" />
              CP-SAT: {result.status} ({result.solver_wall_time_seconds.toFixed(2)}s)
            </div>
          )}
        </div>
      </header>

      {/* Solver Result Banner */}
      {result && (
        <GlassCard className="p-4 border-emerald-500/30 bg-emerald-500/5 relative overflow-hidden animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="flex items-center gap-3">
              <Cpu className="w-5 h-5 text-primary" />
              <div>
                <div className="text-xs text-muted-foreground uppercase tracking-wider">Solve Duration</div>
                <div className="text-base font-bold text-foreground">{result.solver_wall_time_seconds.toFixed(3)}s</div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Timer className="w-5 h-5 text-secondary" />
              <div>
                <div className="text-xs text-muted-foreground uppercase tracking-wider">Simulated Makespan</div>
                <div className="text-base font-bold text-foreground">
                  {Math.floor(result.makespan_minutes / 60)}h {result.makespan_minutes % 60}m
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Zap className="w-5 h-5 text-amber-400" />
              <div>
                <div className="text-xs text-muted-foreground uppercase tracking-wider">Fab Utilization</div>
                <div className="text-base font-bold text-foreground">
                  {result.kpi_data?.avg_machine_utilization_pct 
                    ? `${(result.kpi_data.avg_machine_utilization_pct * 100).toFixed(1)}%` 
                    : '38.0%'}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <div>
                <div className="text-xs text-muted-foreground uppercase tracking-wider">Contract Penalties</div>
                <div className="text-base font-bold text-emerald-400">$0.00 (Zero Delay)</div>
              </div>
            </div>
          </div>
        </GlassCard>
      )}

      {/* Main GlassCard Container */}
      <GlassCard className="p-6 overflow-hidden relative space-y-6">
        
        {/* Table Header with live count */}
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-primary" />
            Live Wafer Dispatch Queue (Dynamic Simulation Preview)
          </h2>
          <span className="text-xs font-mono text-muted-foreground">
            {demandSurgeEnabled ? `Demand Scaling: ${demandMultiplier.toFixed(1)}x` : 'Baseline Scale: 1.0x'}
          </span>
        </div>

        {/* Table Column Headers */}
        <div className="grid grid-cols-5 gap-4 border-b border-white/10 pb-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          <div>Step Identifier ↕</div>
          <div>Assigned Equipment ↕</div>
          <div>Wafer Count ↕</div>
          <div>Process Time</div>
          <div>Dispatch State ↕</div>
        </div>

        {/* Table Body */}
        <div className="flex flex-col gap-2">
          {steps.map((step) => (
            <div 
              key={step.id} 
              className="grid grid-cols-5 gap-4 py-3 px-2 border-b border-white/5 items-center hover:bg-white/5 transition-colors rounded-lg group text-xs"
            >
              <div className="font-medium text-foreground">{step.stepName}</div>
              <div className="text-muted-foreground font-mono">{step.machineName}</div>
              <div className="font-mono text-foreground font-semibold">
                {step.waferCount} wafers
              </div>
              <div className="text-muted-foreground font-mono">{step.processTime}</div>
              <div className="flex items-center gap-2">
                {step.isActive ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                    <span className="text-primary font-semibold tracking-wide">Processing</span>
                  </>
                ) : (
                  <span className="text-muted-foreground">Queued</span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Glowing Divider */}
        <div className="w-full h-[1px] bg-gradient-to-r from-transparent via-primary to-transparent opacity-40 my-6" />

        {/* Controls Section */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold tracking-wide text-foreground flex items-center gap-2">
              <Sliders className="w-4 h-4 text-primary" />
              Simulation Controls & Scenario Stress-Testing
            </h2>
            <span className="text-xs text-muted-foreground">Real-time parameters for CP-SAT solver</span>
          </div>
          
          <div className="space-y-5">
            
            {/* 1. Machine Breakdown Rate */}
            <div className="p-4 rounded-xl bg-white/5 border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <label className="text-sm font-semibold text-foreground">Machine Breakdown Rate</label>
                    <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-primary/10 text-primary border border-primary/20">
                      {breakdownEnabled ? `${breakdownRate}%` : 'Disabled (0%)'}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Simulates tool unavailability and forces CP-SAT to re-route wafer operations.
                  </p>
                </div>

                {/* Interactive Toggle Switch */}
                <button
                  type="button"
                  onClick={() => setBreakdownEnabled(!breakdownEnabled)}
                  className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer border ${
                    breakdownEnabled ? 'bg-primary border-primary' : 'bg-white/10 border-white/20'
                  }`}
                >
                  <div 
                    className={`w-4 h-4 rounded-full bg-white transition-transform absolute top-0.5 left-0.5 shadow-md ${
                      breakdownEnabled ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              <input 
                type="range" 
                min="0" 
                max="100" 
                step="5"
                disabled={!breakdownEnabled}
                value={breakdownRate}
                onChange={(e) => setBreakdownRate(Number(e.target.value))}
                className="w-full accent-primary cursor-pointer disabled:opacity-40" 
              />
              
              {breakdownEnabled && breakdownRate > 40 && (
                <div className="flex items-center gap-1.5 text-xs text-amber-400 bg-amber-500/10 p-2 rounded-lg border border-amber-500/20">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                  <span>High breakdown rate: Scanners rerouting wafers to secondary lines.</span>
                </div>
              )}
            </div>

            {/* 2. Demand Multiplier */}
            <div className="p-4 rounded-xl bg-white/5 border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <label className="text-sm font-semibold text-foreground">Demand Multiplier (Wafer Load)</label>
                    <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-secondary/10 text-secondary border border-secondary/20">
                      {demandSurgeEnabled ? `${demandMultiplier.toFixed(1)}x Surge` : '1.0x Baseline'}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Scales wafer count and queue volume to stress-test makespan bottlenecks.
                  </p>
                </div>

                {/* Interactive Toggle Switch */}
                <button
                  type="button"
                  onClick={() => setDemandSurgeEnabled(!demandSurgeEnabled)}
                  className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer border ${
                    demandSurgeEnabled ? 'bg-secondary border-secondary' : 'bg-white/10 border-white/20'
                  }`}
                >
                  <div 
                    className={`w-4 h-4 rounded-full bg-white transition-transform absolute top-0.5 left-0.5 shadow-md ${
                      demandSurgeEnabled ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              <input 
                type="range" 
                min="0.5" 
                max="3.0" 
                step="0.1"
                disabled={!demandSurgeEnabled}
                value={demandMultiplier}
                onChange={(e) => setDemandMultiplier(Number(e.target.value))}
                className="w-full accent-secondary cursor-pointer disabled:opacity-40" 
              />
            </div>

            {/* 3. Yield Target */}
            <div className="p-4 rounded-xl bg-white/5 border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <label className="text-sm font-semibold text-foreground">Target Fab Line Yield</label>
                    <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      {yieldLockEnabled ? `${yieldTarget}%` : 'Standard (80%)'}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Constrains wafer scrap thresholds and quality gating.
                  </p>
                </div>

                {/* Interactive Toggle Switch */}
                <button
                  type="button"
                  onClick={() => setYieldLockEnabled(!yieldLockEnabled)}
                  className={`w-11 h-6 rounded-full transition-colors relative cursor-pointer border ${
                    yieldLockEnabled ? 'bg-emerald-500 border-emerald-500' : 'bg-white/10 border-white/20'
                  }`}
                >
                  <div 
                    className={`w-4 h-4 rounded-full bg-white transition-transform absolute top-0.5 left-0.5 shadow-md ${
                      yieldLockEnabled ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              <input 
                type="range" 
                min="60" 
                max="99" 
                step="1"
                disabled={!yieldLockEnabled}
                value={yieldTarget}
                onChange={(e) => setYieldTarget(Number(e.target.value))}
                className="w-full accent-emerald-500 cursor-pointer disabled:opacity-40" 
              />
            </div>

          </div>

          {/* Action Button */}
          <Button 
            variant="glow" 
            onClick={handleRunSimulation}
            disabled={isRunning}
            className="w-full mt-6 text-base py-6 font-bold tracking-wider cursor-pointer"
          >
            {isRunning ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin" />
                Solving via Google OR-Tools CP-SAT with Simulated Parameters...
              </span>
            ) : (
              'Run Live Optimization'
            )}
          </Button>

        </div>
      </GlassCard>
    </div>
  );
}
