import { useState } from "react";
import { Layout } from "./components/layout/Layout";
import { Sidebar } from "./components/layout/Sidebar";
import { MainContent } from "./components/layout/MainContent";
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

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

  return (
    <Layout
      sidebar={
        <Sidebar
          activeTab={activeTab}
          onTabChange={handleTabChange}
          profile={profile}
          profileLoading={profileLoading}
        />
      }
    >
      <MainContent activeTab={activeTab} />
    </Layout>
  );
}
