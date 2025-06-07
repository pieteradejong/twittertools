import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

interface Following {
  id: string;
  username: string;
  display_name: string;
  user_link?: string;
  avatar_url?: string;
  verified?: boolean;
  follower_count?: number;
  following_count?: number;
  tweet_count?: number;
  relationship_created_at?: string;
}

interface FollowingResponse {
  following: Following[];
  total_count: number;
  limit: number;
  offset: number;
}

async function fetchFollowing(limit: number = 100, offset: number = 0) {
  const { data } = await axios.get<FollowingResponse>(
    `http://localhost:8000/api/following?limit=${limit}&offset=${offset}`
  );
  return data;
}

export function FollowingList({ isActive }: { isActive: boolean }) {
  const { data: followingData, isLoading, error, refetch } = useQuery({
    queryKey: ['following'],
    queryFn: () => fetchFollowing(),
    enabled: isActive,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    refetchInterval: false,
  });

  if (!isActive) return null;

  const following = followingData?.following || [];
  const totalCount = followingData?.total_count || 0;

  return (
    <div className="max-w-4xl mx-auto py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Following</h1>
        {totalCount > 0 && (
          <span className="text-gray-500 text-sm">
            {totalCount} accounts
          </span>
        )}
      </div>
      
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
            <p className="text-gray-500">Loading following...</p>
          </div>
        </div>
      ) : error ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <p className="text-red-600 mb-4">Error loading following</p>
            <button
              onClick={() => refetch()}
              className="px-4 py-2 rounded-md bg-red-500 hover:bg-red-600 text-white text-sm"
            >
              Try Again
            </button>
          </div>
        </div>
      ) : !following?.length ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="text-6xl mb-4">🎉</div>
            <p className="text-gray-500 text-lg">You're not following anyone!</p>
            <p className="text-gray-400 text-sm mt-2">Start following people to see them here.</p>
          </div>
        </div>
      ) : (
        <div className="bg-white divide-y divide-gray-200 rounded-xl shadow">
          {following.map((user) => (
            <div key={user.id} className="flex items-center gap-4 p-6">
              <img
                src={user.avatar_url || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png'}
                alt={user.display_name || `User ${user.id}`}
                className="w-16 h-16 rounded-full object-cover"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <div className="font-semibold text-gray-900 text-lg">
                    {user.display_name || `User ${user.id.slice(-8)}`}
                  </div>
                  {user.verified && (
                    <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                  )}
                </div>
                <div className="text-gray-500 mb-2">
                  {user.username ? `@${user.username}` : `ID: ${user.id}`}
                </div>
                
                {/* Stats */}
                <div className="flex items-center gap-4 text-sm text-gray-600 mb-2">
                  {user.follower_count !== undefined && user.follower_count !== null && (
                    <span>{user.follower_count.toLocaleString()} followers</span>
                  )}
                  {user.following_count !== undefined && user.following_count !== null && (
                    <span>{user.following_count.toLocaleString()} following</span>
                  )}
                  {user.tweet_count !== undefined && user.tweet_count !== null && (
                    <span>{user.tweet_count.toLocaleString()} tweets</span>
                  )}
                </div>
                
                <div className="flex items-center gap-4">
                  <a 
                    href={user.user_link || `https://twitter.com/intent/user?user_id=${user.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 text-sm font-medium hover:underline"
                  >
                    View Profile
                  </a>
                  {user.relationship_created_at && (
                    <span className="text-xs text-gray-400">
                      Following since {new Date(user.relationship_created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
} 