import { SimpleTweetList } from "../tweets/SimpleTweetList";
import { SemanticTweetList } from "../tweets/SemanticTweetList";
import { TopicAnalysisView } from "../tweets/TopicAnalysisView";
import { ReplyList } from "../communication/ReplyList";
import { FollowingList } from "../users/FollowingList";
import { FollowersList } from "../users/FollowersList";
import { UserList } from "../users/UserList";
import { DirectMessageList } from "../communication/DirectMessageList";
import { ListsList } from "../users/ListsList";
import { ProfileEnrichment, ProfileInfo } from "../profile";
import type { ComponentType } from "react";

interface TabConfig {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  component: ComponentType<any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  props?: any;
}

const TAB_COMPONENTS: Record<string, TabConfig> = {
  'tweets': {
    component: SimpleTweetList,
    props: { isActive: true }
  },
  'likes': {
    component: SimpleTweetList,
    props: { isActive: true, type: 'likes' }
  },
  'semantic-likes': {
    component: SemanticTweetList,
    props: { isActive: true }
  },
  'topic-tweets': {
    component: TopicAnalysisView,
    props: { isActive: true, dataSource: 'tweets', title: 'Tweet Topic Analysis', showCustomTopics: true }
  },
  'topic-likes': {
    component: TopicAnalysisView,
    props: { isActive: true, dataSource: 'likes', title: 'Likes Topic Analysis', showCustomTopics: true }
  },
  'topic-replies': {
    component: TopicAnalysisView,
    props: { isActive: true, dataSource: 'replies', title: 'Replies Topic Analysis' }
  },
  'bookmarks': {
    component: SimpleTweetList,
    props: { isActive: true, type: 'bookmarks' }
  },
  'replies': {
    component: ReplyList,
    props: { isActive: true }
  },
  'following': {
    component: FollowingList,
    props: { isActive: true }
  },
  'followers': {
    component: FollowersList,
    props: { isActive: true }
  },
  'profile-info': {
    component: ProfileInfo,
    props: { isActive: true }
  },
  'profile-enrichment': {
    component: ProfileEnrichment,
    props: {}
  },
  'blocked': {
    component: UserList,
    props: { type: 'blocks', isActive: true }
  },
  'muted': {
    component: UserList,
    props: { type: 'mutes', isActive: true }
  },
  'direct-messages': {
    component: DirectMessageList,
    props: { isActive: true }
  },
  'lists': {
    component: ListsList,
    props: { isActive: true }
  },
  'zero-engagement-tweets': {
    component: SimpleTweetList,
    props: { isActive: true }
  }
};

// Map tab values to display names
const TAB_DISPLAY_NAMES: Record<string, string> = {
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

interface PlaceholderTabProps {
  tabName: string;
}

function PlaceholderTab({ tabName }: PlaceholderTabProps) {
  const displayName = TAB_DISPLAY_NAMES[tabName] || tabName;
  
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">{displayName}</h2>
        <p className="text-gray-500">This feature is coming soon!</p>
      </div>
    </div>
  );
}

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

interface TabRouterProps {
  activeTab: string;
  profile?: ProfileData;
  profileLoading?: boolean;
}

export function TabRouter({ activeTab, profile, profileLoading }: TabRouterProps) {
  const tabConfig = TAB_COMPONENTS[activeTab];
  
  if (!tabConfig) {
    return <PlaceholderTab tabName={activeTab} />;
  }
  
  const { component: Component, props = {} } = tabConfig;
  
  // Pass profile data to components that need it
  const componentProps = {
    ...props,
    ...(activeTab === 'profile-info' && { profile, profileLoading })
  };
  
  return <Component {...componentProps} />;
} 