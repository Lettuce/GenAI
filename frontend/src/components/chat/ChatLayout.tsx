import { Outlet } from 'react-router-dom'

import { ThreadSidebar } from '@/components/chat/ThreadSidebar'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { ThreadsProvider } from '@/components/chat/ThreadsProvider'

export function ChatLayout() {
  return (
    <ThreadsProvider>
      <SidebarProvider>
        <ThreadSidebar />
        <SidebarInset className="flex min-h-svh flex-col">
          <header className="flex h-12 shrink-0 items-center border-b px-4 md:hidden">
            <SidebarTrigger />
          </header>
          <Outlet />
        </SidebarInset>
      </SidebarProvider>
    </ThreadsProvider>
  )
}
