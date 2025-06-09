import type { ReactNode } from 'react';

interface MenuItemProps {
  label: string;
  icon: ReactNode;
  isActive: boolean;
  onClick: () => void;
  disabled?: boolean;
}

export function MenuItem({ label, icon, isActive, onClick, disabled = false }: MenuItemProps) {
  return (
    <button
      className={`w-full px-6 py-3 text-left transition-colors flex items-center gap-4 ${
        disabled 
          ? "text-gray-400 cursor-not-allowed opacity-50" 
          : isActive
            ? "bg-gray-100 text-black border-r-2 border-black cursor-pointer"
            : "text-gray-700 hover:text-black hover:bg-gray-50 cursor-pointer"
      }`}
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
    >
      <span className="flex-shrink-0">{icon}</span>
      <span className="font-medium text-lg">{label}</span>
    </button>
  );
} 