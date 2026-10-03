import { getDeviceFingerprint } from "../../api/fingerprint";

function filenameFrom(response: Response): string {
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  return match?.[1] ?? "report.xlsx";
}

/**
 * Скачивает экспортный эндпоинт и отдаёт файл браузеру.
 * Экспорт защищён тем же guard'ом, что и остальные запросы, поэтому нужен
 * заголовок X-Device-Fingerprint — обычная ссылка <a download> его не отправит.
 */
export async function downloadExport(url: string): Promise<void> {
  const fingerprint = await getDeviceFingerprint();
  const response = await fetch(url, {
    headers: { "X-Device-Fingerprint": fingerprint },
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);

  const objectUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filenameFrom(response);
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
