'use client'

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Activity,
  AlertCircle,
  BarChart3,
  CalendarCheck,
  Clock,
  Lock,
  LogIn,
  Target,
  Timer,
  TrendingUp,
  UserCheck,
  UserPlus,
  Users,
} from "lucide-react"
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  Cell,
  PieChart,
  Pie,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts"
import { useAuth, usePermission } from "@/lib/auth-context"
import { useOrgAnalytics, useMyAnalytics } from "@/lib/react-query"

const CHART_COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)']

function KpiCard({ title, value, subtitle, icon: Icon }) {
  return (
    <Card className="border-gray-200">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-gray-700">{title}</CardTitle>
        <div className="h-8 w-8 rounded-full bg-blue-50 flex items-center justify-center">
          <Icon className="h-4 w-4 text-blue-600" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold text-black">{value}</div>
        {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
      </CardContent>
    </Card>
  )
}

const tooltipStyle = {
  backgroundColor: 'var(--popover, white)',
  border: '1px solid var(--border, #e5e7eb)',
  borderRadius: '8px',
  fontSize: '12px',
}

function ChartCard({ title, description, children, className = "" }) {
  return (
    <Card className={`border-gray-200 ${className}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
        {description && <CardDescription className="text-xs">{description}</CardDescription>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

const dayShort = (d) => new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

// ---------------------------------------------------------------- Overview tab

function OverviewTab({ days }) {
  const { data, isLoading, error } = useOrgAnalytics(days, { refetchInterval: 300_000 })

  if (isLoading) {
    return <p className="text-sm text-gray-500 py-10 text-center">Loading analytics…</p>
  }
  if (error) {
    return (
      <p className="text-sm text-red-600 py-10 text-center">
        {error?.detail || 'Failed to load analytics.'}
      </p>
    )
  }
  if (!data) return null

  const timeseries = (data.timeseries || []).map(p => ({ ...p, day: dayShort(p.date) }))
  const topUsers = data.top_active_users || []
  const notifications = (data.notifications_by_type || []).slice(0, 8)

  const weekly = (data.weekly_engagement || []).map(w => ({
    ...w,
    week: new Date(w.week_start).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
  }))
  const latestWeek = weekly[weekly.length - 1]
  const sessionStats = data.session_stats

  return (
    <div className="space-y-4">
      {/* KPI row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <KpiCard title="Total Users" value={data.total_users} subtitle={`${data.active_users} active`} icon={Users} />
        <KpiCard title="Active (30d)" value={data.active_users_30d} subtitle={`${data.active_users_7d} in last 7 days`} icon={UserCheck} />
        <KpiCard title="Logins Today" value={data.logins_today} subtitle={`${data.logins_30d} in last 30 days`} icon={LogIn} />
        <KpiCard title="Failed Logins (30d)" value={data.failed_logins_30d} subtitle="Check for spikes" icon={AlertCircle} />
        <KpiCard title="New Users (30d)" value={data.new_users_30d} subtitle="Onboarded this month" icon={UserPlus} />
      </div>

      {/* Engagement KPI row */}
      <div className="grid gap-4 md:grid-cols-3">
        <KpiCard
          title="Weekly Active Staff"
          value={latestWeek ? latestWeek.active_users : 0}
          subtitle={latestWeek ? `${latestWeek.logins} logins this week` : 'No sessions yet'}
          icon={CalendarCheck}
        />
        <KpiCard
          title="Avg Session Duration"
          value={sessionStats ? `${sessionStats.avg_session_minutes} min` : '—'}
          subtitle={sessionStats ? `${sessionStats.sessions_count} sessions (last ${days}d)` : 'Awaiting heartbeat data'}
          icon={Clock}
        />
        <KpiCard
          title="Total Time on Platform"
          value={sessionStats ? `${sessionStats.total_session_hours}h` : '—'}
          subtitle={`Last ${days} days`}
          icon={Timer}
        />
      </div>

      {/* Weekly engagement */}
      {weekly.length > 0 && (
        <ChartCard title="Weekly Engagement" description="Distinct staff and logins per week">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={weekly}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e5e7eb)" />
              <XAxis dataKey="week" fontSize={11} tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="logins" name="Logins" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="active_users" name="Active staff" fill="var(--chart-2)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      {/* Logins timeseries */}
      <ChartCard title="Daily Logins" description={`Successful vs failed logins over the last ${days} days`}>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={timeseries}>
            <defs>
              <linearGradient id="loginFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--chart-1)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--chart-1)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e5e7eb)" />
            <XAxis dataKey="day" fontSize={11} tickLine={false} axisLine={false} interval="preserveStartEnd" />
            <YAxis fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Area type="monotone" dataKey="logins" name="Logins" stroke="var(--chart-1)" fill="url(#loginFill)" strokeWidth={2} />
            <Area type="monotone" dataKey="failed_logins" name="Failed" stroke="var(--chart-5)" fill="none" strokeWidth={1.5} />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* Active users + users by org level */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Active Users per Day" description="Distinct users with recorded activity">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={timeseries}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e5e7eb)" />
              <XAxis dataKey="day" fontSize={11} tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="active_users" name="Active users" fill="var(--chart-2)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Users by Grade Level" description="Civil service grade distribution">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data.users_by_level} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e5e7eb)" />
              <XAxis type="number" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
              <YAxis type="category" dataKey="name" fontSize={11} tickLine={false} axisLine={false} width={70} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="count" name="Users" fill="var(--chart-3)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Roles donut + notifications + organizations */}
      <div className="grid gap-4 lg:grid-cols-3">
        <ChartCard title="Users by Role">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={data.users_by_role} dataKey="count" nameKey="name" innerRadius={45} outerRadius={80} paddingAngle={2}>
                {(data.users_by_role || []).map((entry, i) => (
                  <Cell key={entry.name} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Notifications (30d)" description="Volume by type">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={notifications} layout="vertical">
              <XAxis type="number" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
              <YAxis type="category" dataKey="name" fontSize={10} tickLine={false} axisLine={false} width={130} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="count" name="Sent" fill="var(--chart-4)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Users by Organization">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={(data.users_by_organization || []).slice(0, 8)}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e5e7eb)" />
              <XAxis dataKey="name" fontSize={9} tickLine={false} axisLine={false} interval={0} angle={-30} textAnchor="end" height={60} />
              <YAxis fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="count" name="Users" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Top active users */}
      <Card className="border-gray-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Most Active Users (30d)</CardTitle>
          <CardDescription className="text-xs">Ranked by recorded activity events</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">#</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Organization</TableHead>
                <TableHead>Role</TableHead>
                <TableHead className="text-right">Activity</TableHead>
                <TableHead className="text-right">Last Login</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {topUsers.map((u, i) => (
                <TableRow key={u.user_id}>
                  <TableCell className="text-gray-500">{i + 1}</TableCell>
                  <TableCell className="font-medium">
                    <div>{u.name}</div>
                    <div className="text-xs text-gray-500">{u.email}</div>
                  </TableCell>
                  <TableCell className="text-sm">{u.organization_name || '—'}</TableCell>
                  <TableCell className="text-sm">{u.role_name || '—'}</TableCell>
                  <TableCell className="text-right">
                    <Badge className="bg-blue-50 text-blue-700">{u.activity_count}</Badge>
                  </TableCell>
                  <TableCell className="text-right text-sm text-gray-500">
                    {u.last_login ? new Date(u.last_login).toLocaleDateString() : '—'}
                  </TableCell>
                </TableRow>
              ))}
              {topUsers.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-sm text-gray-500 py-6">
                    No activity recorded yet
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

// ---------------------------------------------------------------- My activity tab

function MyActivityTab({ days }) {
  const { data, isLoading, error } = useMyAnalytics(days, { refetchInterval: 300_000 })

  if (isLoading) {
    return <p className="text-sm text-gray-500 py-10 text-center">Loading your activity…</p>
  }
  if (error) {
    return (
      <p className="text-sm text-red-600 py-10 text-center">
        {error?.detail || 'Failed to load your analytics.'}
      </p>
    )
  }
  if (!data) return null

  const timeseries = (data.logins_timeseries || []).map(p => ({ ...p, day: dayShort(p.date) }))
  const latest = data.latest_performance

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <KpiCard title="Total Logins" value={data.total_logins} subtitle="All time" icon={LogIn} />
        <KpiCard title="My Goals" value={data.goals?.total ?? 0} subtitle={`${data.goals?.achieved ?? 0} achieved`} icon={Target} />
        <KpiCard title="My Initiatives" value={data.initiatives?.total ?? 0} subtitle={`${data.initiatives?.completed ?? 0} completed`} icon={TrendingUp} />
        <KpiCard title="Avg Goal Progress" value={`${data.goals?.avg_progress ?? 0}%`} icon={Activity} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="My Logins" description={`Your login activity over the last ${days} days`}>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={timeseries}>
              <defs>
                <linearGradient id="myLoginFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--chart-2)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--chart-2)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e5e7eb)" />
              <XAxis dataKey="day" fontSize={11} tickLine={false} axisLine={false} interval="preserveStartEnd" />
              <YAxis fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="logins" name="Logins" stroke="var(--chart-2)" fill="url(#myLoginFill)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="My Goals by Status">
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={data.goals?.by_status || []} dataKey="count" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2}>
                {(data.goals?.by_status || []).map((entry, i) => (
                  <Cell key={entry.name} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="My Initiatives by Status">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.initiatives?.by_status || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border, #e5e7eb)" />
              <XAxis dataKey="name" fontSize={10} tickLine={false} axisLine={false} />
              <YAxis fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="count" name="Initiatives" fill="var(--chart-3)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Latest Performance" description={latest ? `Period: ${latest.period}` : undefined}>
          {latest ? (
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Overall Rating</span>
                <Badge className="bg-green-50 text-green-700">{latest.overall_rating}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Goal Achievement Rate</span>
                <span className="font-medium">{latest.goal_achievement_rate ?? '—'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Task Completion Rate</span>
                <span className="font-medium">{latest.task_completion_rate ?? '—'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Peer Feedback Score</span>
                <span className="font-medium">{latest.peer_feedback_score ?? '—'}</span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500 py-6 text-center">No performance record yet</p>
          )}
        </ChartCard>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- Page

export default function AnalyticsPage() {
  const { user } = useAuth()
  const [days, setDays] = useState('30')
  const daysNum = parseInt(days, 10)

  const hasReportsPermission = usePermission('reports_generate')
  const hasAuditPermission = usePermission('audit_access')
  const canViewOrg = hasReportsPermission || hasAuditPermission || user?.scope === 'global'

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BarChart3 className="h-6 w-6" />
            Analytics
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Usage and performance insight across the organization
          </p>
        </div>
        <Select value={days} onValueChange={setDays}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Date range" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">Last 7 days</SelectItem>
            <SelectItem value="30">Last 30 days</SelectItem>
            <SelectItem value="90">Last 90 days</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Tabs defaultValue={canViewOrg ? 'overview' : 'my-activity'}>
        {canViewOrg && (
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="my-activity">My Activity</TabsTrigger>
          </TabsList>
        )}

        {canViewOrg && (
          <TabsContent value="overview">
            <OverviewTab days={daysNum} />
          </TabsContent>
        )}

        <TabsContent value="my-activity">
          <MyActivityTab days={daysNum} />
        </TabsContent>
      </Tabs>

      {!canViewOrg && (
        <Card className="border-gray-200">
          <CardContent className="flex items-center gap-3 py-4">
            <Lock className="h-4 w-4 text-gray-400" />
            <p className="text-xs text-gray-500">
              Organization-wide analytics requires the &quot;reports_generate&quot; permission. Talk to your administrator if you need access.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}