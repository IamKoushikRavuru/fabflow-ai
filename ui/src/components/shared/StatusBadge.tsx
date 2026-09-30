import { cn } from '@/lib/utils';
import { type MachineStatus } from '@/types';

interface StatusBadgeProps {
  status: MachineStatus;
  className?: string;
  showText?: boolean;
}

export function StatusBadge({ status, className, showText = true }: StatusBadgeProps) {
  let colorClass = '';
  switch (status) {
    case 'Running':
      colorClass = 'bg-status-running text-status-running border-status-running/30 shadow-[0_0_10px_-2px_rgba(34,197,94,0.5)]';
      break;
    case 'Idle':
      colorClass = 'bg-status-idle text-status-idle border-status-idle/30 shadow-[0_0_10px_-2px_rgba(245,158,11,0.5)]';
      break;
    case 'Maintenance':
      colorClass = 'bg-status-maintenance text-status-maintenance border-status-maintenance/30 shadow-[0_0_10px_-2px_rgba(239,68,68,0.5)]';
      break;
    case 'Offline':
      colorClass = 'bg-muted-foreground text-muted-foreground border-border/50';
      break;
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className={cn('h-3 w-3 rounded-md border', colorClass.split(' ')[0], colorClass.split(' ')[2], colorClass.split(' ')[3])} />
      {showText && <span className={cn('text-xs font-medium', colorClass.split(' ')[1])}>{status}</span>}
    </div>
  );
}
