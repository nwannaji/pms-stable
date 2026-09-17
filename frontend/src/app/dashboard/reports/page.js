'use client'

import { useState, useMemo } from 'react'
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

export default function ReportsPage() {
  const canGenerate = usePermission('reports_generate')

  const { data: reportTypes = [], isLoading: typesLoading } = useReportTypes()
  const { data: orgData } = useOrganizations({ per_page: 100 })

  const [selectedType, setSelectedType] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [orgId, setOrgId] = useState('')
  const [downloading, setDownloading] = useState(null)

  const previewParams = useMemo(() => ({
    type: selectedType || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    organization_id: orgId || undefined,
    limit: 50,
  }), [selectedType, dateFrom, dateTo, orgId])

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
  const displayRows = firstSection?.rows?.slice(0, 15) || []

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
                  ? `${firstSection?.title || 'Report'} — showing ${displayRows.length} of ${preview.total_rows} total rows`
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
                      <TableCell className="text-gray-400">{i + 1}</TableCell>
                      {row.map((cell, j) => (
                        <TableCell key={j} className="text-sm whitespace-nowrap max-w-[280px] truncate">
                          {cellText(cell)}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {firstSection.rows.length > 15 && (
                <p className="text-xs text-gray-500 mt-2">
                  Preview capped at 15 rows — the full {preview.total_rows} rows are included in the download.
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}