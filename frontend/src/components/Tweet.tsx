export interface TweetProps {
  text: string;
  created_at: string;
  metrics?: {
    like_count?: number;
    retweet_count?: number;
    reply_count?: number;
    quote_count?: number;
  };
  user?: {
    avatar_url?: string;
    display_name?: string;
    username?: string;
    verified?: boolean;
  };
  media?: { url: string; type: string }[];
  profileUsername?: string;
  id?: string;
}

export function Tweet({ text, created_at, metrics, user, media, profileUsername, id }: TweetProps) {
  const displayName = user?.display_name || 'You';
  const username = user?.username ? user.username : (profileUsername || 'you');
  const isVerified = user?.verified ?? true;
  const avatarUrl = user?.avatar_url || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png';
  
  // Format timestamp as 'x years, y months, z days ago'
  const formatTimestamp = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    let years = now.getFullYear() - date.getFullYear();
    let months = now.getMonth() - date.getMonth();
    let days = now.getDate() - date.getDate();

    if (days < 0) {
      months -= 1;
      // Get days in previous month
      const prevMonth = new Date(now.getFullYear(), now.getMonth(), 0);
      days += prevMonth.getDate();
    }
    if (months < 0) {
      years -= 1;
      months += 12;
    }

    const parts = [];
    if (years > 0) parts.push(`${years} year${years > 1 ? 's' : ''}`);
    if (months > 0) parts.push(`${months} month${months > 1 ? 's' : ''}`);
    if (days > 0 && years === 0) parts.push(`${days} day${days > 1 ? 's' : ''}`);
    if (parts.length === 0) return 'today';
    return parts.join(', ') + ' ago';
  };

  const formatCount = (count: number) => {
    if (count >= 1000000) {
      return `${(count / 1000000).toFixed(1)}M`;
    } else if (count >= 1000) {
      return `${(count / 1000).toFixed(1)}K`;
    }
    return count.toString();
  };

  return (
    <div className="border-b border-gray-200 p-3 hover:bg-gray-50 transition-colors">
      <div className="flex gap-3">
        {/* Profile Picture */}
        <img 
          src={avatarUrl} 
          alt={displayName} 
          className="rounded-full w-10 h-10 object-cover flex-shrink-0" 
        />
        
        {/* Tweet Content */}
        <div className="flex-1 min-w-0">
          {/* Header: Name, Username, Verified Badge, Timestamp */}
          <div className="flex items-center gap-1 mb-1 flex-wrap">
            <span className="font-bold text-gray-900 truncate">{displayName}</span>
            {isVerified && (
              <svg className="w-5 h-5 text-blue-500 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
                <path d="M22.25 12c0-1.43-.88-2.67-2.19-3.34.46-1.39.2-2.9-.81-3.91s-2.52-1.27-3.91-.81c-.66-1.31-1.91-2.19-3.34-2.19s-2.67.88-3.33 2.19c-1.4-.46-2.91-.2-3.92.81s-1.26 2.52-.8 3.91c-1.31.67-2.2 1.91-2.2 3.34s.89 2.67 2.2 3.34c-.46 1.39-.21 2.9.8 3.91s2.52 1.27 3.91.81c.67 1.31 1.91 2.19 3.34 2.19s2.68-.88 3.34-2.19c1.39.46 2.9.2 3.91-.81s1.27-2.52.81-3.91c1.31-.67 2.19-1.91 2.19-3.34zm-11.71 4.2L6.8 12.46l1.41-1.42 2.26 2.26 4.8-5.23 1.47 1.36-6.2 6.77z"/>
              </svg>
            )}
            <span className="text-gray-500 truncate">@{username}</span>
            <span className="text-gray-500">·</span>
            <span className="text-gray-500 flex-shrink-0">{formatTimestamp(created_at)}</span>
          </div>
          
          {/* Tweet Text */}
          <div className="text-gray-900 mb-3 whitespace-pre-wrap break-words">
            {text}
          </div>
          
          {/* Media */}
          {media && media.length > 0 && (
            <div className="mb-3 rounded-2xl overflow-hidden border border-gray-200">
              {media.map((m, i) => (
                <img key={i} src={m.url} alt={m.type} className="w-full" />
              ))}
            </div>
          )}
          
          {/* Engagement Metrics and Actions */}
          <div className="flex items-center justify-between max-w-md mt-3">
            {/* Reply */}
            <div className="flex items-center gap-1 text-gray-500 hover:text-blue-500 cursor-pointer group">
              <div className="p-2 rounded-full group-hover:bg-blue-50 transition-colors">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <span className="text-sm">{metrics?.reply_count !== undefined && metrics?.reply_count !== null ? formatCount(metrics.reply_count) : '0'}</span>
            </div>
            
            {/* Retweet */}
            <div className="flex items-center gap-1 text-gray-500 hover:text-green-500 cursor-pointer group">
              <div className="p-2 rounded-full group-hover:bg-green-50 transition-colors">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </div>
              <span className="text-sm">{metrics?.retweet_count !== undefined && metrics?.retweet_count !== null ? formatCount(metrics.retweet_count) : '0'}</span>
            </div>
            
            {/* Like */}
            <div className="flex items-center gap-1 text-gray-500 hover:text-red-500 cursor-pointer group">
              <div className="p-2 rounded-full group-hover:bg-red-50 transition-colors">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                </svg>
              </div>
              <span className="text-sm">{metrics?.like_count !== undefined && metrics?.like_count !== null ? formatCount(metrics.like_count) : '0'}</span>
            </div>
            
            {/* Views */}
            <div className="flex items-center gap-1 text-gray-500 hover:text-blue-500 cursor-pointer group">
              <div className="p-2 rounded-full group-hover:bg-blue-50 transition-colors">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <span className="text-sm">5.3K</span>
            </div>
            
            {/* Bookmark and Share */}
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-full hover:bg-blue-50 text-gray-500 hover:text-blue-500 cursor-pointer transition-colors">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                </svg>
              </div>
              <div className="p-2 rounded-full hover:bg-blue-50 text-gray-500 hover:text-blue-500 cursor-pointer transition-colors">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.367 2.684 3 3 0 00-5.367-2.684z" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>
      {/* Management Panel */}
      <div className="mt-4 flex justify-start">
        {/* Only show if username and tweet id are available */}
        <a
          href={`https://twitter.com/${profileUsername}/status/${id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block px-4 py-2 bg-blue-100 text-blue-700 rounded-full font-semibold shadow hover:bg-blue-200 transition-colors text-sm"
        >
          View on Twitter
        </a>
      </div>
    </div>
  );
} 