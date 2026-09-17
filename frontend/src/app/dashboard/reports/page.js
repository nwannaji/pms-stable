'use client'

import { useState, useMemo, useEffect } from 'react'
import { toast } from 'sonner'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
import { SearchableSelect } from "@/components/ui/searchable-select"
import {
  Download,
  FileSpreadsheet,
  FileText,
  Loader2,
} from "lucide-react"
import { usePermission } from "@/lib/auth-context"
import { useReportTypes, useReportPreview, useOrganizations } from "@/lib/react-query"
import { reports } from "@/lib/api"

const cellText = (value) => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const TIMESTAMP_COLUMN_RE = /created|updated|login|logout|timestamp|exported/i
const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/

// Timestamps arrive as ISO strings (e.g. 2026-01-20T05:22:12.336830-08:00);
// render them as a readable local date + H:M:S am/pm time.
const formatCell = (value, column) => {
  const text = cellText(value)
  if (!text || !TIMESTAMP_COLUMN_RE.test(column || '')) return text
  const parsed = Date.parse(text)
  if (Number.isNaN(parsed)) return text
  const d = new Date(parsed)
  if (DATE_ONLY_RE.test(text)) {
    return d.toLocaleDateString()
  }
  const datePart = d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
  const timePart = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true })
  return `${datePart}, ${timePart}`
}

const PREVIEW_PAGE_SIZE = 15
// Enough to cover the whole staff list in preview; the export always
// includes every row regardless of this limit.
const PREVIEW_FETCH_LIMIT = 500

export default function ReportsPage() {
  const canGenerate = usePermission('reports_generate')

  const { data: reportTypes = [], isLoading: typesLoading } = useReportTypes()
  const { data: orgData } = useOrganizations({ per_page: 100 })

  const [selectedType, setSelectedType] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [orgId, setOrgId] = useState('')
  const [downloading, setDownloading] = useState(null)
  const [page, setPage] = useState(1)

  const previewParams = useMemo(() => ({
    type: selectedType || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    organization_id: orgId || undefined,
    limit: PREVIEW_FETCH_LIMIT,
  }), [selectedType, dateFrom, dateTo, orgId])

  // New filters mean new data — back to the first page
  useEffect(() => {
    setPage(1)
  }, [selectedType, dateFrom, dateTo, orgId])

  const { data: preview, isFetching: previewLoading, error: previewError } =
    useReportPreview(canGenerate ? previewParams : null)

  const orgOptions = useMemo(() => {
    const list = Array.isArray(orgData) ? orgData : (orgData?.organizations || [])
    return list.map(o => ({ value: o.id, label: o.name }))
  }, [orgData])

  const handleExport = async (format) => {
    if (!selectedType) {
      toast.error('Select a report type first')
      return
    }
    setDownloading(format)
    try {
      const filename = await reports.export({ ...previewParams, format })
      toast.success(`Downloaded ${filename}`)
    } catch (err) {
      toast.error(err?.message || 'Export failed')
    } finally {
      setDownloading(null)
    }
  }

  if (!canGenerate) {
    return (
      <div className="space-y-6 p-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <FileText className="h-6 w-6" />
          Reports
        </h1>
        <Card className="border-gray-200">
          <CardContent className="flex items-center gap-3 py-4">
            <FileSpreadsheet className="h-4 w-4 text-gray-400" />
            <p className="text-xs text-gray-500">
              Generating reports requires the &quot;reports_generate&quot; permission. Talk to your administrator if you need access.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const sections = preview?.sections || []
  const firstSection = sections[0]
  const allRows = firstSection?.rows || []
  const totalPages = Math.max(1, Math.ceil(allRows.length / PREVIEW_PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const displayRows = allRows.slice(
    (currentPage - 1) * PREVIEW_PAGE_SIZE,
    currentPage * PREVIEW_PAGE_SIZE,
  )

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <FileText className="h-6 w-6" />
          Reports
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Generate, preview and export actionable reports as Excel or JSON
        </p>
      </div>

      {/* Report type cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {typesLoading && (
          <p className="text-sm text-gray-500 col-span-full">Loading report types…</p>
        )}
        {(reportTypes || []).map((t) => (
          <Card
            key={t.id}
            className={`border-gray-200 cursor-pointer transition-shadow hover:shadow-md ${
              selectedType === t.id ? 'ring-2 ring-blue-500' : ''
            }`}
            onClick={() => setSelectedType(t.id)}
          >
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <FileSpreadsheet className="h-4 w-4 text-blue-600" />
                {t.name}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-gray-500">{t.description}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <Card className="border-gray-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1">
            <Label className="text-xs text-gray-500">Report type</Label>
            <Select value={selectedType} onValueChange={setSelectedType}>
              <SelectTrigger>
                <SelectValue placeholder="Select report type" />
              </SelectTrigger>
              <SelectContent>
                {(reportTypes || []).map(t => (
                  <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-gray-500">From</Label>
            <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-gray-500">To</Label>
            <Input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-gray-500">Organization</Label>
            <SearchableSelect
              value={orgId}
              onValueChange={setOrgId}
              placeholder="All organizations"
              searchPlaceholder="Search organizations…"
              options={orgOptions}
            />
          </div>
        </CardContent>
      </Card>

      {/* Preview + export */}
      <Card className="border-gray-200">
        <CardHeader className="pb-2">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <CardTitle className="text-base">Preview</CardTitle>
              <CardDescription className="text-xs">
                {preview
                  ? `${firstSection?.title || 'Report'} — showing ${allRows.length === 0 ? 0 : (currentPage - 1) * PREVIEW_PAGE_SIZE + 1}–${(currentPage - 1) * PREVIEW_PAGE_SIZE + displayRows.length} of ${preview.total_rows} total rows`
                  : 'Select a report type to preview'}
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={() => handleExport('xlsx')}
                disabled={!selectedType || downloading !== null || previewLoading}
              >
                {downloading === 'xlsx'
                  ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  : <Download className="h-4 w-4 mr-2" />}
                Excel
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleExport('json')}
                disabled={!selectedType || downloading !== null || previewLoading}
              >
                {downloading === 'json'
                  ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  : <Download className="h-4 w-4 mr-2" />}
                JSON
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {previewError && (
            <p className="text-sm text-red-600 py-4">
              {previewError?.detail || 'Failed to load preview.'}
            </p>
          )}

          {previewLoading && (
            <p className="text-sm text-gray-500 py-6 text-center">Loading preview…</p>
          )}

          {!previewLoading && !preview && !previewError && (
            <p className="text-sm text-gray-500 py-6 text-center">
              Choose a report type above to see a preview
            </p>
          )}

          {firstSection && (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">#</TableHead>
                    {firstSection.columns.map(col => (
                      <TableHead key={col} className="whitespace-nowrap">{col}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {displayRows.map((row, i) => (
                    <TableRow key={i}>
                      <TableCell className="text-gray-400">
                        {(currentPage - 1) * PREVIEW_PAGE_SIZE + i + 1}
                      </TableCell>
                      {row.map((cell, j) => (
                        <TableCell key={j} className="text-sm whitespace-nowrap max-w-[280px] truncate">
                          {formatCell(cell, firstSection.columns[j])}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                  {allRows.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={firstSection.columns.length + 1} className="text-center text-sm text-gray-500 py-6">
                        No rows match the current filters
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
              {totalPages > 1 && (
                <div className="flex items-center justify-between gap-2 mt-3">
                  <p className="text-xs text-gray-500">
                    Page {currentPage} of {totalPages}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={currentPage <= 1}
                    >
                      Previous
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                      disabled={currentPage >= totalPages}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
              {preview.total_rows > allRows.length && (
                <p className="text-xs text-gray-500 mt-2">
                  Preview limited to {allRows.length} rows — the full {preview.total_rows} rows are included in the download.
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}