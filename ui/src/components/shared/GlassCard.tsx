import React from 'react';
import { cn } from '@/lib/utils';
import { motion, HTMLMotionProps } from 'framer-motion';

interface GlassCardProps extends HTMLMotionProps<"div"> {
  children: React.ReactNode;
  active?: boolean;
}

export function GlassCard({ children, className, active = false, ...props }: GlassCardProps) {
  return (
    <motion.div
      className={cn(
        'relative rounded-3xl overflow-hidden transition-all duration-300',
        active ? 'glass-panel-active' : 'glass-panel',
        className
      )}
      {...props}
    >
      {children}
    </motion.div>
  );
}
