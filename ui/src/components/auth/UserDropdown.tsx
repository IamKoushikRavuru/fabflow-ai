import { useRef, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { 
  User, 
  LogOut, 
  Users, 
  Check, 
  LogIn, 
  Building2, 
  ShieldCheck 
} from 'lucide-react';

interface UserDropdownProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenProfile: () => void;
  onOpenAuth: () => void;
}

export function UserDropdown({ isOpen, onClose, onOpenProfile, onOpenAuth }: UserDropdownProps) {
  const { currentUser, isAuthenticated, logout, switchPersona, allPersonas } = useAuth();
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
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

  return (
    <div 
      ref={menuRef}
      className="absolute top-16 right-4 sm:right-6 w-80 max-w-[calc(100vw-2rem)] z-50 rounded-2xl bg-background/95 backdrop-blur-2xl border border-white/15 shadow-[0_20px_50px_rgba(0,0,0,0.6)] overflow-hidden animate-in fade-in slide-in-from-top-3 duration-200"
    >
      {isAuthenticated && currentUser ? (
        <>
          {/* User Profile Card */}
          <div className="p-4 border-b border-white/10 bg-white/[0.02]">
            <div className="flex items-center gap-3">
              <div className={`h-11 w-11 rounded-xl flex items-center justify-center font-bold text-sm border shadow-[0_0_15px_-3px_rgba(56,189,248,0.3)] ${currentUser.badgeColor}`}>
                {currentUser.initials}
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-bold text-foreground truncate">{currentUser.name}</h4>
                <p className="text-xs text-muted-foreground truncate">{currentUser.email}</p>
                <span className="inline-block mt-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-white/5 border border-white/10 text-primary truncate max-w-full">
                  {currentUser.role}
                </span>
              </div>
            </div>
            <div className="mt-3 flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <Building2 className="w-3.5 h-3.5 text-primary shrink-0" />
              <span className="truncate">{currentUser.facility}</span>
            </div>
          </div>

          {/* Persona Switcher */}
          <div className="p-3 border-b border-white/10 space-y-1">
            <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-2 mb-1 flex items-center gap-1">
              <Users className="w-3 h-3 text-primary" /> Switch Enterprise Persona
            </div>
            {allPersonas.slice(0, 3).map((persona) => (
              <button
                key={persona.id}
                onClick={() => {
                  switchPersona(persona.id);
                  onClose();
                }}
                className={`w-full text-left px-2.5 py-1.5 rounded-xl text-xs flex items-center justify-between transition-colors cursor-pointer ${
                  currentUser.id === persona.id 
                    ? 'bg-primary/10 text-primary font-semibold' 
                    : 'text-muted-foreground hover:text-foreground hover:bg-white/5'
                }`}
              >
                <div className="truncate">
                  <div className="font-medium truncate">{persona.name}</div>
                  <div className="text-[10px] opacity-70 truncate">{persona.role}</div>
                </div>
                {currentUser.id === persona.id && (
                  <Check className="w-3.5 h-3.5 text-primary shrink-0 ml-2" />
                )}
              </button>
            ))}
          </div>

          {/* Quick Actions */}
          <div className="p-2 space-y-1 text-xs">
            <button
              onClick={() => {
                onClose();
                onOpenProfile();
              }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors cursor-pointer"
            >
              <User className="w-4 h-4 text-primary" />
              Edit Profile & Credentials
            </button>
            <button
              onClick={() => {
                onClose();
                onOpenAuth();
              }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-muted-foreground hover:text-foreground hover:bg-white/5 transition-colors cursor-pointer"
            >
              <ShieldCheck className="w-4 h-4 text-secondary" />
              Sign in with Another Account
            </button>
            <button
              onClick={() => {
                logout();
                onClose();
              }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
              Sign Out
            </button>
          </div>
        </>
      ) : (
        <div className="p-5 text-center space-y-3">
          <div className="h-12 w-12 rounded-2xl bg-primary/10 text-primary mx-auto flex items-center justify-center">
            <User className="w-6 h-6" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-foreground">Sign In to FabFlow AI</h4>
            <p className="text-xs text-muted-foreground mt-1">
              Access real-time semiconductor schedules, CP-SAT optimization, and audit reports.
            </p>
          </div>
          <button
            onClick={() => {
              onClose();
              onOpenAuth();
            }}
            className="w-full py-2.5 px-4 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-semibold text-xs flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(56,189,248,0.4)] cursor-pointer"
          >
            <LogIn className="w-4 h-4" /> Sign In / Demo Accounts
          </button>
        </div>
      )}
    </div>
  );
}
