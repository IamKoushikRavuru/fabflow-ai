import React from 'react';
import { GlassCard } from './GlassCard';
import { cn } from '@/lib/utils';
import { type KPI } from '@/types';
import { ArrowDownRight, ArrowUpRight } from 'lucide-react';

interface MetricCardProps {
  kpi: KPI;
  icon?: React.ReactNode;
  className?: string;
}

export function MetricCard({ kpi, icon, className }: MetricCardProps) {
  return (
    <GlassCard className={cn('p-5 flex flex-col justify-between gap-4', className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-muted-foreground">
          {icon && <span className="opacity-70">{icon}</span>}
          <span className="text-sm font-medium">{kpi.label}</span>
        </div>
        {kpi.isLive && (
          <div className="flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-status-running opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-status-running shadow-[0_0_8px_rgba(34,197,94,0.8)]"></span>
            </span>
            <span className="text-[10px] uppercase font-bold tracking-wider text-status-running">Live</span>
          </div>
        )}
      </div>

      <div>
        <div className="text-3xl font-semibold tracking-tight text-foreground mb-1">
          {kpi.value}
        </div>
        <div className="flex items-center gap-1 text-sm">
          <span className={cn(
            'flex items-center font-medium',
            kpi.trend.isPositive ? 'text-status-running' : 'text-status-maintenance'
          )}>
            {kpi.trend.value}
            {kpi.trend.isPositive ? <ArrowUpRight className="h-3 w-3 ml-0.5" /> : <ArrowDownRight className="h-3 w-3 ml-0.5" />}
          </span>
        </div>
      </div>
    </GlassCard>
  );
}
