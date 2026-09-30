import { Outlet, useLocation } from 'react-router-dom';
import { TopNavigation } from '@/components/shared/TopNavigation';
import { BottomNavigation } from '@/components/shared/BottomNavigation';
import { motion, AnimatePresence } from 'framer-motion';

export function MainLayout() {
  const location = useLocation();
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col relative pb-20">
      <TopNavigation />
      
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 relative z-10">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>

      <BottomNavigation />

      {/* Ambient background glow effects */}
      <div className="fixed top-0 left-1/4 w-[500px] h-[500px] bg-primary/10 rounded-full blur-[120px] pointer-events-none -z-10" />
      <div className="fixed bottom-0 right-1/4 w-[400px] h-[400px] bg-purple-500/10 rounded-full blur-[100px] pointer-events-none -z-10" />
    </div>
  );
}
