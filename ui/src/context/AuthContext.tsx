import React, { createContext, useContext, useState, useEffect } from 'react';

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: string;
  department: string;
  facility: string;
  initials: string;
  badgeColor: string;
  notifications: {
    emailAlerts: boolean;
    pushAlerts: boolean;
    smsHotLotAlerts: boolean;
  };
}

export const ENTERPRISE_PERSONAS: UserProfile[] = [
  {
    id: 'dr-thorne',
    name: 'Dr. Aris Thorne',
    email: 'a.thorne@fabflow.ai',
    role: 'VP of Fab Operations & AI',
    department: 'Executive Operations & Planning',
    facility: 'Fab 12 — Hsinchu 300mm Advanced Pilot Node',
    initials: 'AT',
    badgeColor: 'bg-primary/20 text-primary border-primary/30',
    notifications: {
      emailAlerts: true,
      pushAlerts: true,
      smsHotLotAlerts: true,
    },
  },
  {
    id: 'elena-rostova',
    name: 'Elena Rostova',
    email: 'e.rostova@fabflow.ai',
    role: 'Senior Fab Dispatch Planner',
    department: 'Real-Time Dispatch & Production Scheduling',
    facility: 'Fab 12 — Hsinchu 300mm Advanced Pilot Node',
    initials: 'ER',
    badgeColor: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    notifications: {
      emailAlerts: true,
      pushAlerts: true,
      smsHotLotAlerts: true,
    },
  },
  {
    id: 'marcus-vance',
    name: 'Marcus Vance',
    email: 'm.vance@fabflow.ai',
    role: 'Principal Equipment & Yield Engineer',
    department: 'Tool Maintenance & Defect Metrology',
    facility: 'Fab 12 — Hsinchu 300mm Advanced Pilot Node',
    initials: 'MV',
    badgeColor: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    notifications: {
      emailAlerts: false,
      pushAlerts: true,
      smsHotLotAlerts: false,
    },
  },
];

interface AuthContextType {
  currentUser: UserProfile | null;
  isAuthenticated: boolean;
  login: (email: string, pass: string) => Promise<boolean>;
  register: (name: string, email: string, role: string, facility: string) => Promise<void>;
  logout: () => void;
  switchPersona: (personaId: string) => void;
  updateProfile: (updates: Partial<UserProfile>) => void;
  allPersonas: UserProfile[];
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem('fabflow_user_profile');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        // fallback
      }
    }
    return ENTERPRISE_PERSONAS[0]; // Default to Dr. Aris Thorne
  });

  const [allPersonas, setAllPersonas] = useState<UserProfile[]>(() => {
    const saved = localStorage.getItem('fabflow_all_personas');
    return saved ? JSON.parse(saved) : ENTERPRISE_PERSONAS;
  });

  useEffect(() => {
    if (currentUser) {
      localStorage.setItem('fabflow_user_profile', JSON.stringify(currentUser));
    } else {
      localStorage.removeItem('fabflow_user_profile');
    }
  }, [currentUser]);

  const login = async (email: string, _pass: string): Promise<boolean> => {
    // Check if exists in personas
    const existing = allPersonas.find(p => p.email.toLowerCase() === email.toLowerCase());
    if (existing) {
      setCurrentUser(existing);
      return true;
    }
    // Generic fallback login
    const generic: UserProfile = {
      id: `user-${Date.now()}`,
      name: email.split('@')[0],
      email,
      role: 'Fab Planning Analyst',
      department: 'Fab Operations',
      facility: 'Fab 12 — Hsinchu 300mm Advanced Pilot Node',
      initials: email.slice(0, 2).toUpperCase(),
      badgeColor: 'bg-primary/20 text-primary border-primary/30',
      notifications: { emailAlerts: true, pushAlerts: true, smsHotLotAlerts: false },
    };
    setCurrentUser(generic);
    return true;
  };

  const register = async (name: string, email: string, role: string, facility: string) => {
    const initials = name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2) || 'FA';

    const newUser: UserProfile = {
      id: `user-${Date.now()}`,
      name,
      email,
      role,
      department: 'Fab Production & Operations',
      facility: facility || 'Fab 12 — Hsinchu 300mm Advanced Pilot Node',
      initials,
      badgeColor: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
      notifications: { emailAlerts: true, pushAlerts: true, smsHotLotAlerts: true },
    };

    const updated = [newUser, ...allPersonas];
    setAllPersonas(updated);
    localStorage.setItem('fabflow_all_personas', JSON.stringify(updated));
    setCurrentUser(newUser);
  };

  const logout = () => {
    setCurrentUser(null);
  };

  const switchPersona = (personaId: string) => {
    const target = allPersonas.find(p => p.id === personaId);
    if (target) {
      setCurrentUser(target);
    }
  };

  const updateProfile = (updates: Partial<UserProfile>) => {
    if (!currentUser) return;
    const updated = { ...currentUser, ...updates };
    setCurrentUser(updated);

    const updatedAll = allPersonas.map(p => p.id === currentUser.id ? updated : p);
    setAllPersonas(updatedAll);
    localStorage.setItem('fabflow_all_personas', JSON.stringify(updatedAll));
  };

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        isAuthenticated: !!currentUser,
        login,
        register,
        logout,
        switchPersona,
        updateProfile,
        allPersonas,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
