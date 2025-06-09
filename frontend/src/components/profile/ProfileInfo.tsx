interface ProfileInfoProps {
  profile?: {
    username: string;
    display_name?: string;
    created_at?: string;
    bio?: string;
    website?: string;
    location?: string;
    avatar_url?: string;
    verified?: boolean;
    stats: {
      tweet_count: number;
      like_count: number;
      reply_count: number;
      bookmark_count: number;
      blocks_count: number;
      mutes_count: number;
      dm_count: number;
      lists_count: number;
      following_count: number;
      zero_engagement_tweets: number;
      zero_engagement_replies: number;
    };
  };
  profileLoading: boolean;
  isActive: boolean;
}

export function ProfileInfo({ profile, profileLoading, isActive }: ProfileInfoProps) {
  if (!isActive) return null;

  if (profileLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-6">
          <div className="flex items-center space-x-4">
            <div className="w-20 h-20 bg-gray-200 rounded-full"></div>
            <div className="space-y-2">
              <div className="h-6 bg-gray-200 rounded w-48"></div>
              <div className="h-4 bg-gray-200 rounded w-32"></div>
            </div>
          </div>
          <div className="space-y-3">
            <div className="h-4 bg-gray-200 rounded w-full"></div>
            <div className="h-4 bg-gray-200 rounded w-3/4"></div>
            <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          </div>
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="p-8 text-center">
        <div className="text-gray-500">No profile information available</div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        {/* Header */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-start space-x-6">
            {/* Avatar */}
            <div className="flex-shrink-0">
              {profile.avatar_url ? (
                <img
                  src={profile.avatar_url}
                  alt={profile.username}
                  className="w-20 h-20 rounded-full object-cover border-2 border-gray-200"
                />
              ) : (
                <div className="w-20 h-20 bg-blue-500 rounded-full flex items-center justify-center">
                  <svg className="w-10 h-10 text-white" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                </div>
              )}
            </div>

            {/* Basic Info */}
            <div className="flex-1">
              <div className="flex items-center space-x-2">
                <h1 className="text-2xl font-bold text-gray-900">
                  {profile.display_name || profile.username}
                </h1>
                {profile.verified && (
                  <svg className="w-6 h-6 text-blue-500" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                )}
              </div>
              <p className="text-gray-600 text-lg">@{profile.username}</p>
              {profile.bio && (
                <p className="mt-3 text-gray-800 leading-relaxed">{profile.bio}</p>
              )}
              
              {/* Additional Details */}
              <div className="mt-4 flex flex-wrap gap-4 text-sm text-gray-600">
                {profile.location && (
                  <div className="flex items-center space-x-1">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <span>{profile.location}</span>
                  </div>
                )}
                {profile.website && (
                  <div className="flex items-center space-x-1">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                    <a 
                      href={profile.website} 
                      className="text-blue-600 hover:underline" 
                      target="_blank" 
                      rel="noopener noreferrer"
                    >
                      {profile.website}
                    </a>
                  </div>
                )}
                {profile.created_at && (
                  <div className="flex items-center space-x-1">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <span>Joined {profile.created_at}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Account Statistics</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            <div className="bg-blue-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-blue-600">{profile.stats.tweet_count}</div>
              <div className="text-sm text-gray-600">Tweets</div>
            </div>
            <div className="bg-red-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-red-600">{profile.stats.like_count}</div>
              <div className="text-sm text-gray-600">Likes</div>
            </div>
            <div className="bg-green-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-green-600">{profile.stats.reply_count}</div>
              <div className="text-sm text-gray-600">Replies</div>
            </div>
            <div className="bg-purple-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-purple-600">{profile.stats.bookmark_count || 0}</div>
              <div className="text-sm text-gray-600">Bookmarks</div>
            </div>
            <div className="bg-indigo-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-indigo-600">{profile.stats.following_count || 0}</div>
              <div className="text-sm text-gray-600">Following</div>
            </div>
            <div className="bg-yellow-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-yellow-600">{profile.stats.lists_count || 0}</div>
              <div className="text-sm text-gray-600">Lists</div>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-gray-600">{profile.stats.blocks_count || 0}</div>
              <div className="text-sm text-gray-600">Blocked</div>
            </div>
            <div className="bg-orange-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-orange-600">{profile.stats.mutes_count || 0}</div>
              <div className="text-sm text-gray-600">Muted</div>
            </div>
            <div className="bg-pink-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-pink-600">{profile.stats.dm_count || 0}</div>
              <div className="text-sm text-gray-600">Direct Messages</div>
            </div>
            <div className="bg-teal-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-teal-600">{profile.stats.zero_engagement_tweets}</div>
              <div className="text-sm text-gray-600">Zero Engagement Tweets</div>
            </div>
            <div className="bg-cyan-50 p-4 rounded-lg text-center">
              <div className="text-2xl font-bold text-cyan-600">{profile.stats.zero_engagement_replies}</div>
              <div className="text-sm text-gray-600">Zero Engagement Replies</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 