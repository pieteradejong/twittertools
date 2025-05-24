import { MantineProvider, AppShell, Tabs, Container, Stack } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TweetList } from './components/TweetList';
import { ReplyList } from './components/ReplyList';
import { AuthStatusComponent } from './components/AuthStatus';
import '@mantine/core/styles.css';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <MantineProvider>
        <AppShell header={{ height: 60 }} padding="md">
          <AppShell.Header style={{ display: 'flex', alignItems: 'center', padding: '0 20px' }}>
            <h1 style={{ margin: 0 }}>Twitter Management Dashboard</h1>
          </AppShell.Header>

          <AppShell.Main>
            <Container size="xl">
              <Stack gap="md">
                <AuthStatusComponent />
                <Tabs defaultValue="tweets">
                  <Tabs.List>
                    <Tabs.Tab value="tweets">Zero Engagement Tweets</Tabs.Tab>
                    <Tabs.Tab value="replies">Zero Engagement Replies</Tabs.Tab>
                  </Tabs.List>

                  <Tabs.Panel value="tweets" pt="md">
                    <TweetList />
                  </Tabs.Panel>

                  <Tabs.Panel value="replies" pt="md">
                    <ReplyList />
                  </Tabs.Panel>
                </Tabs>
              </Stack>
            </Container>
          </AppShell.Main>
        </AppShell>
      </MantineProvider>
    </QueryClientProvider>
  );
}

export default App;
