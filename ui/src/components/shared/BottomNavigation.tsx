import { NavLink } from 'react-router-dom';
import { Home, Compass, BarChart2, FileText, Settings, Activity } from 'lucide-react';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';

const NAV_ITEMS = [
  { path: '/dashboard', label: 'Home', icon: Home },
  { path: '/explore', label: 'Explore', icon: Compass },
  { path: '/simulate', label: 'Simulate', icon: Activity },
  { path: '/analytics', label: 'Analytics', icon: BarChart2 },
  { path: '/reports', label: 'Reports', icon: FileText },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export function BottomNavigation() {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-background/80 backdrop-blur-xl border-t border-white/10 pb-safe">
      <nav className="flex items-center justify-around h-16 px-4">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              cn(
                "relative flex flex-col items-center justify-center w-full h-full text-xs font-medium transition-colors",
                isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"
              )
            }
          >
            {({ isActive }) => (
              <>
                <item.icon className={cn("w-5 h-5 mb-1 transition-transform", isActive && "scale-110")} />
                <span>{item.label}</span>
                {isActive && (
                  <motion.div
                    layoutId="bottomNavIndicator"
                    className="absolute -top-[1px] w-8 h-[2px] bg-primary shadow-[0_0_10px_rgba(56,189,248,0.8)]"
                    initial={false}
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
