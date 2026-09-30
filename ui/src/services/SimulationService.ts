import { SimulationStep, OptimizationResult } from '@/types';
import { fetchApi } from '@/lib/api';
import { SettingsService } from './SettingsService';

interface BackendLot {
  id: number;
  name: string;
  priority: string;
  wafer_count: number;
  operations: Array<{
    id: number;
    sequence_num: number;
    processing_time_minutes: number;
  }>;
}

interface BackendScheduleResponse {
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
  gantt_data?: {
    tasks: Array<{
      lot_id: number;
      lot_name: string;
      sequence_num: number;
      machine_name: string;
      stage: string;
      duration_minutes: number;
    }>;
  };
}

export class SimulationService {
  static async getSimulationSteps(params?: {
    breakdownRate?: number;
    breakdownEnabled?: boolean;
    demandMultiplier?: number;
    yieldTarget?: number;
  }): Promise<SimulationStep[]> {
    const mult = params?.demandMultiplier ?? 1.2;
    const isBreakdownHigh = (params?.breakdownRate ?? 30) > 40 && (params?.breakdownEnabled ?? true);

    try {
      const lots = await fetchApi<BackendLot[]>('/jobs');
      if (lots && lots.length > 0) {
        const steps: SimulationStep[] = [];
        lots.slice(0, 6).forEach((lot) => {
          lot.operations.slice(0, 1).forEach((op) => {
            const calculatedWafers = Math.round((lot.wafer_count || 25) * mult);
            const extraTime = isBreakdownHigh ? 15 : 0;
            const procTime = (op.processing_time_minutes || 45) + extraTime;
            const machine = isBreakdownHigh && op.sequence_num === 0
              ? 'Backup Scanner (Rerouted)'
              : lot.priority === 'HOT'
              ? 'Scanner LITH-01 (Priority Line)'
              : 'Etch Chamber ETCH-01';

            steps.push({
              id: `step-${lot.id}-${op.id}`,
              stepName: `${lot.name} (Step #${op.sequence_num + 1})`,
              machineName: machine,
              waferCount: calculatedWafers,
              processTime: `${procTime}m`,
              isActive: lot.priority === 'HOT' || isBreakdownHigh,
            });
          });
        });
        if (steps.length > 0) return steps;
      }
    } catch {
      // fallback
    }

    const calculatedWafers = Math.round(25 * mult);
    const extraTime = isBreakdownHigh ? 15 : 0;

    return [
      { id: '1', stepName: 'HotLot-0001 (Gate Litho)', machineName: isBreakdownHigh ? 'Scanner LITH-02 (Rerouted)' : 'LITH-01 Scanner', waferCount: calculatedWafers, processTime: `${45 + extraTime}m`, isActive: true },
      { id: '2', stepName: 'HotLot-0002 (Interconnect)', machineName: 'ETCH-01 RIE', waferCount: calculatedWafers, processTime: `${30 + extraTime}m`, isActive: true },
      { id: '3', stepName: 'Lot-Logic-01 (Dielectric)', machineName: isBreakdownHigh ? 'CVD DEP-02 (Derated)' : 'DEP-01 CVD', waferCount: calculatedWafers, processTime: `${50 + extraTime}m`, isActive: false },
      { id: '4', stepName: 'Lot-Logic-02 (Planarize)', machineName: 'CMP-01 Tool', waferCount: calculatedWafers, processTime: `${40 + extraTime}m`, isActive: false },
      { id: '5', stepName: 'Lot-Mem-01 (Dopant Implant)', machineName: 'IMP-01 Implanter', waferCount: calculatedWafers, processTime: `${25 + extraTime}m`, isActive: false },
      { id: '6', stepName: 'Lot-Mem-02 (Metrology SEM)', machineName: 'INSP-01 SEM', waferCount: calculatedWafers, processTime: `${15 + extraTime}m`, isActive: false },
    ];
  }

  static async runOptimization(params?: {
    lotCount?: number;
    breakdownRate?: number;
    breakdownEnabled?: boolean;
    demandMultiplier?: number;
    yieldTarget?: number;
    solverTimeLimit?: number;
  }): Promise<OptimizationResult> {
    const settings = SettingsService.getSettings();
    const lotIds = [1, 2, 3, 4, 5];
    const mult = params?.demandMultiplier ?? 1.2;
    const includeMaint = params?.breakdownEnabled ? (params.breakdownRate || 0) > 20 : settings.includeMaintenance;
    const includeFail = params?.breakdownEnabled ? (params.breakdownRate || 0) > 50 : settings.includeFailures;

    const payload = {
      lot_ids: lotIds,
      max_ops_per_lot: settings.maxOpsPerLot || 8,
      horizon_minutes: Math.round((settings.horizonMinutes || 6000) * mult),
      solver_time_limit_seconds: params?.solverTimeLimit || settings.solverTimeLimitSeconds || 15,
      weights: settings.weights || {
        makespan: 1.0,
        idle_time: 0.5,
        weighted_tardiness: 2.0,
        penalty_cost: 3.0,
      },
      include_maintenance: includeMaint,
      include_failures: includeFail,
    };

    const response = await fetchApi<BackendScheduleResponse>('/schedule/run', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    return {
      id: response.id,
      status: response.status,
      makespan_minutes: response.makespan_minutes,
      solver_wall_time_seconds: response.solver_wall_time_seconds,
      objective_value: response.objective_value,
      kpi_data: response.kpi_data ? {
        avg_machine_utilization_pct: response.kpi_data.avg_machine_utilization_pct,
        total_penalty_cost: response.kpi_data.total_penalty_cost,
        total_weighted_tardiness: response.kpi_data.total_weighted_tardiness,
        makespan_minutes: response.kpi_data.makespan_minutes,
      } : undefined,
      tasks_count: response.gantt_data?.tasks?.length || 0,
    };
  }
}
