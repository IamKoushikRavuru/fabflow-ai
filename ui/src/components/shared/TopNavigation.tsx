import { useState } from 'react';
import { Bell, User, RefreshCw, Radio } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useLiveSync } from '@/context/LiveSyncContext';
import { useNotifications } from '@/context/NotificationContext';
import { useAuth } from '@/context/AuthContext';
import { NotificationsDrawer } from '@/components/notifications/NotificationsDrawer';
import { UserDropdown } from '@/components/auth/UserDropdown';
import { AuthModal } from '@/components/auth/AuthModal';
import { ProfileModal } from '@/components/auth/ProfileModal';

export function TopNavigation() {
  const { isLive, latencyMs, isSyncing, triggerSync, setIsLive } = useLiveSync();
  const { unreadCount } = useNotifications();
  const { currentUser, isAuthenticated } = useAuth();

  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const [isUserOpen, setIsUserOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);

  return (
    <>
      <header className="sticky top-0 z-40 w-full backdrop-blur-xl bg-background/80 border-b border-white/10 h-16 flex items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-3">
          {/* Abstract Logo */}
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center shadow-[0_0_15px_-3px_rgba(56,189,248,0.5)]">
            <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"></path>
              <path d="M12 12v9"></path>
              <path d="m8 17 4 4 4-4"></path>
            </svg>
          </div>
          <div>
            <span className="font-semibold text-lg tracking-wide text-foreground">FabFlow AI</span>
            <span className="hidden md:inline-block ml-2 px-1.5 py-0.5 rounded text-[10px] font-mono uppercase bg-white/5 border border-white/10 text-muted-foreground">
              SMT2020 Enterprise
            </span>
          </div>
        </div>

        {/* Center / Right controls */}
        <div className="flex items-center gap-2 sm:gap-3 relative">
          
          {/* Live Telemetry Beacon */}
          <div 
            onClick={() => setIsLive(!isLive)}
            title={isLive ? "Click to pause real-time sync" : "Click to resume real-time sync"}
            className={`flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-mono cursor-pointer transition-all duration-300 border ${
              isLive 
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20' 
                : 'bg-white/5 border-white/10 text-muted-foreground hover:bg-white/10'
            }`}
          >
            <span className="relative flex h-2 w-2">
              {isLive && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              )}
              <span className={`relative inline-flex rounded-full h-2 w-2 ${isLive ? 'bg-emerald-400' : 'bg-gray-500'}`} />
            </span>
            <span className="font-semibold uppercase tracking-wider text-[11px]">
              {isLive ? `Live (${latencyMs}ms)` : 'Paused'}
            </span>
            <Radio className="w-3 h-3 opacity-60 ml-0.5" />
          </div>

          {/* Manual Sync Trigger */}
          <button
            onClick={() => triggerSync()}
            disabled={isSyncing}
            title="Force Telemetry Sync"
            className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-primary' : ''}`} />
          </button>

          <div className="h-4 w-[1px] bg-white/10 mx-1 hidden sm:block" />

          {/* Notifications Button */}
          <div className="relative">
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => setIsNotifOpen(!isNotifOpen)}
              title="Fab Notifications & Alerts"
              className={`relative h-8 w-8 cursor-pointer ${
                isNotifOpen 
                  ? 'bg-white/10 text-primary' 
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 h-4 w-4 rounded-full bg-rose-500 text-white text-[9px] font-bold flex items-center justify-center shadow-[0_0_8px_rgba(244,63,94,0.8)]">
                  {unreadCount}
                </span>
              )}
            </Button>

            <NotificationsDrawer
              isOpen={isNotifOpen}
              onClose={() => setIsNotifOpen(false)}
            />
          </div>

          {/* User Profile Avatar / Sign In */}
          <div className="relative">
            {isAuthenticated && currentUser ? (
              <button
                onClick={() => setIsUserOpen(!isUserOpen)}
                className={`h-8 px-2 rounded-xl flex items-center gap-2 border transition-all cursor-pointer ${
                  isUserOpen ? 'border-primary/50 bg-white/10' : 'border-white/10 hover:border-white/20 bg-white/5'
                }`}
              >
                <div className={`h-5 w-5 rounded-md flex items-center justify-center font-bold text-[10px] ${currentUser.badgeColor}`}>
                  {currentUser.initials}
                </div>
                <span className="text-xs font-medium text-foreground max-w-[90px] truncate hidden md:inline-block">
                  {currentUser.name.split(' ')[0]}
                </span>
              </button>
            ) : (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsAuthModalOpen(true)}
                title="Sign In"
                className="h-8 w-8 text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <User className="h-4 w-4" />
              </Button>
            )}

            <UserDropdown
              isOpen={isUserOpen}
              onClose={() => setIsUserOpen(false)}
              onOpenProfile={() => setIsProfileModalOpen(true)}
              onOpenAuth={() => setIsAuthModalOpen(true)}
            />
          </div>

        </div>
      </header>

      {/* Auth & Profile Modals */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
      />

      <ProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
      />
    </>
  );
}
