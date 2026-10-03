import { useState } from "react";
import { todayIso } from "../../lib/dates";
import { useDailyReport, dailyExportUrl } from "../../api/reports";
import { ReportTable, type ReportHallRow } from "./ReportTable";
import { downloadExport } from "./downloadExport";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { Input } from "../../components/ui/Input";

export function DailyReportPage() {
  const [date, setDate] = useState(todayIso());
  const [downloadError, setDownloadError] = useState(false);
  const { data, isLoading, isError } = useDailyReport(date);

  const rows: ReportHallRow[] = (data?.halls ?? []).map((h) => ({
    hallId: h.hall_id,
    hallName: h.hall_name,
    meals: h.meals,
    total: h.day_total,
    reserveTotal: h.day_reserve_total,
  }));

  function handleExport() {
    setDownloadError(false);
    downloadExport(dailyExportUrl(date)).catch(() => setDownloadError(true));
  }

  return (
    <div className="mx-auto max-w-6xl p-4">
      <h1 className="mb-4 text-xl font-semibold">Отчёт за день</h1>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          Дата
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
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
      {data && rows.length === 0 && <EmptyState title="За выбранный день данных нет" />}
      {rows.length > 0 && (
        <ReportTable rows={rows} grandTotal={data!.grand_total} grandReserveTotal={data!.grand_reserve_total} />
      )}
    </div>
  );
}
