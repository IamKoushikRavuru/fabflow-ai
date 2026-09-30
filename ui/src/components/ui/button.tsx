import * as React from "react"
import { cn } from "@/lib/utils"
import { motion, HTMLMotionProps } from "framer-motion"

export interface ButtonProps extends HTMLMotionProps<"button"> {
  variant?: 'default' | 'outline' | 'ghost' | 'glow';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    return (
      <motion.button
        ref={ref}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className={cn(
          "inline-flex items-center justify-center whitespace-nowrap rounded-2xl text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
          {
            "bg-primary text-primary-foreground hover:bg-primary/90": variant === "default",
            "border border-white/10 bg-white/5 hover:bg-white/10 text-foreground backdrop-blur-sm": variant === "outline",
            "hover:bg-accent hover:text-accent-foreground": variant === "ghost",
            "bg-transparent border border-primary/50 text-primary hover:bg-primary/10 hover:border-primary hover:shadow-[0_0_15px_-3px_rgba(56,189,248,0.4)]": variant === "glow",
            "h-10 px-4 py-2": size === "default",
            "h-9 rounded-xl px-3": size === "sm",
            "h-12 rounded-3xl px-8 text-base": size === "lg",
            "h-10 w-10": size === "icon",
          },
          className
        )}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button }
