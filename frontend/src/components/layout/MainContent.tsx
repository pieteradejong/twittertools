import { TabRouter } from "../tabs/TabRegistry";

interface MainContentProps {
  activeTab: string;
}

export function MainContent({ activeTab }: MainContentProps) {
  return (
    <main className="flex-1 overflow-y-auto bg-gray-50">
      <TabRouter activeTab={activeTab} />
    </main>
  );
} 