import React, { useState } from 'react';
import { useAuth, ENTERPRISE_PERSONAS } from '@/context/AuthContext';
import { GlassCard } from '@/components/shared/GlassCard';
import { Button } from '@/components/ui/button';
import { 
  Lock, 
  Mail, 
  User, 
  Briefcase, 
  Building2, 
  Sparkles, 
  X, 
  CheckCircle2 
} from 'lucide-react';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AuthModal({ isOpen, onClose }: AuthModalProps) {
  const { login, register, switchPersona } = useAuth();
  const [mode, setMode] = useState<'LOGIN' | 'REGISTER'>('LOGIN');

  // Login form
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPass, setLoginPass] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  // Register form
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regRole, setRegRole] = useState('Senior Dispatch Engineer');
  const [regFacility, setRegFacility] = useState('Fab 12 — Hsinchu 300mm Advanced Pilot Node');
  const [regLoading, setRegLoading] = useState(false);

  if (!isOpen) return null;

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginEmail) return;
    setLoginLoading(true);
    try {
      await login(loginEmail, loginPass);
      onClose();
    } finally {
      setLoginLoading(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!regName || !regEmail) return;
    setRegLoading(true);
    try {
      await register(regName, regEmail, regRole, regFacility);
      onClose();
    } finally {
      setRegLoading(false);
    }
  };

  const handleQuickSignIn = (personaId: string) => {
    switchPersona(personaId);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-200">
      <GlassCard className="w-full max-w-md p-6 relative border border-white/20 shadow-[0_25px_60px_rgba(0,0,0,0.8)] overflow-hidden">
        
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-white/10 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="text-center mb-6">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary to-purple-600 mx-auto flex items-center justify-center mb-3 shadow-[0_0_15px_rgba(56,189,248,0.5)]">
            <Lock className="w-5 h-5 text-white" />
          </div>
          <h2 className="text-xl font-bold text-foreground">FabFlow AI Enterprise Access</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Certified Semiconductor Dispatch & Mathematical Optimization
          </p>
        </div>

        {/* Mode Toggle Tabs */}
        <div className="flex rounded-xl bg-white/5 p-1 mb-5 text-xs font-medium border border-white/5">
          <button
            onClick={() => setMode('LOGIN')}
            className={`flex-1 py-1.5 rounded-lg transition-all cursor-pointer ${
              mode === 'LOGIN' 
                ? 'bg-primary text-primary-foreground font-semibold shadow-[0_0_10px_rgba(56,189,248,0.4)]' 
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Sign In
          </button>
          <button
            onClick={() => setMode('REGISTER')}
            className={`flex-1 py-1.5 rounded-lg transition-all cursor-pointer ${
              mode === 'REGISTER' 
                ? 'bg-primary text-primary-foreground font-semibold shadow-[0_0_10px_rgba(56,189,248,0.4)]' 
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Create Account
          </button>
        </div>

        {mode === 'LOGIN' ? (
          <div className="space-y-5">
            {/* Quick Demo Personas */}
            <div className="space-y-2">
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-primary" /> Instant Enterprise Demo Accounts
              </span>
              <div className="space-y-1.5">
                {ENTERPRISE_PERSONAS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => handleQuickSignIn(p.id)}
                    className="w-full p-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-left flex items-center justify-between transition-all cursor-pointer group"
                  >
                    <div>
                      <div className="text-xs font-bold text-foreground group-hover:text-primary transition-colors">
                        {p.name}
                      </div>
                      <div className="text-[10px] text-muted-foreground">{p.role}</div>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 border border-white/10 text-primary">
                      Demo Sign-In
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="relative flex py-1 items-center">
              <div className="flex-grow border-t border-white/10" />
              <span className="flex-shrink mx-3 text-[11px] text-muted-foreground uppercase font-mono">
                or use credentials
              </span>
              <div className="flex-grow border-t border-white/10" />
            </div>

            {/* Standard Login Form */}
            <form onSubmit={handleLoginSubmit} className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Corporate Email</label>
                <div className="relative">
                  <Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="email"
                    required
                    placeholder="planner@fabflow.ai"
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="password"
                    placeholder="••••••••••••"
                    value={loginPass}
                    onChange={(e) => setLoginPass(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
                  />
                </div>
              </div>

              <Button
                variant="glow"
                type="submit"
                disabled={loginLoading}
                className="w-full mt-2 font-bold text-xs py-5 cursor-pointer"
              >
                {loginLoading ? 'Authenticating...' : 'Sign In to Platform'}
              </Button>
            </form>
          </div>
        ) : (
          /* Register Form */
          <form onSubmit={handleRegisterSubmit} className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Full Name</label>
              <div className="relative">
                <User className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  required
                  placeholder="Alex Rivera"
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Corporate Email</label>
              <div className="relative">
                <Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="email"
                  required
                  placeholder="alex.rivera@fabflow.ai"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Job Title / Role</label>
              <div className="relative">
                <Briefcase className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  required
                  placeholder="Lead Equipment Planner"
                  value={regRole}
                  onChange={(e) => setRegRole(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Semiconductor Facility Node</label>
              <div className="relative">
                <Building2 className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={regFacility}
                  onChange={(e) => setRegFacility(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50"
                />
              </div>
            </div>

            <Button
              variant="glow"
              type="submit"
              disabled={regLoading}
              className="w-full mt-3 font-bold text-xs py-5 cursor-pointer"
            >
              {regLoading ? 'Creating Account...' : 'Register Corporate Account'}
            </Button>
          </form>
        )}

        <div className="mt-4 pt-3 border-t border-white/10 text-center text-[11px] text-muted-foreground flex items-center justify-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          <span>Role-Based Access Control Active (RBAC)</span>
        </div>

      </GlassCard>
    </div>
  );
}
