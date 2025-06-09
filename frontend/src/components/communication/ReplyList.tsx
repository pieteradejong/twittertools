import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { Tweet } from '../tweets/Tweet';

interface ReplyData {
  id: string;
  text: string;
  created_at: string;
  metrics?: {
    like_count?: number;
    retweet_count?: number;
    reply_count?: number;
    quote_count?: number;
  };
  author?: {
    id?: string;
    username?: string;
    display_name?: string;
    avatar_url?: string;
    verified?: boolean;
  };
  in_reply_to: string;
}

async function fetchReplies() {
  const { data } = await axios.get<ReplyData[]>('http://localhost:8000/api/replies/zero-engagement');
  return data;
}

interface ReplyListProps {
  isActive: boolean;
}

export function ReplyList({ isActive }: ReplyListProps) {
  const { data: replies, isLoading, error, refetch } = useQuery({
    queryKey: ['replies'],
    queryFn: fetchReplies,
    // Only fetch when the tab is active
    enabled: isActive,
    // Cache for 5 minutes
    staleTime: 5 * 60 * 1000,
    // Don't refetch automatically
    refetchOnWindowFocus: false,
    refetchInterval: false,
  });

  if (!isActive) return null;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-4 sticky top-0 z-10">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Zero Engagement Replies</h1>
            <p className="text-sm text-gray-600 mt-1">
              {replies ? `${replies.length} replies with no engagement` : 'Loading...'}
            </p>
          </div>
          <button 
            className="px-4 py-2 rounded-md bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium transition-colors" 
            onClick={() => refetch()}
            disabled={isLoading}
          >
            {isLoading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
              <p className="text-gray-500">Loading replies...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <p className="text-red-600 mb-4">Error loading replies</p>
              <button 
                onClick={() => refetch()}
                className="px-4 py-2 rounded-md bg-red-500 hover:bg-red-600 text-white text-sm"
              >
                Try Again
              </button>
            </div>
          </div>
        ) : !replies?.length ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="text-6xl mb-4">🎉</div>
              <p className="text-gray-500 text-lg">No zero engagement replies found!</p>
              <p className="text-gray-400 text-sm mt-2">All your replies have engagement.</p>
            </div>
          </div>
        ) : (
          <div className="bg-white">
            {replies.map((reply) => (
              <div key={reply.id} className="border-b border-gray-200">
                <Tweet
                  id={reply.id}
                  text={reply.text}
                  created_at={reply.created_at}
                  metrics={reply.metrics}
                  author={reply.author}
                />
                {/* Reply context */}
                <div className="px-4 pb-3 text-xs text-gray-500 bg-gray-50 border-b border-gray-200">
                  <span className="inline-flex items-center gap-1">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M7.707 3.293a1 1 0 010 1.414L5.414 7H11a7 7 0 717 7v2a1 1 0 11-2 0v-2a5 5 0 00-5-5H5.414l2.293 2.293a1 1 0 11-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    Replying to: {reply.in_reply_to}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
} 