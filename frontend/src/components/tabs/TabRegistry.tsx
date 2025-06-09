import { SimpleTweetList } from "../tweets/SimpleTweetList";
import { SemanticTweetList } from "../tweets/SemanticTweetList";
import { ReplyList } from "../communication/ReplyList";
import { FollowingList } from "../users/FollowingList";
import { FollowersList } from "../users/FollowersList";
import { UserList } from "../users/UserList";
import { DirectMessageList } from "../communication/DirectMessageList";
import { ListsList } from "../users/ListsList";
import { ProfileEnrichment } from "../profile/ProfileEnrichment";
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

interface TabRouterProps {
  activeTab: string;
}

export function TabRouter({ activeTab }: TabRouterProps) {
  const tabConfig = TAB_COMPONENTS[activeTab];
  
  if (!tabConfig) {
    return <PlaceholderTab tabName={activeTab} />;
  }
  
  const { component: Component, props = {} } = tabConfig;
  return <Component {...props} />;
} 