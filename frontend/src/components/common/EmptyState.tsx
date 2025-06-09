interface EmptyStateProps {
  icon: string;
  title: string;
  description: string;
}

export function EmptyState({ icon, title, description }: EmptyStateProps) {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="text-6xl mb-4">{icon}</div>
        <p className="text-gray-500 text-lg">{title}</p>
        <p className="text-gray-400 text-sm mt-2">{description}</p>
      </div>
    </div>
  );
} 