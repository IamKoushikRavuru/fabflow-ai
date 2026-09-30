import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { GlassCard } from '@/components/shared/GlassCard';
import { Button } from '@/components/ui/button';
import { 
  User, 
  Briefcase, 
  Building2, 
  Bell, 
  ShieldCheck, 
  X, 
  Save, 
  CheckCircle2 
} from 'lucide-react';

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ProfileModal({ isOpen, onClose }: ProfileModalProps) {
  const { currentUser, updateProfile } = useAuth();

  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [department, setDepartment] = useState('');
  const [facility, setFacility] = useState('');
  const [emailAlerts, setEmailAlerts] = useState(true);
  const [pushAlerts, setPushAlerts] = useState(true);
  const [smsHotLotAlerts, setSmsHotLotAlerts] = useState(true);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    if (currentUser) {
      setName(currentUser.name);
      setRole(currentUser.role);
      setDepartment(currentUser.department);
      setFacility(currentUser.facility);
      setEmailAlerts(currentUser.notifications.emailAlerts);
      setPushAlerts(currentUser.notifications.pushAlerts);
      setSmsHotLotAlerts(currentUser.notifications.smsHotLotAlerts);
    }
  }, [currentUser]);

  if (!isOpen || !currentUser) return null;

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    updateProfile({
      name,
      role,
      department,
      facility,
      notifications: {
        emailAlerts,
        pushAlerts,
        smsHotLotAlerts,
      },
    });
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      onClose();
    }, 1200);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-200">
      <GlassCard className="w-full max-w-lg p-6 relative border border-white/20 shadow-[0_25px_60px_rgba(0,0,0,0.8)] max-h-[90vh] overflow-y-auto">
        
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-white/10 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-4 mb-6 pb-4 border-b border-white/10">
          <div className={`h-14 w-14 rounded-2xl flex items-center justify-center font-bold text-lg border shadow-[0_0_15px_-3px_rgba(56,189,248,0.4)] ${currentUser.badgeColor}`}>
            {currentUser.initials}
          </div>
          <div>
            <h2 className="text-xl font-bold text-foreground">{currentUser.name}</h2>
            <p className="text-xs text-muted-foreground">{currentUser.email}</p>
            <span className="inline-block mt-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-white/5 border border-white/10 text-primary">
              {currentUser.role}
            </span>
          </div>
        </div>

        {savedSuccess && (
          <div className="mb-4 flex items-center gap-2 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium animate-in fade-in duration-200">
            <CheckCircle2 className="w-4 h-4" />
            Profile changes saved and synced across FabFlow AI sessions!
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4">
          
          {/* Section: Personal Info */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-primary" /> Identity & Position
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Full Name</label>
                <div className="relative">
                  <User className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-foreground focus:outline-none focus:border-primary/50"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Corporate Role</label>
                <div className="relative">
                  <Briefcase className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="text"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-foreground focus:outline-none focus:border-primary/50"
                  />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Department</label>
                <input
                  type="text"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-foreground focus:outline-none focus:border-primary/50"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Assigned Facility Node</label>
                <div className="relative">
                  <Building2 className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="text"
                    value={facility}
                    onChange={(e) => setFacility(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-foreground focus:outline-none focus:border-primary/50"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Section: Notifications */}
          <div className="space-y-2 pt-3 border-t border-white/10">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <Bell className="w-3.5 h-3.5 text-secondary" /> Automated Dispatch Alerts
            </h3>

            <div className="space-y-2">
              <label className="flex items-center justify-between p-2.5 rounded-xl bg-white/5 border border-white/5 cursor-pointer hover:bg-white/10 transition-colors">
                <span className="text-xs text-foreground">In-App Live Alerts (Tool PM & Solvers)</span>
                <input
                  type="checkbox"
                  checked={pushAlerts}
                  onChange={(e) => setPushAlerts(e.target.checked)}
                  className="h-4 w-4 rounded accent-primary cursor-pointer"
                />
              </label>

              <label className="flex items-center justify-between p-2.5 rounded-xl bg-white/5 border border-white/5 cursor-pointer hover:bg-white/10 transition-colors">
                <span className="text-xs text-foreground">Hot Lot Priority SLA Alerts (Immediate Dispatch)</span>
                <input
                  type="checkbox"
                  checked={smsHotLotAlerts}
                  onChange={(e) => setSmsHotLotAlerts(e.target.checked)}
                  className="h-4 w-4 rounded accent-primary cursor-pointer"
                />
              </label>

              <label className="flex items-center justify-between p-2.5 rounded-xl bg-white/5 border border-white/5 cursor-pointer hover:bg-white/10 transition-colors">
                <span className="text-xs text-foreground">Daily Shift Summary via Corporate Email</span>
                <input
                  type="checkbox"
                  checked={emailAlerts}
                  onChange={(e) => setEmailAlerts(e.target.checked)}
                  className="h-4 w-4 rounded accent-primary cursor-pointer"
                />
              </label>
            </div>
          </div>

          {/* Section: Security */}
          <div className="p-3 rounded-xl bg-white/5 border border-white/10 flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Enterprise SSO (Okta / Azure AD Connected)</span>
            </div>
            <span className="font-mono text-[10px] text-emerald-400">ACTIVE</span>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/10">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="text-xs py-2 px-4 rounded-xl border-white/10 cursor-pointer"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="glow"
              className="text-xs font-bold py-2 px-5 rounded-xl flex items-center gap-2 cursor-pointer"
            >
              <Save className="w-3.5 h-3.5" />
              Save Profile
            </Button>
          </div>

        </form>

      </GlassCard>
    </div>
  );
}
