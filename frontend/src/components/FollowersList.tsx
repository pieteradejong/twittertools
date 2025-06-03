import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

interface Follower {
  id: string;
  username: string;
  display_name: string;
  avatar_url?: string;
}

async function fetchFollowers() {
  const { data } = await axios.get<Follower[]>(
    'http://localhost:8000/api/followers'
  );
  return data;
}

export function FollowersList({ isActive }: { isActive: boolean }) {
  const { data: followers, isLoading, error, refetch } = useQuery({
    queryKey: ['followers'],
    queryFn: fetchFollowers,
    enabled: isActive,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    refetchInterval: false,
  });

  if (!isActive) return null;

  return (
    <div className="max-w-2xl mx-auto py-8">
      <h1 className="text-2xl font-bold mb-4">Followers</h1>
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
            <p className="text-gray-500">Loading followers...</p>
          </div>
        </div>
      ) : error ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <p className="text-red-600 mb-4">Error loading followers</p>
            <button
              onClick={() => refetch()}
              className="px-4 py-2 rounded-md bg-red-500 hover:bg-red-600 text-white text-sm"
            >
              Try Again
            </button>
          </div>
        </div>
      ) : !followers?.length ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="text-6xl mb-4">🎉</div>
            <p className="text-gray-500 text-lg">No followers found!</p>
            <p className="text-gray-400 text-sm mt-2">No one is following you yet.</p>
          </div>
        </div>
      ) : (
        <div className="bg-white divide-y divide-gray-200 rounded-xl shadow">
          {followers.map((follower) => (
            <div key={follower.id} className="flex items-center gap-4 p-4">
              <img
                src={follower.avatar_url || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png'}
                alt={follower.display_name}
                className="w-12 h-12 rounded-full object-cover"
              />
              <div>
                <div className="font-semibold text-gray-900">{follower.display_name}</div>
                <div className="text-gray-500">@{follower.username}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
} 