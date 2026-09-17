'use client'

import * as React from "react"
import { useState, useEffect } from "react"
import Image from "next/image"
import Link from "next/link"
import { useRouter, usePathname } from "next/navigation"
import {
  Building2,
  Users,
  Target,
  CheckSquare,
  Settings,
  BarChart3,
  Shield,
  LogOut,
  Home,
  Calendar,
  FileText,
  Star,
  TrendingUp,
  Moon,
  Sun,
} from "lucide-react"

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
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { useAuth, usePermission, PermissionGuard } from "@/lib/auth-context"

// Navigation items with permissions
const navigationItems = [
  {
    title: "Dashboard",
    url: "/dashboard",
    icon: Home,
    permission: null, // Available to all authenticated users
  },
  {
    title: "Initiatives",
    url: "/dashboard/initiatives",
    icon: CheckSquare,
    permission: null,
  },
  {
    title: "Goals",
    url: "/dashboard/goals",
    icon: Target,
    permission: null,
  },
  {
    title: "Calendar",
    url: "/dashboard/calendar",
    icon: Calendar,
    permission: null,
  },
  {
    title: "Reviews",
    url: "/dashboard/reviews",
    icon: Star,
    permission: null,
  },
]

const managementItems = [
  {
    title: "Organization",
    url: "/dashboard/organization",
    icon: Building2,
    permission: "organization_create",
  },
  {
    title: "Users",
    url: "/dashboard/users",
    icon: Users,
    permission: "user_view_all",
  },
  {
    title: "Roles",
    url: "/dashboard/roles",
    icon: Shield,
    permission: "role_create",
  },
  {
    title: "Goals Management",
    url: "/dashboard/goals-management",
    icon: Target,
    permission: "goal_create_yearly",
  },
  {
    title: "Review Management",
    url: "/dashboard/review-management",
    icon: Star,
    permission: "review_create_cycle",
  },
  {
    title: "Performance Management",
    url: "/dashboard/performance",
    icon: TrendingUp,
    permission: "performance_view_all",
  },
]

const reportsItems = [
  {
    // Personal analytics (My Activity) is available to everyone; the page
    // self-gates the org-wide Overview tab by permission.
    title: "Analytics",
    url: "/dashboard/analytics",
    icon: BarChart3,
    permission: null,
  },
  {
    title: "Reports",
    url: "/dashboard/reports",
    icon: FileText,
    permission: "reports_generate",
  },
]

const settingsItems = [
  {
    title: "Settings",
    url: "/dashboard/settings",
    icon: Settings,
    permission: null,
  },
]

function NavGroup({ title, items }) {
  const pathname = usePathname()

  const visibleItems = items.filter(item => {
    if (!item.permission) return true
    return usePermission(item.permission)
  })

  if (visibleItems.length === 0) return null

  return (
    <SidebarGroup>
      <SidebarGroupLabel className="text-sidebar-foreground/40 text-[10px] uppercase tracking-widest font-semibold px-3">{title}</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {visibleItems.map((item) => {
            // Check if current path matches the item URL
            // For /dashboard, only match exact path to prevent highlighting on all routes
            // For other items, match if pathname exactly equals item.url OR starts with item.url followed by '/'
            // This prevents /dashboard/goals-management from matching /dashboard/goals
            const isActive = item.url === '/dashboard'
              ? pathname === '/dashboard'
              : pathname === item.url || pathname.startsWith(item.url + '/')

            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  asChild
                  className={
                    isActive
                      ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium hover:bg-sidebar-accent"
                      : "text-sidebar-foreground/55 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
                  }
                >
                  <Link href={item.url}>
                    <item.icon className="h-4 w-4" />
                    <span>{item.title}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

export function AppSidebar() {
  const { user, logout } = useAuth()
  const router = useRouter()
  const [isDark, setIsDark] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('theme')
    if (saved === 'dark') {
      document.documentElement.classList.add('dark')
      setIsDark(true)
    }
  }, [])

  const toggleTheme = () => {
    const next = !isDark
    setIsDark(next)
    if (next) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }

  const handleLogout = async () => {
    try {
      await logout()
      // The logout function already handles routing to /login, so we don't need to do it again here
    } catch (error) {
      console.error('Logout error:', error)
      // Force navigation even if logout fails
      router.push('/login')
    }
  }

  const userInitials = user?.name
    ? user.name.split(' ').map(n => n[0]).join('').toUpperCase()
    : 'U'

  return (
    <Sidebar variant="inset" collapsible="icon">
      <SidebarHeader className="border-b border-sidebar-border px-5 py-4 group-data-[collapsible=icon]:px-2 group-data-[collapsible=icon]:py-3">
        <div className="flex items-center gap-3">
          <div className="h-7 w-7 rounded-md overflow-hidden flex-shrink-0">
            <Image
              src={isDark ? "/icon_dark.png" : "/icon_light.png"}
              alt="Nigcomsat Logo"
              width={28}
              height={28}
              className="w-full h-full object-contain"
            />
          </div>
          <div className="flex flex-col group-data-[collapsible=icon]:hidden">
            <span className="text-sm font-semibold text-sidebar-foreground">Nigcomsat PMS</span>
            <span className="text-xs text-sidebar-foreground/50">Performance Management</span>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent className="px-2">
        <NavGroup title="" items={navigationItems} />

        <PermissionGuard permission="user_view_all">
          <Separator className="my-1 bg-sidebar-border" />
          <NavGroup title="Management" items={managementItems} />
        </PermissionGuard>

        <Separator className="my-1 bg-sidebar-border" />
        <NavGroup title="Reports" items={reportsItems} />

        <Separator className="my-1 bg-sidebar-border" />
        <NavGroup title="Settings" items={settingsItems} />
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border px-4 py-3 group-data-[collapsible=icon]:px-2 space-y-3">
        <div className="flex items-center gap-3 group-data-[collapsible=icon]:justify-center">
          <Avatar className="h-8 w-8 flex-shrink-0">
            <AvatarFallback className="text-xs bg-sidebar-accent text-sidebar-accent-foreground font-medium">
              {userInitials}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0 group-data-[collapsible=icon]:hidden">
            <p className="text-sm font-medium text-sidebar-foreground truncate">{user?.name}</p>
            <p className="text-xs text-sidebar-foreground/50 truncate">
              {user?.role_name}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1 group-data-[collapsible=icon]:flex-col">
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleTheme}
            className="flex-1 justify-start gap-2 text-sidebar-foreground/55 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 group-data-[collapsible=icon]:w-full group-data-[collapsible=icon]:justify-center"
            title={isDark ? "Switch to light mode" : "Switch to dark mode"}
          >
            {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            <span className="group-data-[collapsible=icon]:hidden text-xs">
              {isDark ? "Light mode" : "Dark mode"}
            </span>
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            className="flex-1 justify-start gap-2 text-sidebar-foreground/55 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 group-data-[collapsible=icon]:w-full group-data-[collapsible=icon]:justify-center"
          >
            <LogOut className="h-4 w-4" />
            <span className="group-data-[collapsible=icon]:hidden text-xs">Sign out</span>
          </Button>
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}