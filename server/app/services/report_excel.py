import io
from datetime import date
from typing import cast
from uuid import UUID

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.models import MealKind
from app.services.report_data import DayCounts, ReportData
from app.services.report_template import ReportTemplate

MEAL_LABELS: dict[MealKind, str] = {
    MealKind.breakfast: "Завтрак",
    MealKind.lunch: "Обед",
    MealKind.snack: "Полдник",
    MealKind.dinner: "Ужин",
}

MEAL_SHORT: dict[MealKind, str] = {
    MealKind.breakfast: "Звтр",
    MealKind.lunch: "Обд",
    MealKind.snack: "Плдн",
    MealKind.dinner: "Ужн",
}

_THIN = Side(style="thin")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_BOLD = Font(bold=True)
_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _fmt(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _weekday(value: date) -> str:
    return ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][value.weekday()]


def _values(
    counts: DayCounts,
    hall_ids: list[UUID],
    meal: MealKind,
    type_ids: list[UUID],
    reserve: bool,
) -> tuple[list[int], int]:
    """Сумма по залам без повторов: зал, указанный дважды, считается один раз."""
    per_type = [0] * len(type_ids)
    total = 0
    for hall_id in dict.fromkeys(hall_ids):
        per_hall = counts.get(hall_id)
        if not per_hall:
            continue
        for index, type_id in enumerate(type_ids):
            normal, reserved = per_hall.get(meal, {}).get(type_id, (0, 0))
            value = reserved if reserve else normal
            per_type[index] += value
            total += value
    return per_type, total


def _put_total_row(
    ws: Worksheet,
    row: int,
    label: str,
    counts: DayCounts,
    hall_ids: list[UUID],
    type_ids: list[UUID],
    show_reserve: bool,
) -> None:
    ws.cell(row=row, column=1, value=label).font = _BOLD
    col = 2
    for meal in MealKind:
        per_type, total = _values(counts, hall_ids, meal, type_ids, reserve=False)
        ws.cell(row=row, column=col, value=total)
        col += 1
        for value in per_type:
            ws.cell(row=row, column=col, value=value)
            col += 1
        if show_reserve:
            _, reserved = _values(counts, hall_ids, meal, type_ids, reserve=True)
            ws.cell(row=row, column=col, value=reserved)
            col += 1


def _write_hall_row(
    ws: Worksheet,
    row: int,
    label: str,
    counts: DayCounts,
    hall_id: UUID,
    type_ids: list[UUID],
    show_reserve: bool,
) -> None:
    ws.cell(row=row, column=1, value=label)
    col = 2
    for meal in MealKind:
        per_type, total = _values(counts, [hall_id], meal, type_ids, reserve=False)
        ws.cell(row=row, column=col, value=total)
        col += 1
        for value in per_type:
            ws.cell(row=row, column=col, value=value)
            col += 1
        if show_reserve:
            _, reserved = _values(counts, [hall_id], meal, type_ids, reserve=True)
            ws.cell(row=row, column=col, value=reserved)
            col += 1


def daily_report_to_xlsx(
    data: ReportData, template: ReportTemplate, *, show_reserve: bool
) -> bytes:
    wb = Workbook()
    ws = cast(Worksheet, wb.active)
    ws.title = "Отчет 1д"

    if not data.dates:
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    day = data.dates[0]
    counts = data.counts.get(day, {})
    type_ids = [tid for tid, _ in data.types]
    block = 1 + len(type_ids) + (1 if show_reserve else 0)
    last_col = 1 + block * len(MealKind)

    ws.cell(
        row=1, column=1,
        value=f"Количество питающихся по залам за: {_fmt(day)}",
    ).font = Font(bold=True, size=14)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)

    ws.cell(row=3, column=1, value="Зал")
    ws.merge_cells(start_row=3, start_column=1, end_row=4, end_column=1)
    col = 2
    for meal in MealKind:
        start = col
        headers = ["Итог"] + [name for _, name in data.types]
        if show_reserve:
            headers.append("Рез.")
        for header in headers:
            ws.cell(row=4, column=col, value=header)
            col += 1
        ws.cell(row=3, column=start, value=MEAL_LABELS[meal])
        ws.merge_cells(start_row=3, start_column=start, end_row=3, end_column=col - 1)

    row = 5
    groups = template.groups or []
    totals = template.totals or []
    all_halls = list(data.hall_names.keys())

    if not groups and not totals:
        for hall_id in all_halls:
            _write_hall_row(
                ws, row, data.hall_names[hall_id], counts, hall_id, type_ids, show_reserve
            )
            row += 1
        _put_total_row(ws, row, "ИТОГО", counts, all_halls, type_ids, show_reserve)
        row += 1
    else:
        for group in groups:
            for hall_id in group.hall_ids:
                _write_hall_row(
                    ws, row, data.hall_names.get(hall_id, "Зал"), counts, hall_id,
                    type_ids, show_reserve,
                )
                row += 1
            if group.show_subtotal:
                _put_total_row(
                    ws, row, f"Итого {group.name}", counts, group.hall_ids,
                    type_ids, show_reserve,
                )
                row += 1
        for total in totals:
            hall_ids = all_halls if total.all_halls else total.hall_ids
            _put_total_row(
                ws, row, total.name, counts, hall_ids, type_ids, show_reserve
            )
            row += 1

    _finish(ws, row - 1, last_col)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def period_report_to_xlsx(
    data: ReportData, template: ReportTemplate, *, show_reserve: bool
) -> bytes:
    wb = Workbook()
    ws = cast(Worksheet, wb.active)
    days = data.dates
    ws.title = f"Отчет {len(days)}д"

    if not days:
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    type_ids = [tid for tid, _ in data.types]
    per_day_cols = len(MealKind) * (2 if show_reserve else 1)
    last_col = 1 + per_day_cols * len(days)

    ws.cell(
        row=1, column=1,
        value=f"Количество питающихся за период: {_fmt(days[0])} – {_fmt(days[-1])}",
    ).font = Font(bold=True, size=14)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)

    ws.cell(row=3, column=1, value="Группа")
    ws.merge_cells(start_row=3, start_column=1, end_row=4, end_column=1)
    col = 2
    for day in days:
        start = col
        for meal in MealKind:
            ws.cell(row=4, column=col, value=MEAL_SHORT[meal])
            col += 1
            if show_reserve:
                ws.cell(row=4, column=col, value=f"{MEAL_SHORT[meal]} рез.")
                col += 1
        ws.cell(row=3, column=start, value=f"{_weekday(day)} {_fmt(day)}")
        ws.merge_cells(start_row=3, start_column=start, end_row=3, end_column=col - 1)

    def write_values(row: int, hall_ids: list[UUID], type_subset: list[UUID]) -> None:
        position = 2
        for day in days:
            counts = data.counts.get(day, {})
            for meal in MealKind:
                _, total = _values(counts, hall_ids, meal, type_subset, reserve=False)
                ws.cell(row=row, column=position, value=total)
                position += 1
                if show_reserve:
                    _, reserved = _values(
                        counts, hall_ids, meal, type_subset, reserve=True
                    )
                    ws.cell(row=row, column=position, value=reserved)
                    position += 1

    row = 5
    groups = template.groups or []
    totals = template.totals or []
    all_halls = list(data.hall_names.keys())

    if not groups and not totals:
        ws.cell(row=row, column=1, value="Все залы").font = _BOLD
        write_values(row, all_halls, type_ids)
        row += 1
        ws.cell(row=row, column=1, value="ИТОГО").font = _BOLD
        write_values(row, all_halls, type_ids)
        row += 1
    else:
        for group in groups:
            ws.cell(row=row, column=1, value=group.name).font = _BOLD
            write_values(row, group.hall_ids, type_ids)
            row += 1
            for type_id, name in data.types:
                ws.cell(row=row, column=1, value=name)
                write_values(row, group.hall_ids, [type_id])
                row += 1
        for total in totals:
            hall_ids = all_halls if total.all_halls else total.hall_ids
            ws.cell(row=row, column=1, value=total.name).font = _BOLD
            write_values(row, hall_ids, type_ids)
            row += 1

    _finish(ws, row - 1, last_col)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _finish(ws: Worksheet, last_row: int, last_col: int) -> None:
    for cells in ws.iter_rows(min_row=3, max_row=last_row, min_col=1, max_col=last_col):
        for cell in cells:
            cell.border = _BORDER
            if cell.row <= 4:
                cell.font = _BOLD
                cell.alignment = _CENTER
    for col in range(1, last_col + 1):
        widest = 0
        for row in range(3, last_row + 1):
            value = ws.cell(row=row, column=col).value
            if value is not None:
                widest = max(widest, len(str(value)))
        ws.column_dimensions[get_column_letter(col)].width = min(
            max(widest + 2, 7), 30
        )
    ws.freeze_panes = "B5"
