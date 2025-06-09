import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';

interface TwitterList {
  id: string;
  name: string;
  url: string;
  type: string;
  member_count?: number;
  follower_count?: number;
  description?: string;
  private?: boolean;
}

interface ListsListProps {
  isActive: boolean;
}

async function fetchLists(page: number = 0) {
  const limit = 20;
  const offset = page * limit;
  const { data } = await axios.get<TwitterList[]>(`http://localhost:8000/api/lists?limit=${limit}&offset=${offset}`);
  return data;
}

async function runListEnrichment() {
  const { data } = await axios.post('http://localhost:8000/api/lists/enrichment/run', null, {
    params: { limit: 10, delay: 1.0 }
  });
  return data;
}

async function fetchEnrichmentStats() {
  const { data } = await axios.get('http://localhost:8000/api/lists/enrichment/stats');
  return data;
}

export function ListsList({ isActive }: ListsListProps) {
  const [page, setPage] = useState(0);
  const queryClient = useQueryClient();

  const { data: lists, isLoading, error } = useQuery({
    queryKey: ['lists', page],
    queryFn: () => fetchLists(page),
    enabled: isActive,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  const { data: enrichmentStats } = useQuery({
    queryKey: ['enrichment-stats'],
    queryFn: fetchEnrichmentStats,
    enabled: isActive,
    staleTime: 30 * 1000, // Cache for 30 seconds
  });

  const enrichmentMutation = useMutation({
    mutationFn: runListEnrichment,
    onSuccess: () => {
      // Invalidate and refetch lists and stats after enrichment
      queryClient.invalidateQueries({ queryKey: ['lists'] });
      queryClient.invalidateQueries({ queryKey: ['enrichment-stats'] });
    },
  });

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto py-8">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="animate-pulse space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-gray-200 rounded"></div>
                <div className="flex-1">
                  <div className="h-4 bg-gray-200 rounded w-1/3 mb-2"></div>
                  <div className="h-3 bg-gray-200 rounded w-1/4"></div>
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
            Error loading lists: {error instanceof Error ? error.message : 'Unknown error'}
          </div>
        </div>
      </div>
    );
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'created': return '📝';
      case 'member': return '👥';
      case 'subscribed': return '📋';
      default: return '📄';
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'created': return 'bg-green-100';
      case 'member': return 'bg-blue-100';
      case 'subscribed': return 'bg-purple-100';
      default: return 'bg-gray-100';
    }
  };

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'created': return 'Created';
      case 'member': return 'Member';
      case 'subscribed': return 'Subscribed';
      default: return type;
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-8">
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                <span>📋</span>
                Twitter Lists
              </h1>
              <p className="text-sm text-gray-500 mt-1">
                {lists?.length || 0} lists from your Twitter archive
                {enrichmentStats && (
                  <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                    {enrichmentStats.lists_with_member_counts} with member counts
                  </span>
                )}
              </p>
            </div>
            <button
              onClick={() => enrichmentMutation.mutate()}
              disabled={enrichmentMutation.isPending}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {enrichmentMutation.isPending ? 'Fetching...' : 'Fetch Member Counts'}
            </button>
          </div>
        </div>

        {/* Lists */}
        <div className="divide-y divide-gray-200">
          {lists && lists.length > 0 ? (
            lists.map((list) => (
              <div key={list.id} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className={`w-10 h-10 ${getTypeColor(list.type)} rounded flex items-center justify-center`}>
                      <span className="text-lg">
                        {getTypeIcon(list.type)}
                      </span>
                    </div>
                    <div>
                      <div className={`text-sm font-medium ${list.name ? 'text-gray-900' : 'text-gray-600'}`}>
                        {list.name || `Untitled List`}
                        {list.name && (
                          <span className="ml-2 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">
                            Named
                          </span>
                        )}
                      </div>
                      <div className="text-sm text-gray-500">
                        {getTypeLabel(list.type)}
                        {!list.name && list.id && (
                          <span className="ml-1 text-xs bg-gray-100 px-2 py-0.5 rounded">
                            ID: {list.id.length > 12 ? `...${list.id.slice(-8)}` : list.id}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col items-end space-y-1">
                    {list.url && (
                      <a
                        href={list.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                      >
                        View List
                      </a>
                    )}
                    <div className="text-xs text-gray-500">
                      {list.member_count !== null && list.member_count !== undefined ? (
                        <span className="font-medium">
                          {list.member_count.toLocaleString()} members
                        </span>
                      ) : (
                        <span className="text-gray-400">Member count unavailable</span>
                      )}
                    </div>
                    {list.follower_count !== null && list.follower_count !== undefined && (
                      <div className="text-xs text-gray-400">
                        {list.follower_count.toLocaleString()} followers
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="px-6 py-8 text-center text-gray-500">
              No lists found.
            </div>
          )}
        </div>

        {/* Pagination */}
        {lists && lists.length === 20 && (
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