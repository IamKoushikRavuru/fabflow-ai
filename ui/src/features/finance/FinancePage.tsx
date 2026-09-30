import { useEffect, useState } from 'react';
import { FinanceService } from '@/services/FinanceService';
import { type FinancialMetrics } from '@/types';
import { GlassCard } from '@/components/shared/GlassCard';
import { Button } from '@/components/ui/button';
import { Trophy, MoreVertical, ChevronRight } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Cell
} from 'recharts';

export default function FinancePage() {
  const [metrics, setMetrics] = useState<FinancialMetrics[]>([]);

  useEffect(() => {
    FinanceService.getStrategyComparison().then(setMetrics);
  }, []);

  return (
    <div className="flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto">
      
      <header className="mb-2">
        <h1 className="text-3xl font-bold tracking-tight">Financial Intelligence & Decision Explorer</h1>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {metrics.map((strategy) => (
          <GlassCard 
            key={strategy.strategyName} 
            active={strategy.isAiOptimized}
            className="p-6 flex flex-col gap-6"
          >
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-2xl font-bold">{strategy.strategyName}</h2>
                <p className="text-muted-foreground">
                  {strategy.isAiOptimized ? '(FabFlow Strategy)' : '(Traditional Strategy)'}
                </p>
                {strategy.isAiOptimized && (
                  <div className="mt-3 flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 bg-status-running/20 text-status-running px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide border border-status-running/30">
                      <Trophy size={14} /> Winner
                    </span>
                    <span className="text-status-running text-xs font-bold uppercase tracking-wide">
                      AI Optimized
                    </span>
                  </div>
                )}
              </div>
              <button className="text-muted-foreground hover:text-foreground transition-colors p-2 rounded-full hover:bg-white/5">
                <MoreVertical size={20} />
              </button>
            </div>

            {/* Cost Breakdown Chart (Simplified Waterfall) */}
            <div className="rounded-xl border border-white/5 bg-black/20 p-4">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-lg">Cost Breakdown</h3>
                  <p className="text-sm text-muted-foreground">(Million USD)</p>
                </div>
                <ChevronRight className="text-muted-foreground" size={20} />
              </div>
              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={[
                    { name: 'Raw', value: strategy.costBreakdown.rawMaterials },
                    { name: 'Labor', value: strategy.costBreakdown.labor },
                    { name: 'Energy', value: strategy.costBreakdown.energy },
                    { name: 'Maint.', value: Math.abs(strategy.costBreakdown.maintenance) },
                    { name: 'Yield', value: Math.abs(strategy.costBreakdown.yieldLoss) },
                    { name: 'Total', value: strategy.costBreakdown.total }
                  ]}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#888' }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#888' }} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {
                        [0, 1, 2, 3, 4, 5].map((_entry, index) => (
                          <Cell key={`cell-${index}`} fill={
                            index === 5 ? (strategy.isAiOptimized ? '#8b5cf6' : '#3b82f6') : 
                            strategy.isAiOptimized ? '#2dd4bf' : '#38bdf8'
                          } />
                        ))
                      }
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Revenue Impact Chart */}
            <div className="rounded-xl border border-white/5 bg-black/20 p-4">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-lg">Revenue Impact</h3>
                  <p className="text-sm text-muted-foreground">(Million USD)</p>
                </div>
                <ChevronRight className="text-muted-foreground" size={20} />
              </div>
              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={[
                    { name: 'Sales', value: strategy.revenueImpact.projectedSales },
                    { name: 'Demand', value: strategy.revenueImpact.marketDemand },
                    { name: 'Time', value: strategy.revenueImpact.timeToMarket }
                  ]}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#888' }} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#888' }} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {
                        [0, 1, 2].map((_entry, index) => (
                          <Cell key={`cell-${index}`} fill={strategy.isAiOptimized ? '#6366f1' : '#38bdf8'} />
                        ))
                      }
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <Button variant="outline" className="w-full mt-auto font-bold tracking-wide py-6 rounded-2xl">
              VIEW FULL ANALYSIS
            </Button>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
