import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { ProfileLinkWithOptions } from '../common/ProfileLink';
import { LoadingState, EmptyState, ErrorState } from '../common';

interface ListMember {
  id: string;
  username: string | null;
  display_name: string;
  description?: string;
  profile_image_url?: string;
  verified?: boolean;
  protected?: boolean;
  follower_count?: number;
  following_count?: number;
  tweet_count?: number;
  created_at?: string;
  location?: string;
  url?: string;
  fetched_at?: string;
  needs_profile_data?: boolean;
}

interface ListMembersResponse {
  list_id: string;
  list_name: string;
  members: ListMember[];
  total_count: number;
  limit: number;
  offset: number;
}

async function fetchListMembers(listId: string, limit: number = 100, offset: number = 0) {
  const { data } = await axios.get<ListMembersResponse>(
    `http://localhost:8000/api/lists/${listId}/members?limit=${limit}&offset=${offset}`
  );
  return data;
}

interface ListMembersListProps {
  listId: string;
  isActive: boolean;
}

export function ListMembersList({ listId, isActive }: ListMembersListProps) {
  const { data: membersData, isLoading, error, refetch } = useQuery({
    queryKey: ['list-members', listId],
    queryFn: () => fetchListMembers(listId),
    enabled: isActive && !!listId,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    refetchInterval: false,
  });

  if (!isActive) return null;

  if (isLoading) {
    return <LoadingState message="Loading list members..." />;
  }

  if (error) {
    return (
      <ErrorState 
        message="Failed to load list members" 
        onRetry={() => refetch()}
      />
    );
  }

  const members = membersData?.members || [];
  const totalCount = membersData?.total_count || 0;
  const listName = membersData?.list_name || 'Unknown List';

  if (members.length === 0) {
    return (
      <EmptyState 
        icon="👥"
        title="No members found"
        description="This list doesn't have any members yet, or the data hasn't been fetched."
      />
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{listName}</h1>
          <p className="text-gray-600 text-sm">List Members</p>
        </div>
        {totalCount > 0 && (
          <span className="text-gray-500 text-sm">
            {totalCount} members
          </span>
        )}
      </div>
      
      <div className="bg-white divide-y divide-gray-200 rounded-xl shadow">
        {members.map((member) => (
          <div key={member.id} className="flex items-center gap-4 p-6">
            <img
              src={member.profile_image_url || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png'}
              alt={member.display_name || `User ${member.id}`}
              className="w-16 h-16 rounded-full object-cover"
            />
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <div className="font-semibold text-gray-900 text-lg">
                  {member.display_name}
                </div>
                {member.verified && (
                  <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                )}
                {member.protected && (
                  <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                  </svg>
                )}
                {member.needs_profile_data && (
                  <span className="inline-flex items-center px-2 py-1 text-xs font-medium text-orange-700 bg-orange-100 rounded-full">
                    Profile data needed
                  </span>
                )}
              </div>
              
              <div className="text-gray-500 mb-2">
                {member.username ? `@${member.username}` : `User ID: ${member.id}`}
              </div>
              
              {/* Bio/Description */}
              {member.description && (
                <div className="text-gray-700 text-sm mb-2 line-clamp-2">
                  {member.description}
                </div>
              )}
              
              {/* Location */}
              {member.location && (
                <div className="text-gray-500 text-sm mb-2 flex items-center gap-1">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                  </svg>
                  {member.location}
                </div>
              )}
              
              {/* Stats */}
              <div className="flex items-center gap-4 text-sm text-gray-600 mb-2">
                {member.follower_count !== undefined && member.follower_count !== null && (
                  <span>{member.follower_count.toLocaleString()} followers</span>
                )}
                {member.following_count !== undefined && member.following_count !== null && (
                  <span>{member.following_count.toLocaleString()} following</span>
                )}
                {member.tweet_count !== undefined && member.tweet_count !== null && (
                  <span>{member.tweet_count.toLocaleString()} tweets</span>
                )}
              </div>
              
              <div className="flex items-center gap-4">
                <ProfileLinkWithOptions 
                  user={{
                    id: member.id,
                    username: member.username,
                    user_link: member.url
                  }}
                  className="text-sm font-medium"
                />
                {member.fetched_at && (
                  <span className="text-xs text-gray-400">
                    Fetched {new Date(member.fetched_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {/* Pagination could be added here if needed */}
      {totalCount > members.length && (
        <div className="mt-6 text-center">
          <p className="text-gray-500 text-sm">
            Showing {members.length} of {totalCount} members
          </p>
        </div>
      )}
    </div>
  );
} 