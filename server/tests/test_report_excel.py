import datetime as dt
import io
import uuid

import openpyxl

from app.models import MealKind
from app.services import report_excel
from app.services.report_data import ReportData
from app.services.report_template import ReportTemplate, TemplateGroup, TemplateTotal

T1, T2 = uuid.uuid4(), uuid.uuid4()
H1, H2 = uuid.uuid4(), uuid.uuid4()


def _data():
    zeros = {mk: {T1: (0, 0), T2: (0, 0)} for mk in MealKind}
    breakfast = dict(zeros)
    breakfast[MealKind.breakfast] = {T1: (5, 2), T2: (1, 0)}
    lunch = dict(zeros)
    lunch[MealKind.lunch] = {T1: (3, 0), T2: (0, 0)}
    return ReportData(
        types=[(T1, "Мясо"), (T2, "Рыба")],
        dates=[dt.date(2026, 6, 10)],
        hall_names={H1: "Зал №1", H2: "Зал №2"},
        counts={dt.date(2026, 6, 10): {H1: breakfast, H2: lunch}},
    )


def _sheet(content):
    return openpyxl.load_workbook(io.BytesIO(content)).active


def test_daily_layout_with_groups_and_total():
    template = ReportTemplate(
        groups=[TemplateGroup(id=None, name="Студенты", show_subtotal=True,
                              hall_ids=[H1, H2])],
        totals=[TemplateTotal(id=None, name="ИТОГО", all_halls=True, hall_ids=[])],
    )
    ws = _sheet(report_excel.daily_report_to_xlsx(_data(), template, show_reserve=False))

    labels = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    assert "Зал №1" in labels
    assert "Зал №2" in labels
    assert "Итого Студенты" in labels
    assert "ИТОГО" in labels

    # строка зала: Завтрак: Итог | Мясо | Рыба
    row = labels.index("Зал №1") + 1
    assert ws.cell(row=row, column=2).value == 6      # 5 + 1
    assert ws.cell(row=row, column=3).value == 5      # Мясо
    assert ws.cell(row=row, column=4).value == 1      # Рыба

    # подытог группы = оба зала: завтрак 6, обед 3 (обед — 5-я колонка)
    sub = labels.index("Итого Студенты") + 1
    assert ws.cell(row=sub, column=2).value == 6
    assert ws.cell(row=sub, column=5).value == 3


def test_total_counts_hall_once_when_it_is_in_two_groups():
    template = ReportTemplate(
        groups=[
            TemplateGroup(id=None, name="A", show_subtotal=True, hall_ids=[H1]),
            TemplateGroup(id=None, name="B", show_subtotal=True, hall_ids=[H1]),
        ],
        totals=[TemplateTotal(id=None, name="ИТОГО", all_halls=True, hall_ids=[])],
    )
    ws = _sheet(report_excel.daily_report_to_xlsx(_data(), template, show_reserve=False))
    labels = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    total = labels.index("ИТОГО") + 1
    # завтрак только у H1 (6), обед только у H2 (3); H1 не удваивается
    assert ws.cell(row=total, column=2).value == 6
    assert ws.cell(row=total, column=5).value == 3


def test_reserve_column_toggle():
    template = ReportTemplate(totals=[TemplateTotal(id=None, name="ИТОГО",
                                                     all_halls=True, hall_ids=[])])
    plain = _sheet(report_excel.daily_report_to_xlsx(_data(), template, show_reserve=False))
    with_reserve = _sheet(report_excel.daily_report_to_xlsx(_data(), template, show_reserve=True))

    headers = [with_reserve.cell(row=4, column=c).value for c in range(1, 10)]
    assert "Рез." in headers
    plain_headers = [plain.cell(row=4, column=c).value for c in range(1, 10)]
    assert "Рез." not in plain_headers
    assert with_reserve.max_column == plain.max_column + 4


def test_empty_template_falls_back_to_flat_halls():
    ws = _sheet(report_excel.daily_report_to_xlsx(_data(), ReportTemplate(), show_reserve=False))
    labels = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    assert "Зал №1" in labels and "Зал №2" in labels
    assert "ИТОГО" in labels


def test_period_layout_has_day_blocks():
    data = _data()
    data.dates = [dt.date(2026, 6, 10), dt.date(2026, 6, 11)]
    data.counts[dt.date(2026, 6, 11)] = data.counts[dt.date(2026, 6, 10)]
    template = ReportTemplate(
        groups=[TemplateGroup(id=None, name="Студенты", show_subtotal=True, hall_ids=[H1, H2])],
        totals=[TemplateTotal(id=None, name="ИТОГО", all_halls=True, hall_ids=[])],
    )
    ws = _sheet(report_excel.period_report_to_xlsx(data, template, show_reserve=True))

    assert ws.title == "Отчет 2д"
    headers = [ws.cell(row=4, column=c).value for c in range(1, 20)]
    assert headers.count("Звтр") == 2
    assert headers.count("Звтр рез.") == 2
    labels = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    assert "Студенты" in labels
    assert "Мясо" in labels
    assert "ИТОГО" in labels


def _is_blue(cell) -> bool:
    return cell.fill.fill_type == "solid" and cell.fill.fgColor.rgb.endswith("DCE6F1")


def test_daily_total_rows_are_highlighted():
    template = ReportTemplate(
        groups=[TemplateGroup(id=None, name="Студенты", show_subtotal=True,
                              hall_ids=[H1, H2])],
        totals=[TemplateTotal(id=None, name="ИТОГО", all_halls=True, hall_ids=[])],
    )
    ws = _sheet(report_excel.daily_report_to_xlsx(_data(), template, show_reserve=False))
    labels = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]

    sub = labels.index("Итого Студенты") + 1
    total = labels.index("ИТОГО") + 1
    hall = labels.index("Зал №1") + 1

    # заливка идёт по всей ширине строки итога
    assert _is_blue(ws.cell(row=sub, column=1))
    assert _is_blue(ws.cell(row=sub, column=ws.max_column))
    assert _is_blue(ws.cell(row=total, column=1))
    assert _is_blue(ws.cell(row=total, column=ws.max_column))
    # строка зала остаётся без заливки
    assert ws.cell(row=hall, column=1).fill.fill_type is None


def test_daily_flat_total_is_highlighted():
    ws = _sheet(report_excel.daily_report_to_xlsx(_data(), ReportTemplate(), show_reserve=False))
    labels = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]

    total = labels.index("ИТОГО") + 1
    assert _is_blue(ws.cell(row=total, column=1))


def test_period_total_rows_are_highlighted():
    data = _data()
    data.dates = [dt.date(2026, 6, 10), dt.date(2026, 6, 11)]
    data.counts[dt.date(2026, 6, 11)] = data.counts[dt.date(2026, 6, 10)]
    template = ReportTemplate(
        groups=[TemplateGroup(id=None, name="Студенты", show_subtotal=True, hall_ids=[H1, H2])],
        totals=[TemplateTotal(id=None, name="ИТОГО", all_halls=True, hall_ids=[])],
    )
    ws = _sheet(report_excel.period_report_to_xlsx(data, template, show_reserve=False))
    labels = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]

    group = labels.index("Студенты") + 1
    total = labels.index("ИТОГО") + 1
    breakdown = labels.index("Мясо") + 1

    assert _is_blue(ws.cell(row=group, column=1))
    assert _is_blue(ws.cell(row=total, column=ws.max_column))
    assert ws.cell(row=breakdown, column=1).fill.fill_type is None
