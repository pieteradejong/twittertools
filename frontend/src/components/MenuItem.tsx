import type { ReactNode } from 'react';

interface MenuItemProps {
  label: string;
  icon: ReactNode;
  isActive: boolean;
  onClick: () => void;
}

export function MenuItem({ label, icon, isActive, onClick }: MenuItemProps) {
  return (
    <button
      className={`w-full px-6 py-3 text-left hover:bg-gray-50 transition-colors flex items-center gap-4 cursor-pointer ${
        isActive
          ? "bg-gray-100 text-black border-r-2 border-black"
          : "text-gray-700 hover:text-black"
      }`}
      onClick={onClick}
    >
      <span className="flex-shrink-0">{icon}</span>
      <span className="font-medium text-lg">{label}</span>
    </button>
  );
} 