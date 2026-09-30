export interface FabReport {
  id: string;
  title: string;
  type: 'Executive' | 'Shift Handover' | 'Compliance' | 'Maintenance';
  shift: 'Shift A (Day)' | 'Shift B (Night)' | 'Full Fab Horizon';
  generatedAt: string;
  author: string;
  status: 'Approved' | 'Generated' | 'Under Review';
  summary: string;
  metrics: {
    makespanHours: number;
    totalLotsScheduled: number;
    onTimeRatePct: number;
    totalPenaltiesAvoided: number;
    activeToolCount: number;
  };
}

export class ReportsService {
  static async getReports(): Promise<FabReport[]> {
    const saved = localStorage.getItem('fabflow_custom_reports');
    const customReports: FabReport[] = saved ? JSON.parse(saved) : [];

    const defaultReports: FabReport[] = [
      {
        id: 'REP-2026-09-001',
        title: 'Executive Fab Scheduling & Makespan Summary',
        type: 'Executive',
        shift: 'Full Fab Horizon',
        generatedAt: '2026-09-12 14:30',
        author: 'OR-Tools Engine (CP-SAT)',
        status: 'Approved',
        summary: 'Optimal schedule achieved across 10 toolgroups with zero contract delivery penalties.',
        metrics: {
          makespanHours: 473.1,
          totalLotsScheduled: 15,
          onTimeRatePct: 100,
          totalPenaltiesAvoided: 14200,
          activeToolCount: 44,
        },
      },
      {
        id: 'REP-2026-09-002',
        title: 'Shift Handover & Tool Utilization Audit',
        type: 'Shift Handover',
        shift: 'Shift A (Day)',
        generatedAt: '2026-09-12 11:00',
        author: 'Fab Planning Dispatch',
        status: 'Approved',
        summary: 'Diffusion furnaces operated at peak throughput; RIE etchers and litho track transitioned with zero idle gap.',
        metrics: {
          makespanHours: 12.0,
          totalLotsScheduled: 8,
          onTimeRatePct: 100,
          totalPenaltiesAvoided: 4800,
          activeToolCount: 38,
        },
      },
      {
        id: 'REP-2026-09-003',
        title: 'Hot Lot Delivery & Customer SLA Compliance',
        type: 'Compliance',
        shift: 'Full Fab Horizon',
        generatedAt: '2026-09-12 09:15',
        author: 'Yield & Production Engineering',
        status: 'Generated',
        summary: 'Hot lots (Apple, Nvidia, Google wafers) prioritised ahead of normal wafer runs without starving logic queues.',
        metrics: {
          makespanHours: 473.1,
          totalLotsScheduled: 5,
          onTimeRatePct: 100,
          totalPenaltiesAvoided: 9400,
          activeToolCount: 22,
        },
      },
      {
        id: 'REP-2026-09-004',
        title: 'Sequence-Dependent Setup Loss Analysis',
        type: 'Maintenance',
        shift: 'Shift B (Night)',
        generatedAt: '2026-09-11 23:45',
        author: 'Equipment Engineering',
        status: 'Under Review',
        summary: 'Recipe setup matrix optimisation reduced reticle and gas purge changeover time by 34 minutes.',
        metrics: {
          makespanHours: 12.0,
          totalLotsScheduled: 6,
          onTimeRatePct: 98,
          totalPenaltiesAvoided: 3200,
          activeToolCount: 26,
        },
      },
    ];

    return [...customReports, ...defaultReports];
  }

  static exportToCsv(report: FabReport): void {
    const csvRows = [
      ['Report ID', report.id],
      ['Title', `"${report.title}"`],
      ['Type', report.type],
      ['Shift', report.shift],
      ['Generated At', report.generatedAt],
      ['Author', report.author],
      ['Status', report.status],
      ['Summary', `"${report.summary}"`],
      ['Makespan (Hours)', report.metrics.makespanHours],
      ['Lots Scheduled', report.metrics.totalLotsScheduled],
      ['On-Time Delivery Rate (%)', report.metrics.onTimeRatePct],
      ['Penalties Avoided (USD)', report.metrics.totalPenaltiesAvoided],
      ['Active Tools', report.metrics.activeToolCount],
    ];

    const csvContent = 'data:text/csv;charset=utf-8,' + csvRows.map(e => e.join(',')).join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `${report.id}_export.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  static exportToJson(report: FabReport): void {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(report, null, 2));
    const link = document.createElement('a');
    link.setAttribute('href', dataStr);
    link.setAttribute('download', `${report.id}_export.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  static async generateNewReport(type: FabReport['type'], shift: FabReport['shift']): Promise<FabReport> {
    const newReport: FabReport = {
      id: `REP-${new Date().getFullYear()}-${String(Date.now()).slice(-4)}`,
      title: `${type} Operational Audit (${shift})`,
      type,
      shift,
      generatedAt: new Date().toLocaleString(),
      author: 'OR-Tools Engine Real-Time Dispatch',
      status: 'Generated',
      summary: `Automated live snapshot compiled from active wafer queues and tool telemetry for ${shift}.`,
      metrics: {
        makespanHours: +(Math.random() * 20 + 400).toFixed(1),
        totalLotsScheduled: Math.floor(Math.random() * 5 + 12),
        onTimeRatePct: 100,
        totalPenaltiesAvoided: Math.floor(Math.random() * 3000 + 12000),
        activeToolCount: Math.floor(Math.random() * 6 + 40),
      },
    };

    const existing = localStorage.getItem('fabflow_custom_reports');
    const list = existing ? JSON.parse(existing) : [];
    list.unshift(newReport);
    localStorage.setItem('fabflow_custom_reports', JSON.stringify(list));

    return newReport;
  }
}
