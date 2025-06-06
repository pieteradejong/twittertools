import { useState } from "react";
import { TweetList } from "./components/TweetList";
import { ReplyList } from "./components/ReplyList";
import { Sidebar } from "./components/Sidebar";
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { FollowingList } from "./components/FollowingList";
import { FollowersList } from "./components/FollowersList";

interface ProfileData {
  user_id: string;
  username: string;
  display_name: string;
  created_at: string;
  stats: {
    tweet_count: number;
    like_count: number;
    reply_count: number;
    zero_engagement_tweets: number;
    zero_engagement_replies: number;
  };
}

async function fetchProfile() {
  const { data } = await axios.get<ProfileData>('http://localhost:8000/api/profile');
  return data;
}

export default function App() {
  const [activeTab, setActiveTab] = useState("zero-engagement-tweets");

  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: fetchProfile,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  if (profileLoading) {
    return <div>Loading profile...</div>;
  }
  if (!profile) {
    return <div>Error: Profile not loaded</div>;
  }

  // Map tab values to display names
  const getTabDisplayName = (tab: string) => {
    const tabNames: Record<string, string> = {
      tweets: "Tweets",
      likes: "Likes", 
      bookmarks: "Bookmarks",
      replies: "Replies",
      lists: "Lists",
      analytics: "Analytics",
      following: "Following",
      blocked: "Blocked",
      followers: "Followers"
    };
    return tabNames[tab] || tab;
  };

  return (
    <div className="flex h-screen bg-white">
      {/* Left Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        profile={profile}
        profileLoading={profileLoading}
      />

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto bg-gray-50">
        {activeTab === "tweets" && <TweetList isActive={true} profile={profile} />}
        {activeTab === "likes" && <TweetList isActive={true} type="likes" profile={profile} />}
        {activeTab === "bookmarks" && <TweetList isActive={true} type="bookmarks" profile={profile} />}
        {activeTab === "replies" && <ReplyList isActive={true} />}
        {activeTab === "zero-engagement-tweets" && (
          <div className="max-w-2xl mx-auto py-8">
            <TweetList isActive={activeTab === "zero-engagement-tweets"} profile={profile} />
          </div>
        )}
        {activeTab === "following" && <FollowingList isActive={true} />}
        {activeTab === "followers" && <FollowersList isActive={true} />}
        {/* Placeholder for other tabs */}
        {!["tweets", "likes", "bookmarks", "replies", "zero-engagement-tweets", "following", "followers"].includes(activeTab) && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">{getTabDisplayName(activeTab)}</h2>
              <p className="text-gray-500">This feature is coming soon!</p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
