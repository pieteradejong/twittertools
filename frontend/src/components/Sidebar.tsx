import { MenuItem } from './MenuItem';

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  profile?: {
    username: string;
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
    avatar_url?: string;
    display_name?: string;
    created_at?: string;
    bio?: string;
    website?: string;
    location?: string;
  };
  profileLoading: boolean;
}

const NAV_ITEMS = [
  {
    label: "Zero Engagement Tweets",
    value: "zero-engagement-tweets",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    )
  },
  { 
    label: "Likes", 
    value: "likes", 
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
      </svg>
    )
  },
  { 
    label: "Semantic Likes", 
    value: "semantic-likes", 
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    )
  },
  { 
    label: "Bookmarks", 
    value: "bookmarks", 
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
      </svg>
    )
  },
  { 
    label: "Replies", 
    value: "replies", 
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
      </svg>
    )
  },
  { 
    label: "Lists", 
    value: "lists", 
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
      </svg>
    )
  },

  { 
    label: "Following", 
    value: "following", 
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    )
  },
  { 
    label: "Followers", 
    value: "followers", 
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    )
  },
  { 
    label: "Blocked", 
    value: "blocked", 
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636m12.728 12.728L12 12m6.364 6.364L12 12m0 0L5.636 5.636M12 12l6.364-6.364M12 12l-6.364 6.364" />
      </svg>
    )
  },
  { 
    label: "Muted", 
    value: "muted", 
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
      </svg>
    )
  },
  { 
    label: "Direct Messages", 
    value: "direct-messages", 
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    )
  }
];

export function Sidebar({ activeTab, onTabChange, profile, profileLoading }: SidebarProps) {
  return (
    <nav className="w-80 border-r border-gray-200 bg-white flex flex-col">
      {/* Twitter Logo & Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center gap-3 mb-4">
          {profile && profile.avatar_url ? (
            <img
              src={profile.avatar_url}
              alt={profile.username}
              className="w-8 h-8 rounded-full object-cover border border-gray-200"
            />
          ) : (
            <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                <path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723c-.951.555-2.005.959-3.127 1.184a4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z"/>
              </svg>
            </div>
          )}
          <h1 className="text-xl font-bold text-gray-900">Twitter Tools</h1>
        </div>
        
        {/* Profile Info */}
        {profileLoading ? (
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
            <div className="h-3 bg-gray-200 rounded w-1/2"></div>
          </div>
        ) : profile ? (
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Hi @{profile.username},
            </h2>
            {/* Stats Panel */}
            <div className="mt-3 border border-gray-200 rounded-lg p-3 bg-gray-50">
              <div className="grid grid-cols-2 gap-2 text-xs text-gray-700">
                <div className="font-medium">Tweets</div>
                <div className="text-right">{profile.stats.tweet_count}</div>
                <div className="font-medium">Replies</div>
                <div className="text-right">{profile.stats.reply_count}</div>
                <div className="font-medium">Likes</div>
                <div className="text-right">{profile.stats.like_count}</div>
                <div className="font-medium">Bookmarks</div>
                <div className="text-right">{profile.stats.bookmark_count || 0}</div>
                <div className="font-medium">Following</div>
                <div className="text-right">{profile.stats.following_count || 0}</div>
                <div className="font-medium">Lists</div>
                <div className="text-right">{profile.stats.lists_count || 0}</div>
                <div className="font-medium">Blocked</div>
                <div className="text-right">{profile.stats.blocks_count || 0}</div>
                <div className="font-medium">Muted</div>
                <div className="text-right">{profile.stats.mutes_count || 0}</div>
                <div className="font-medium">Direct Messages</div>
                <div className="text-right">{profile.stats.dm_count || 0}</div>
                <div className="font-medium">Zero Engagement Tweets</div>
                <div className="text-right">{profile.stats.zero_engagement_tweets}</div>
                <div className="font-medium">Zero Engagement Replies</div>
                <div className="text-right">{profile.stats.zero_engagement_replies}</div>
              </div>
            </div>
            {/* Profile Info Panel */}
            <div className="mt-3 border border-gray-200 rounded-lg p-3 bg-gray-50">
              <div className="text-xs text-gray-700 space-y-1">
                <div><span className="font-medium">Display Name:</span> {profile.display_name}</div>
                <div><span className="font-medium">Username:</span> @{profile.username}</div>
                <div><span className="font-medium">Joined:</span> {profile.created_at}</div>
                {profile.bio && <div><span className="font-medium">Bio:</span> {profile.bio}</div>}
                {profile.website && <div><span className="font-medium">Website:</span> <a href={profile.website} className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer">{profile.website}</a></div>}
                {profile.location && <div><span className="font-medium">Location:</span> {profile.location}</div>}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-sm text-gray-500">Loading profile...</div>
        )}
      </div>

      {/* Navigation Items */}
      <div className="flex-1 py-2">
        {NAV_ITEMS.map((item) => (
          <MenuItem
            key={item.value}
            label={item.label}
            icon={item.icon}
            isActive={activeTab === item.value}
            onClick={() => onTabChange(item.value)}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="p-6 border-t border-gray-200 text-xs text-gray-500">
        <div className="mb-1">
          <strong>Archive generated:</strong> May 30, 2025
        </div>
        <div>
          Data from your Twitter archive
        </div>
      </div>
    </nav>
  );
} 