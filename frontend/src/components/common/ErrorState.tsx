interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({ message = "Error loading data", onRetry }: ErrorStateProps) {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <p className="text-red-600 mb-4">{message}</p>
        {onRetry && (
          <button 
            onClick={onRetry}
            className="px-4 py-2 rounded-md bg-red-500 hover:bg-red-600 text-white text-sm"
          >
            Try Again
          </button>
        )}
      </div>
    </div>
  );
} 