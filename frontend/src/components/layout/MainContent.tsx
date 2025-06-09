import { TabRouter } from "../tabs/TabRegistry";

interface ProfileData {
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
}

interface MainContentProps {
  activeTab: string;
  profile?: ProfileData;
  profileLoading?: boolean;
}

export function MainContent({ activeTab, profile, profileLoading }: MainContentProps) {
  return (
    <main className="w-full bg-gray-50 max-w-4xl">
      <TabRouter activeTab={activeTab} profile={profile} profileLoading={profileLoading} />
    </main>
  );
} 