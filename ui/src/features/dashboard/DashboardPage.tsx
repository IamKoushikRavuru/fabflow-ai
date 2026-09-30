import React, { useEffect, useState } from 'react';
import { DashboardService } from '@/services/DashboardService';
import { type SystemHealth, type KPI, type Machine, type ScheduleTask } from '@/types';
import { SystemHealthCard } from './SystemHealthCard';
import { MetricCard } from '@/components/shared/MetricCard';
import { GlassCard } from '@/components/shared/GlassCard';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { Hourglass, Activity, Target, Zap, Clock, Box, RefreshCw, Layers } from 'lucide-react';

const KPI_ICONS: Record<string, React.ReactNode> = {
  makespan: <Hourglass size={16} />,
  utilization: <Activity size={16} />,
  throughput: <Target size={16} />,
  yield: <Zap size={16} />,
  cycleTime: <Clock size={16} />,
  wip: <Box size={16} />,
};

export default function DashboardPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [tasks, setTasks] = useState<ScheduleTask[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadData = async () => {
    setIsRefreshing(true);
    try {
      const [h, k, m, t] = await Promise.all([
        DashboardService.getSystemHealth(),
        DashboardService.getKPIs(),
        DashboardService.getMachineOverview(),
        DashboardService.getRecentSchedule(),
      ]);
      setHealth(h);
      setKpis(k);
      setMachines(m);
      setTasks(t);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();

    const handleSync = () => {
      // Background silent refresh
      Promise.all([
        DashboardService.getSystemHealth(),
        DashboardService.getKPIs(),
        DashboardService.getMachineOverview(),
        DashboardService.getRecentSchedule(),
      ]).then(([h, k, m, t]) => {
        setHealth(h);
        setKpis(k);
        setMachines(m);
        setTasks(t);
      }).catch(err => console.debug('Sync update caught:', err));
    };

    window.addEventListener('fabflow:sync', handleSync);
    return () => window.removeEventListener('fabflow:sync', handleSync);
  }, []);

  return (
    <div className="flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      {/* Hero Section */}
      <GlassCard className="p-8 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-purple-500/10 to-transparent pointer-events-none mix-blend-screen" />
        
        {/* Animated Mesh Background Simulation */}
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-primary/20 rounded-full blur-[80px]" />
        
        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-2 text-transparent bg-clip-text bg-gradient-to-r from-white to-white/70">
              Decision<br/>Intelligence
            </h1>
            <p className="text-muted-foreground text-lg">AI-Optimized Semiconductor Manufacturing Platform.</p>
          </div>
          <button
            onClick={loadData}
            disabled={isRefreshing}
            className="self-start md:self-auto flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-sm font-medium text-foreground transition-all duration-200 cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-primary' : ''}`} />
            {isRefreshing ? 'Syncing...' : 'Sync Live'}
          </button>
        </div>
      </GlassCard>

      <SystemHealthCard health={health} />

      <section>
        <h2 className="text-lg font-medium tracking-wide mb-4">Key Performance Indicators</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {kpis.map(kpi => (
            <MetricCard key={kpi.id} kpi={kpi} icon={KPI_ICONS[kpi.id]} />
          ))}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium tracking-wide">Real-Time Production Schedule</h2>
          <span className="text-xs text-muted-foreground flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-primary" /> Active CP-SAT Pipeline
          </span>
        </div>
        <GlassCard className="p-6">
          <div className="flex flex-col gap-4">
            {tasks.map((task) => (
              <div key={task.id} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-foreground flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_8px_rgba(56,189,248,0.8)]" />
                    {task.stage}
                  </span>
                  <span className="text-muted-foreground font-mono">{task.startDate} → {task.endDate}</span>
                </div>
                <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden border border-white/5 relative">
                  <div 
                    className="h-full bg-gradient-to-r from-primary via-purple-500 to-primary rounded-full transition-all duration-500" 
                    style={{ width: `${task.progressPct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      </section>

      <section>
        <h2 className="text-lg font-medium tracking-wide mb-4">Machine Status Grid</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {machines.map(machine => (
            <GlassCard key={machine.id} className="p-4 flex items-center justify-between hover:border-primary/40 transition-colors">
              <div>
                <h4 className="font-medium text-foreground mb-1 text-sm">{machine.name}</h4>
                <div className="text-xs text-muted-foreground mb-2">{machine.type}</div>
                <StatusBadge status={machine.status} />
              </div>
              <StatusBadge status={machine.status} showText={false} className="scale-125" />
            </GlassCard>
          ))}
        </div>
      </section>

    </div>
  );
}
