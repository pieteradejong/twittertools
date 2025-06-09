import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

interface DirectMessage {
  message_id: string;
  conversation_id: string;
  sender_id: string;
  recipient_id: string;
  text: string;
  created_at: string;
  media_url?: string;
}

interface DirectMessageListProps {
  isActive: boolean;
}

async function fetchDirectMessages(page: number = 0) {
  const limit = 20;
  const offset = page * limit;
  const { data } = await axios.get<DirectMessage[]>(`http://localhost:8000/api/direct-messages?limit=${limit}&offset=${offset}`);
  return data;
}

export function DirectMessageList({ isActive }: DirectMessageListProps) {
  const [page, setPage] = useState(0);

  const { data: messages, isLoading, error } = useQuery({
    queryKey: ['direct-messages', page],
    queryFn: () => fetchDirectMessages(page),
    enabled: isActive,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto py-8">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="animate-pulse space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="space-y-2">
                <div className="h-4 bg-gray-200 rounded w-1/4"></div>
                <div className="h-3 bg-gray-200 rounded w-3/4"></div>
                <div className="h-3 bg-gray-200 rounded w-1/2"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto py-8">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="text-center text-red-600">
            Error loading direct messages: {error instanceof Error ? error.message : 'Unknown error'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto py-8">
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <span>💬</span>
            Direct Messages
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {messages?.length || 0} messages
          </p>
        </div>

        {/* Message List */}
        <div className="divide-y divide-gray-200">
          {messages && messages.length > 0 ? (
            messages.map((message) => (
              <div key={message.message_id} className="px-6 py-4 hover:bg-gray-50">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-500">
                      From: {message.sender_id} → To: {message.recipient_id}
                    </div>
                    <div className="text-sm text-gray-500">
                      {new Date(message.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="text-gray-900">
                    {message.text || <em className="text-gray-500">No text content</em>}
                  </div>
                  {message.media_url && (
                    <div className="mt-2">
                      <a
                        href={message.media_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 text-sm"
                      >
                        📎 View Media
                      </a>
                    </div>
                  )}
                  <div className="text-xs text-gray-400">
                    Conversation: {message.conversation_id}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="px-6 py-8 text-center text-gray-500">
              No direct messages found.
            </div>
          )}
        </div>

        {/* Pagination */}
        {messages && messages.length === 20 && (
          <div className="px-6 py-4 border-t border-gray-200 flex justify-between items-center">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-sm text-gray-500">
              Page {page + 1}
            </span>
            <button
              onClick={() => setPage(page + 1)}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
} 