'use client'

import { Bell, Search, Settings, LogOut, Check, X } from "lucide-react"
import { useRouter } from "next/navigation"
import { SidebarTrigger } from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useAuth } from "@/lib/auth-context"
import { useNotifications } from "@/lib/notification-context"
import {
  useNotificationsQuery,
  useNotificationStats,
  useDeleteNotification
} from "@/lib/react-query"
import { useEffect } from "react"
import { formatDistanceToNow } from "date-fns"

export function DashboardHeader() {
  const { user, logout } = useAuth()
  const router = useRouter()
  const { unreadCount, isConnected, isPolling, setInitialNotifications, markAsRead: contextMarkAsRead, markAllAsRead: contextMarkAllAsRead } = useNotifications()

  // Fetch initial notifications
  const { data: notificationsData, isLoading } = useNotificationsQuery({
    limit: 10,
    unread_only: false
  })

  // Periodically refresh stats to keep the badge in sync even if
  // WebSocket/polling messages are missed
  const { data: statsData } = useNotificationStats()

  const deleteNotificationMutation = useDeleteNotification()

  // Set initial notifications when data loads
  useEffect(() => {
    if (notificationsData) {
      setInitialNotifications(
        notificationsData.notifications || [],
        notificationsData.unread_count || 0
      )
    }
  }, [notificationsData, setInitialNotifications])

  // Sync stats-based unread count into context whenever it refreshes.
  // This ensures the badge stays correct even if a real-time message is missed.
  useEffect(() => {
    if (statsData && typeof statsData.unread_count === 'number') {
      // Only override if we're not connected via WebSocket (to avoid overwriting
      // real-time increments). When polling, stats are the source of truth.
      if (!isConnected) {
        setInitialNotifications(
          notificationsData?.notifications || [],
          statsData.unread_count
        )
      }
    }
  }, [statsData, isConnected, notificationsData, setInitialNotifications])

  const handleNotificationClick = (notification) => {
    if (!notification.is_read) {
      // Context method: optimistic badge update + REST API persist + query invalidation
      contextMarkAsRead(notification.id)
    }
    if (notification.action_url) {
      router.push(notification.action_url)
    }
  }

  const handleMarkAllAsRead = () => {
    // Context method: optimistic badge clear + REST API persist + query invalidation
    contextMarkAllAsRead()
  }

  const handleDeleteNotification = (e, notificationId) => {
    e.stopPropagation()
    deleteNotificationMutation.mutate(notificationId)
  }

  const userInitials = user?.name
    ? user.name.split(' ').map(n => n[0]).join('').toUpperCase()
    : 'U'

  const handleLogout = async () => {
    await logout()
  }

  return (
    <header className="flex h-16 items-center gap-4 border-b bg-background px-6">
      <SidebarTrigger className="-ml-1" />

      <div className="flex-1" />

      {/* Search */}
      <div className="relative flex-1 max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search tasks, goals, users..."
          className="pl-9"
        />
      </div>

      {/* Notifications */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="relative">
            <Bell className="h-4 w-4" />
            {unreadCount > 0 && (
              <Badge
                variant="destructive"
                className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-xs"
              >
                {unreadCount > 99 ? '99+' : unreadCount}
              </Badge>
            )}
            {/* Connection indicator: green = WebSocket, orange = polling */}
            {isConnected && (
              <span className="absolute bottom-0 right-0 h-2 w-2 bg-green-500 rounded-full border-2 border-background" title="Live (WebSocket)" />
            )}
            {!isConnected && isPolling && (
              <span className="absolute bottom-0 right-0 h-2 w-2 bg-orange-400 rounded-full border-2 border-background" title="Polling for updates" />
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-96">
          <div className="flex items-center justify-between px-2 py-1.5">
            <DropdownMenuLabel className="p-0">Notifications</DropdownMenuLabel>
            {unreadCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleMarkAllAsRead}
                className="h-auto py-1 px-2 text-xs"
              >
                <Check className="mr-1 h-3 w-3" />
                Mark all read
              </Button>
            )}
          </div>
          <DropdownMenuSeparator />

          {isLoading ? (
            <div className="p-4 space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex flex-col gap-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-full" />
                </div>
              ))}
            </div>
          ) : notificationsData?.notifications?.length > 0 ? (
            <ScrollArea className="max-h-[400px]">
              {notificationsData.notifications.map((notification) => (
                <DropdownMenuItem
                  key={notification.id}
                  className={`flex flex-col items-start gap-1 p-3 cursor-pointer ${
                    !notification.is_read ? 'bg-blue-50' : ''
                  }`}
                  onClick={() => handleNotificationClick(notification)}
                >
                  <div className="flex items-start justify-between w-full gap-2">
                    <div className="flex-1 space-y-1">
                      <p className={`text-sm ${!notification.is_read ? 'font-semibold' : 'font-medium'}`}>
                        {notification.title}
                      </p>
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {notification.message}
                      </p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        {notification.triggered_by_name && (
                          <span>By {notification.triggered_by_name}</span>
                        )}
                        {notification.created_at && (
                          <span>• {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true })}</span>
                        )}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => handleDeleteNotification(e, notification.id)}
                      className="h-6 w-6 p-0 hover:bg-red-100"
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                </DropdownMenuItem>
              ))}
            </ScrollArea>
          ) : (
            <div className="p-6 text-center">
              <Bell className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No notifications</p>
            </div>
          )}

          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => router.push('/dashboard/notifications')} className="justify-center">
            <Button variant="link" size="sm" className="w-full p-0 h-auto">
              View all notifications
            </Button>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* User menu */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="relative h-8 w-8 rounded-full">
            <Avatar className="h-8 w-8">
              <AvatarImage
                src={user?.profile_image_url ? `${process.env.NEXT_PUBLIC_API_URL}${user.profile_image_url}` : undefined}
                alt={user?.name || 'User'}
              />
              <AvatarFallback>{userInitials}</AvatarFallback>
            </Avatar>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-56" align="end">
          <DropdownMenuLabel className="font-normal">
            <div className="flex flex-col space-y-1">
              <p className="text-sm font-medium leading-none">{user?.name}</p>
              <p className="text-xs leading-none text-muted-foreground">
                {user?.email}
              </p>
              <div className="flex gap-1 mt-1">
                <Badge variant="secondary" className="text-xs">
                  {user?.role_name}
                </Badge>
              </div>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => router.push('/dashboard/settings')} className="cursor-pointer">
            <Settings className="mr-2 h-4 w-4" />
            <span>Settings</span>
          </DropdownMenuItem>
          <DropdownMenuItem>
            <span>Support</span>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={handleLogout} className="text-red-600 cursor-pointer">
            <LogOut className="mr-2 h-4 w-4" />
            <span>Log out</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  )
}