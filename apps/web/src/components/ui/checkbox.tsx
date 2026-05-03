"use client";

import { Check } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export const Checkbox = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => {
  return (
    <span
      className={cn(
        "relative inline-flex h-4 w-4 shrink-0 items-center justify-center",
        className,
      )}
    >
      <input
        ref={ref}
        type="checkbox"
        className="peer absolute inset-0 h-4 w-4 cursor-pointer rounded-sm border border-primary bg-background appearance-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 checked:bg-primary disabled:cursor-not-allowed disabled:opacity-50"
        {...props}
      />
      <Check className="pointer-events-none h-3 w-3 text-primary-foreground opacity-0 peer-checked:opacity-100" />
    </span>
  );
});
Checkbox.displayName = "Checkbox";
