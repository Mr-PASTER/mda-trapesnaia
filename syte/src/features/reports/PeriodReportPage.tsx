import { useState } from "react";
import { todayIso } from "../../lib/dates";
import { usePeriodReport, periodExportUrl } from "../../api/reports";
import { ReportTable, type ReportHallRow } from "./ReportTable";
import { downloadExport } from "./downloadExport";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { Input } from "../../components/ui/Input";

function firstDayOfMonth(): string {
  return `${todayIso().slice(0, 8)}01`;
}

export function PeriodReportPage() {
  const [from, setFrom] = useState(firstDayOfMonth());
  const [to, setTo] = useState(todayIso());
  const [downloadError, setDownloadError] = useState(false);
  const { data, isLoading, isError } = usePeriodReport(from, to);

  const rows: ReportHallRow[] = (data?.halls ?? []).map((h) => ({
    hallId: h.hall_id,
    hallName: h.hall_name,
    meals: h.meals,
    total: h.period_total,
    reserveTotal: h.period_reserve_total,
  }));

  function handleExport() {
    setDownloadError(false);
    downloadExport(periodExportUrl(from, to)).catch(() => setDownloadError(true));
  }

  return (
    <div className="mx-auto max-w-6xl p-4">
      <h1 className="mb-4 text-xl font-semibold">Отчёт за период</h1>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          С
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label className="text-sm">
          По
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
        <button
          type="button"
          onClick={handleExport}
          className="inline-flex min-h-11 items-center rounded-xl border border-border px-4 text-sm hover:bg-surface"
        >
          Скачать Excel
        </button>
      </div>

      {downloadError && <p className="mb-4 text-sm font-medium text-accent">Не удалось скачать файл</p>}
      {isLoading && <Spinner />}
      {isError && <p className="text-sm font-medium text-accent">Не удалось загрузить отчёт</p>}
      {data && rows.length === 0 && <EmptyState title="За выбранный период данных нет" />}
      {rows.length > 0 && (
        <ReportTable rows={rows} grandTotal={data!.grand_total} grandReserveTotal={data!.grand_reserve_total} />
      )}
    </div>
  );
}
