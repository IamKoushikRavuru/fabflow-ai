import { FinancialMetrics } from '@/types';

export class FinanceService {
  static async getStrategyComparison(): Promise<FinancialMetrics[]> {
    return [
      {
        strategyName: 'FIFO',
        isAiOptimized: false,
        costBreakdown: {
          rawMaterials: 45.2,
          labor: 23.4,
          energy: 14.1,
          maintenance: 8.9,
          yieldLoss: 12.0,
          total: 83.6
        },
        revenueImpact: {
          projectedSales: 230,
          marketDemand: 290,
          timeToMarket: 380
        }
      },
      {
        strategyName: 'AI Optimized',
        isAiOptimized: true,
        costBreakdown: {
          rawMaterials: 34.1,
          labor: 21.5,
          energy: 10.9,
          maintenance: -4.5,
          yieldLoss: -36.5,
          total: 12.5
        },
        revenueImpact: {
          projectedSales: 1500,
          marketDemand: 2250,
          timeToMarket: 290
        }
      }
    ];
  }
}
