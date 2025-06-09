import { useState } from "react";
import { TweetList } from "./components/TweetList";
import { ReplyList } from "./components/ReplyList";
import { Sidebar } from "./components/Sidebar";
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { FollowingList } from "./components/FollowingList";
import { FollowersList } from "./components/FollowersList";
import { UserList } from "./components/UserList";
import { DirectMessageList } from "./components/DirectMessageList";
import { ListsList } from "./components/ListsList";
import { SemanticLikesFilter } from "./components/SemanticLikesFilter";
import { ProfileEnrichment } from "./components/ProfileEnrichment";

interface ProfileData {
  user_id: string;
  username: string;
  display_name: string;
  created_at: string;
  stats: {
    tweet_count: number;
    like_count: number;
    bookmark_count: number;
    reply_count: number;
    blocks_count: number;
    mutes_count: number;
    dm_count: number;
    lists_count: number;
    following_count: number;
    zero_engagement_tweets: number;
    zero_engagement_replies: number;
  };
}

async function fetchProfile() {
  const { data } = await axios.get<ProfileData>('http://localhost:8000/api/profile');
  return data;
}

export default function App() {
  const [activeTab, setActiveTab] = useState(() => {
    // Load the last selected tab from localStorage, default to "zero-engagement-tweets"
    return localStorage.getItem('twittertools-active-tab') || "zero-engagement-tweets";
  });

  // Handle tab change and persist to localStorage
  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    localStorage.setItem('twittertools-active-tab', tab);
  };

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
      following: "Following",
      blocked: "Blocked",
      muted: "Muted",
      "direct-messages": "Direct Messages",
      followers: "Followers"
    };
    return tabNames[tab] || tab;
  };

  return (
    <div className="flex h-screen bg-white">
      {/* Left Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={handleTabChange}
        profile={profile}
        profileLoading={profileLoading}
      />

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto bg-gray-50">
        {activeTab === "tweets" && (
          <div className="max-w-2xl mx-auto py-8">
            <TweetList isActive={true} />
          </div>
        )}
        {activeTab === "likes" && (
          <div className="max-w-2xl mx-auto py-8">
            <TweetList isActive={true} type="likes" />
          </div>
        )}
        {activeTab === "semantic-likes" && (
          <div className="max-w-2xl mx-auto py-8">
            <SemanticLikesFilter isActive={true} />
          </div>
        )}
        {activeTab === "bookmarks" && (
          <div className="max-w-2xl mx-auto py-8">
            <TweetList isActive={true} type="bookmarks" />
          </div>
        )}
        {activeTab === "replies" && (
          <div className="max-w-2xl mx-auto py-8">
            <ReplyList isActive={true} />
          </div>
        )}
        {activeTab === "following" && <FollowingList isActive={true} />}
        {activeTab === "followers" && <FollowersList isActive={true} />}
        {activeTab === "profile-enrichment" && <ProfileEnrichment />}
        {activeTab === "blocked" && <UserList type="blocks" isActive={true} />}
        {activeTab === "muted" && <UserList type="mutes" isActive={true} />}
        {activeTab === "direct-messages" && <DirectMessageList isActive={true} />}
        {activeTab === "lists" && <ListsList isActive={true} />}
        {activeTab === "zero-engagement-tweets" && (
          <div className="max-w-2xl mx-auto py-8">
            <TweetList isActive={activeTab === "zero-engagement-tweets"} />
          </div>
        )}
        {/* Placeholder for other tabs */}
        {!["tweets", "likes", "semantic-likes", "bookmarks", "replies", "zero-engagement-tweets", "following", "followers", "profile-enrichment", "blocked", "muted", "direct-messages", "lists"].includes(activeTab) && (
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
