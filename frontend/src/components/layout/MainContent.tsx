import { TabRouter } from "../tabs/TabRegistry";

interface MainContentProps {
  activeTab: string;
}

export function MainContent({ activeTab }: MainContentProps) {
  return (
    <main className="w-full overflow-y-auto bg-gray-50 max-w-4xl">
      <TabRouter activeTab={activeTab} />
    </main>
  );
} 