import React, { createContext, useContext, useState } from 'react';

export type AlertSeverity = 'CRITICAL' | 'WARNING' | 'SUCCESS' | 'INFO';

export interface FabNotification {
  id: string;
  title: string;
  message: string;
  severity: AlertSeverity;
  timestamp: string;
  isRead: boolean;
  category: 'HOT_LOT' | 'TOOL_PM' | 'SOLVER' | 'AUDIT';
}

const DEFAULT_NOTIFICATIONS: FabNotification[] = [
  {
    id: 'notif-1',
    title: 'Hot Lot Priority Dispatch Alert',
    message: 'Hot Lot LOT-HOT-001 (Apple-Sim 7nm) approaching DUV Lithography scanner LITH-01 queue.',
    severity: 'CRITICAL',
    timestamp: 'Just now',
    isRead: false,
    category: 'HOT_LOT',
  },
  {
    id: 'notif-2',
    title: 'Tool Maintenance Scheduled (PM)',
    message: 'Diffusion Furnace FE_120-11 entering planned chamber clean in 35 minutes.',
    severity: 'WARNING',
    timestamp: '12m ago',
    isRead: false,
    category: 'TOOL_PM',
  },
  {
    id: 'notif-3',
    title: 'CP-SAT Optimization Succeeded',
    message: 'OR-Tools CP-SAT solved Flexible Job Shop schedule to OPTIMAL state in 0.300s. Zero contract delay.',
    severity: 'SUCCESS',
    timestamp: '25m ago',
    isRead: false,
    category: 'SOLVER',
  },
  {
    id: 'notif-4',
    title: 'Shift Handover Audit Signed Off',
    message: 'Shift A handover report REP-2026-6688 certified with 99.5% delivery compliance.',
    severity: 'INFO',
    timestamp: '1h ago',
    isRead: true,
    category: 'AUDIT',
  },
];

interface NotificationContextType {
  notifications: FabNotification[];
  unreadCount: number;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  clearAll: () => void;
  simulateAlert: () => void;
  addNotification: (notif: Omit<FabNotification, 'id' | 'timestamp' | 'isRead'>) => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<FabNotification[]>(() => {
    const saved = localStorage.getItem('fabflow_notifications');
    return saved ? JSON.parse(saved) : DEFAULT_NOTIFICATIONS;
  });

  const unreadCount = notifications.filter(n => !n.isRead).length;

  const markAsRead = (id: string) => {
    setNotifications(prev => {
      const updated = prev.map(n => n.id === id ? { ...n, isRead: true } : n);
      localStorage.setItem('fabflow_notifications', JSON.stringify(updated));
      return updated;
    });
  };

  const markAllAsRead = () => {
    setNotifications(prev => {
      const updated = prev.map(n => ({ ...n, isRead: true }));
      localStorage.setItem('fabflow_notifications', JSON.stringify(updated));
      return updated;
    });
  };

  const clearAll = () => {
    setNotifications([]);
    localStorage.setItem('fabflow_notifications', JSON.stringify([]));
  };

  const simulateAlert = () => {
    const alerts: Array<Omit<FabNotification, 'id' | 'timestamp' | 'isRead'>> = [
      {
        title: 'Thermal Purge Cycle Complete',
        message: 'LPCVD Chamber DEP-02 completed purge cycle for Recipe DEP-LPCVD-Poly. Ready for wafer loading.',
        severity: 'SUCCESS',
        category: 'TOOL_PM',
      },
      {
        title: 'Hot Lot Interconnect Etch Complete',
        message: 'Hot Lot LOT-HOT-002 (Nvidia-Sim 5nm) finished reactive ion etch on ETCH-01.',
        severity: 'INFO',
        category: 'HOT_LOT',
      },
      {
        title: 'Chamber Pressure Fluctuation Detected',
        message: 'Minor vacuum variance on CMP-01 slurry dispense unit. Auto-recalibrated by sub-system.',
        severity: 'WARNING',
        category: 'TOOL_PM',
      },
      {
        title: 'High-Priority Customer SLA Alert',
        message: 'Google-Sim Memory Lot approaching 4-hour window for STI Planarisation on CMP-01.',
        severity: 'CRITICAL',
        category: 'HOT_LOT',
      },
    ];

    const pick = alerts[Math.floor(Math.random() * alerts.length)];
    const newNotif: FabNotification = {
      id: `notif-${Date.now()}`,
      ...pick,
      timestamp: 'Just now',
      isRead: false,
    };

    setNotifications(prev => {
      const updated = [newNotif, ...prev];
      localStorage.setItem('fabflow_notifications', JSON.stringify(updated));
      return updated;
    });
  };

  const addNotification = (notif: Omit<FabNotification, 'id' | 'timestamp' | 'isRead'>) => {
    const newNotif: FabNotification = {
      id: `notif-${Date.now()}`,
      ...notif,
      timestamp: 'Just now',
      isRead: false,
    };
    setNotifications(prev => {
      const updated = [newNotif, ...prev];
      localStorage.setItem('fabflow_notifications', JSON.stringify(updated));
      return updated;
    });
  };

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        unreadCount,
        markAsRead,
        markAllAsRead,
        clearAll,
        simulateAlert,
        addNotification,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
}
