import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { MessageSquarePlusIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import { useThreads } from '@/hooks/useThreads'
import { formatRelativeTime } from '@/lib/format'
import { supabase } from '@/lib/supabase'

export function ThreadSidebar() {
  const navigate = useNavigate()
  const { threadId } = useParams()
  const { threads, isLoading, error, createNewThread } = useThreads()
  const [isCreating, setIsCreating] = useState(false)

  async function handleNewChat() {
    setIsCreating(true)
    try {
      const id = await createNewThread()
      navigate(`/chats/${id}`)
    } finally {
      setIsCreating(false)
    }
  }

  async function handleSignOut() {
    await supabase.auth.signOut()
    navigate('/login', { replace: true })
  }

  return (
    <Sidebar>
      <SidebarHeader className="gap-3 border-b border-sidebar-border p-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-sm font-medium text-sidebar-foreground">Document Copilot</p>
            <p className="text-xs text-sidebar-foreground/70">SEC filing assistant</p>
          </div>
        </div>
        <Button
          className="w-full justify-start gap-2"
          onClick={() => void handleNewChat()}
          disabled={isCreating}
        >
          <MessageSquarePlusIcon className="size-4" />
          {isCreating ? 'Creating…' : 'New chat'}
        </Button>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Conversations</SidebarGroupLabel>
          <SidebarGroupContent>
            {isLoading ? (
              <p className="px-2 py-3 text-sm text-sidebar-foreground/70">Loading…</p>
            ) : null}

            {!isLoading && error ? (
              <p className="px-2 py-3 text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : null}

            {!isLoading && !error && threads.length === 0 ? (
              <p className="px-2 py-3 text-sm text-sidebar-foreground/70">
                No conversations yet.
              </p>
            ) : null}

            <SidebarMenu>
              {threads.map((thread) => (
                <SidebarMenuItem key={thread.id}>
                  <SidebarMenuButton asChild isActive={thread.id === threadId}>
                    <Link to={`/chats/${thread.id}`}>
                      <span className="truncate font-medium">{thread.title}</span>
                      <span className="truncate text-xs text-sidebar-foreground/70">
                        {formatRelativeTime(thread.updatedAt)}
                      </span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border p-4">
        <Button variant="outline" className="w-full" onClick={() => void handleSignOut()}>
          Sign out
        </Button>
      </SidebarFooter>
    </Sidebar>
  )
}
