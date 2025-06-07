import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

interface User {
  user_id: string;
  user_link: string;
  username: string;
}

interface UserListProps {
  type: 'blocks' | 'mutes';
  isActive: boolean;
}

async function fetchUsers(type: string, page: number = 0) {
  const limit = 20;
  const offset = page * limit;
  const { data } = await axios.get<User[]>(`http://localhost:8000/api/${type}?limit=${limit}&offset=${offset}`);
  return data;
}

export function UserList({ type, isActive }: UserListProps) {
  const [page, setPage] = useState(0);

  const { data: users, isLoading, error } = useQuery({
    queryKey: [type, page],
    queryFn: () => fetchUsers(type, page),
    enabled: isActive,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  const title = type === 'blocks' ? 'Blocked Users' : 'Muted Users';
  const emptyMessage = type === 'blocks' ? 'No blocked users found.' : 'No muted users found.';
  const icon = type === 'blocks' ? '🚫' : '🔇';

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto py-8">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="animate-pulse space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-gray-200 rounded-full"></div>
                <div className="flex-1">
                  <div className="h-4 bg-gray-200 rounded w-1/4 mb-2"></div>
                  <div className="h-3 bg-gray-200 rounded w-1/3"></div>
                </div>
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
            Error loading {type}: {error instanceof Error ? error.message : 'Unknown error'}
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
            <span>{icon}</span>
            {title}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {users?.length || 0} {type === 'blocks' ? 'blocked' : 'muted'} users
          </p>
        </div>

        {/* User List */}
        <div className="divide-y divide-gray-200">
          {users && users.length > 0 ? (
            users.map((user) => (
              <div key={user.user_id} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center">
                      <span className="text-gray-600 font-medium">
                        {user.username.charAt(0).toUpperCase()}
                      </span>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-gray-900">
                        @{user.username}
                      </div>
                      <div className="text-sm text-gray-500">
                        User ID: {user.user_id}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    {user.user_link && (
                      <a
                        href={user.user_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 text-sm"
                      >
                        View Profile
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="px-6 py-8 text-center text-gray-500">
              {emptyMessage}
            </div>
          )}
        </div>

        {/* Pagination */}
        {users && users.length === 20 && (
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