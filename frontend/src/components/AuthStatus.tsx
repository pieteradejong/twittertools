import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

interface AuthStatus {
  is_authenticated: boolean;
  username: string | null;
  error: string | null;
  can_fetch_data: boolean;
  test_tweet_count: number | null;
  auth_steps: string[];
}

async function fetchAuthStatus() {
  const { data } = await axios.get<AuthStatus>('http://localhost:8000/api/test-auth');
  return data;
}

export function AuthStatusComponent() {
  const { data: status, isLoading, error, refetch } = useQuery({
    queryKey: ['auth-status'],
    queryFn: fetchAuthStatus,
    retry: false,
    // Increase stale time to 5 minutes to prevent unnecessary refetches
    staleTime: 5 * 60 * 1000,
    // Only refetch on window focus if we're not rate limited
    refetchOnWindowFocus: false,
    // Remove automatic refetch interval
    refetchInterval: false,
  });

  if (isLoading) {
    return (
      <div className="border rounded-lg p-4 mb-4 bg-white shadow">
        <div className="flex flex-col gap-2">
          <span>Checking authentication status...</span>
          <div className="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-700">
            <div className="bg-blue-600 h-2.5 rounded-full w-full animate-pulse"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-red-400 rounded-lg p-4 mb-4 bg-white shadow">
        <div className="flex flex-col gap-2">
          <span className="text-red-600 font-semibold">Failed to check authentication status</span>
          <span className="text-sm text-gray-500">The backend server might not be running or is unreachable.</span>
          <button onClick={() => refetch()} className="px-3 py-1 rounded bg-gray-100 hover:bg-gray-200 text-sm border border-gray-300 w-fit">Retry</button>
        </div>
      </div>
    );
  }

  if (!status) {
    return null;
  }

  return (
    <div className={`border rounded-lg p-4 mb-4 bg-white shadow ${status.is_authenticated && status.can_fetch_data ? 'border-green-400' : 'border-red-400'}`}>
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="font-semibold">Twitter API Status</span>
          <div className="flex gap-2">
            <span className={`px-2 py-1 rounded text-xs font-semibold ${status.is_authenticated ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>{status.is_authenticated ? 'Authenticated' : 'Not Authenticated'}</span>
            {status.can_fetch_data && (
              <span className="px-2 py-1 rounded text-xs font-semibold bg-green-100 text-green-800">Can Fetch Data</span>
            )}
          </div>
        </div>

        {status.auth_steps.length > 0 && (
          <div className="flex flex-col gap-1 mt-2">
            <span className="text-sm font-semibold">Authentication Steps:</span>
            {status.auth_steps.map((step: string, index: number) => (
              <div key={index} className="flex items-center gap-2">
                <span className="inline-block w-4 h-4 bg-green-200 text-green-700 rounded-full flex items-center justify-center text-xs">✓</span>
                <span className="text-sm">{step}</span>
              </div>
            ))}
          </div>
        )}

        {status.username && (
          <span className="text-sm">Connected as: <span className="font-mono">@{status.username}</span></span>
        )}

        {status.test_tweet_count !== null && (
          <span className="text-sm">Test tweet fetch: {status.test_tweet_count} tweets found</span>
        )}

        {status.error && (
          <span className="text-sm text-red-600">{status.error}</span>
        )}

        <button 
          onClick={() => refetch()} 
          className="px-3 py-1 rounded bg-gray-100 hover:bg-gray-200 text-sm border border-gray-300 w-fit mt-2"
        >
          Refresh Status
        </button>
      </div>
    </div>
  );
} 