export type MachineStatus = 'Running' | 'Idle' | 'Maintenance' | 'Offline';
export type LotPriority = 'Normal' | 'Hot Lot' | 'Delayed';

export interface SystemHealth {
  backendConnection: { status: 'Connected' | 'Disconnected'; latencyMs: number };
  dataSync: { status: 'Synced' | 'Syncing' | 'Failed'; lastSync: string };
}

export interface KPI {
  id: string;
  label: string;
  value: string;
  trend: { value: string; isPositive: boolean };
  isLive: boolean;
}

export interface Machine {
  id: string;
  name: string;
  type: string;
  status: MachineStatus;
}

export interface ScheduleTask {
  id: string;
  stage: string;
  startDate: string;
  endDate: string;
  progressPct: number;
}

export interface SimulationStep {
  id: string;
  stepName: string;
  machineName: string;
  waferCount: number;
  processTime: string;
  isActive: boolean;
}

export interface FinancialMetrics {
  strategyName: string;
  isAiOptimized: boolean;
  costBreakdown: {
    rawMaterials: number;
    labor: number;
    energy: number;
    maintenance: number;
    yieldLoss: number;
    total: number;
  };
  revenueImpact: {
    projectedSales: number;
    marketDemand: number;
    timeToMarket: number;
  };
}

export interface OptimizationResult {
  id: number;
  status: string;
  makespan_minutes: number;
  solver_wall_time_seconds: number;
  objective_value?: number;
  kpi_data?: {
    avg_machine_utilization_pct: number;
    total_penalty_cost: number;
    total_weighted_tardiness: number;
    makespan_minutes: number;
  };
  tasks_count?: number;
}
