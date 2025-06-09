import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { ProfileLinkWithOptions } from '../common/ProfileLink';

interface Follower {
  id: string;
  username: string | null;
  display_name: string;
  user_link?: string;
  avatar_url?: string;
  verified?: boolean;
  follower_count?: number;
  following_count?: number;
  tweet_count?: number;
  relationship_created_at?: string;
  needs_profile_data?: boolean;
}

interface FollowersResponse {
  followers: Follower[];
  total_count: number;
  limit: number;
  offset: number;
}

async function fetchFollowers(limit: number = 100, offset: number = 0) {
  const { data } = await axios.get<FollowersResponse>(
    `http://localhost:8000/api/followers?limit=${limit}&offset=${offset}`
  );
  return data;
}

export function FollowersList({ isActive }: { isActive: boolean }) {
  const { data: followersData, isLoading, error, refetch } = useQuery({
    queryKey: ['followers'],
    queryFn: () => fetchFollowers(),
    enabled: isActive,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    refetchInterval: false,
  });

  if (!isActive) return null;

  const followers = followersData?.followers || [];
  const totalCount = followersData?.total_count || 0;

  return (
    <div className="max-w-4xl mx-auto py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Followers</h1>
        {totalCount > 0 && (
          <span className="text-gray-500 text-sm">
            {totalCount} followers
          </span>
        )}
      </div>
      
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
            <div key={follower.id} className="flex items-center gap-4 p-6">
              <img
                src={follower.avatar_url || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png'}
                alt={follower.display_name || `User ${follower.id}`}
                className="w-16 h-16 rounded-full object-cover"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <div className="font-semibold text-gray-900 text-lg">
                    {follower.display_name}
                  </div>
                  {follower.verified && (
                    <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                  )}
                  {follower.needs_profile_data && (
                    <span className="inline-flex items-center px-2 py-1 text-xs font-medium text-orange-700 bg-orange-100 rounded-full">
                      Profile data needed
                    </span>
                  )}
                </div>
                <div className="text-gray-500 mb-2">
                  {follower.username ? `@${follower.username}` : `User ID: ${follower.id}`}
                </div>
                
                {/* Stats */}
                <div className="flex items-center gap-4 text-sm text-gray-600 mb-2">
                  {follower.follower_count !== undefined && follower.follower_count !== null && (
                    <span>{follower.follower_count.toLocaleString()} followers</span>
                  )}
                  {follower.following_count !== undefined && follower.following_count !== null && (
                    <span>{follower.following_count.toLocaleString()} following</span>
                  )}
                  {follower.tweet_count !== undefined && follower.tweet_count !== null && (
                    <span>{follower.tweet_count.toLocaleString()} tweets</span>
                  )}
                </div>
                
                <div className="flex items-center gap-4">
                  <ProfileLinkWithOptions 
                    user={{
                      id: follower.id,
                      username: follower.username,
                      user_link: follower.user_link
                    }}
                    className="text-sm font-medium"
                  />
                  {follower.relationship_created_at && (
                    <span className="text-xs text-gray-400">
                      Following since {new Date(follower.relationship_created_at).toLocaleDateString()}
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