'use client'

import { SidebarProvider } from "@/components/ui/sidebar"
import { AppSidebar } from "@/components/dashboard/app-sidebar"
import { DashboardHeader } from "@/components/dashboard/dashboard-header"
import { SessionHeartbeat } from "@/components/dashboard/session-heartbeat"
import { AuthGuard } from "@/lib/auth-context"

export default function DashboardLayout({ children }) {
  return (
    <AuthGuard>
      <SessionHeartbeat />
      <SidebarProvider>
        <div className="flex min-h-screen w-full ">
          <AppSidebar />
          <div className="flex-1 flex flex-col">
            <DashboardHeader />
            <main className="flex-1 p-6 bg-background border-[2px] border-border/60">
              {children}
            </main>
          </div>
        </div>
      </SidebarProvider>
    </AuthGuard>
  )
}