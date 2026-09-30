import { GlassCard } from '@/components/shared/GlassCard';
import { type SystemHealth } from '@/types';

export function SystemHealthCard({ health }: { health: SystemHealth | null }) {
  if (!health) return null;

  return (
    <GlassCard className="p-5 flex flex-col gap-3">
      <h3 className="text-sm font-semibold text-foreground tracking-wide">System Health</h3>
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 text-sm">
          <div className="h-2 w-2 rounded-full bg-status-running shadow-[0_0_8px_rgba(34,197,94,0.8)]" />
          <span className="text-muted-foreground">Backend Connection:</span>
          <span className="text-status-running font-medium">
            {health.backendConnection.status} ({health.backendConnection.latencyMs}ms)
          </span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <div className="h-2 w-2 rounded-full bg-status-running shadow-[0_0_8px_rgba(34,197,94,0.8)]" />
          <span className="text-muted-foreground">Data Sync:</span>
          <span className="text-status-running font-medium">
            {health.dataSync.status} ({health.dataSync.lastSync})
          </span>
        </div>
      </div>
    </GlassCard>
  );
}
