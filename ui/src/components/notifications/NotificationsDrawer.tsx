import { useState, useRef, useEffect } from 'react';
import { useNotifications, type AlertSeverity } from '@/context/NotificationContext';
import { 
  Bell, 
  Check, 
  Trash2, 
  Sparkles, 
  AlertOctagon, 
  AlertTriangle, 
  CheckCircle2, 
  Info,
  X
} from 'lucide-react';

interface NotificationsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export function NotificationsDrawer({ isOpen, onClose }: NotificationsDrawerProps) {
  const { notifications, unreadCount, markAsRead, markAllAsRead, clearAll, simulateAlert } = useNotifications();
  const [filter, setFilter] = useState<'ALL' | 'UNREAD' | 'CRITICAL'>('ALL');
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const filtered = notifications.filter(n => {
    if (filter === 'UNREAD') return !n.isRead;
    if (filter === 'CRITICAL') return n.severity === 'CRITICAL';
    return true;
  });

  const getSeverityIcon = (sev: AlertSeverity) => {
    switch (sev) {
      case 'CRITICAL':
        return <AlertOctagon className="w-4 h-4 text-rose-400 shrink-0" />;
      case 'WARNING':
        return <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />;
      case 'SUCCESS':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />;
      case 'INFO':
      default:
        return <Info className="w-4 h-4 text-primary shrink-0" />;
    }
  };

  return (
    <div 
      ref={drawerRef}
      className="absolute top-16 right-4 sm:right-6 w-96 max-w-[calc(100vw-2rem)] z-50 rounded-2xl bg-background/95 backdrop-blur-2xl border border-white/15 shadow-[0_20px_50px_rgba(0,0,0,0.6)] overflow-hidden animate-in fade-in slide-in-from-top-3 duration-200"
    >
      {/* Drawer Header */}
      <div className="p-4 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-bold text-foreground">Fab Notifications</h3>
          {unreadCount > 0 && (
            <span className="px-1.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-primary text-primary-foreground">
              {unreadCount}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          {unreadCount > 0 && (
            <button
              onClick={markAllAsRead}
              title="Mark all as read"
              className="text-[11px] text-muted-foreground hover:text-primary transition-colors flex items-center gap-1 px-2 py-1 rounded hover:bg-white/5 cursor-pointer"
            >
              <Check className="w-3 h-3" /> Mark all read
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1 text-muted-foreground hover:text-foreground rounded-lg hover:bg-white/5 cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1 px-4 py-2 border-b border-white/5 text-xs bg-white/[0.02]">
        {(['ALL', 'UNREAD', 'CRITICAL'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setFilter(tab)}
            className={`px-2.5 py-1 rounded-lg font-medium transition-colors cursor-pointer text-[11px] ${
              filter === tab
                ? 'bg-primary/20 text-primary border border-primary/30'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Notifications List */}
      <div className="max-h-80 overflow-y-auto divide-y divide-white/5">
        {filtered.length === 0 ? (
          <div className="p-8 text-center text-xs text-muted-foreground">
            No notifications in this filter.
          </div>
        ) : (
          filtered.map((notif) => (
            <div
              key={notif.id}
              onClick={() => markAsRead(notif.id)}
              className={`p-3.5 hover:bg-white/5 transition-colors cursor-pointer flex gap-3 relative ${
                !notif.isRead ? 'bg-primary/[0.03]' : ''
              }`}
            >
              <div className="mt-0.5">
                {getSeverityIcon(notif.severity)}
              </div>
              <div className="flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <h4 className={`text-xs font-semibold ${!notif.isRead ? 'text-foreground' : 'text-muted-foreground'}`}>
                    {notif.title}
                  </h4>
                  <span className="text-[10px] text-muted-foreground font-mono">{notif.timestamp}</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  {notif.message}
                </p>
              </div>
              {!notif.isRead && (
                <span className="w-1.5 h-1.5 rounded-full bg-primary absolute top-4 right-2 shadow-[0_0_6px_rgba(56,189,248,0.8)]" />
              )}
            </div>
          ))
        )}
      </div>

      {/* Drawer Footer Actions */}
      <div className="p-3 border-t border-white/10 bg-white/[0.02] flex items-center justify-between text-xs">
        <button
          onClick={simulateAlert}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-primary/10 hover:bg-primary/20 border border-primary/30 text-primary font-medium transition-colors cursor-pointer text-[11px]"
        >
          <Sparkles className="w-3.5 h-3.5" />
          Simulate Fab Alert
        </button>

        {notifications.length > 0 && (
          <button
            onClick={clearAll}
            className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-rose-400 transition-colors cursor-pointer px-2 py-1 rounded hover:bg-white/5"
          >
            <Trash2 className="w-3 h-3" /> Clear
          </button>
        )}
      </div>
    </div>
  );
}
