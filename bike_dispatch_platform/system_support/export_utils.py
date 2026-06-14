from __future__ import annotations

from io import BytesIO

import pandas as pd
from django.http import HttpResponse


def resolve_export_format(request, default: str = "csv") -> str:
    export_format = (request.GET.get("format") or default).strip().lower()
    if export_format not in {"csv", "xlsx"}:
        export_format = default
    return export_format


def dataframe_to_response(
    dataframe: pd.DataFrame,
    filename_stem: str,
    export_format: str = "csv",
    sheet_name: str = "report",
) -> HttpResponse:
    if export_format == "xlsx":
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name=sheet_name[:31] or "report")
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename_stem}.xlsx"'
        return response

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="{filename_stem}.csv"'
    dataframe.to_csv(response, index=False, encoding="utf-8-sig")
    return response
