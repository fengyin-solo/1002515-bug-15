"""信号电缆接口：维护信号电缆，覆盖台账导入导出、登记报警、查找接地点、办理更换等动作。"""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.schemas import ActionResult, EntryPayload, ImportReport, PageResult
from app.services.cable import FIELD_ORDER, HeaderMismatchError, STATUS_ORDER, CableService

router = APIRouter(prefix="/api/cable", tags=["信号电缆"])

service = CableService()

STATUSES = STATUS_ORDER


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按电缆编号检索"),
    status: str | None = Query(default=None, description="绝缘良好、绝缘下降、接地报警、已更换"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按电缆编号与状态过滤信号电缆列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


# 注意：/import、/export 必须排在 /{entry_id} 之前，否则会被当成电缆编号匹配。
@router.post("/import", response_model=ImportReport)
async def import_entries(request: Request) -> ImportReport:
    """导入信号电缆台账（CSV，UTF-8）。

    - 表头列名与顺序必须与模板完全一致，否则整批退回（400）且不写任何数据；
    - 必填列（电缆编号、起止站点、电缆芯数）为空或整行空白的行整行跳过，行号在结果里给出；
    - 按电缆编号合并：已存在则更新，不存在才新增，重复导入不会多出一份；
    - 非必填列（如绝缘电阻）为空时保留空值，不补零。
    """
    try:
        text = (await request.body()).decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件不是 UTF-8 编码的 CSV，请另存为 UTF-8 后重试")
    try:
        report = service.import_rows(text)
    except HeaderMismatchError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ImportReport(**report)


@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None, description="按电缆编号检索，与列表筛选保持一致"),
    status: str | None = Query(default=None, description="按电缆状态过滤，与列表筛选保持一致"),
) -> Response:
    """按当前筛选条件导出 CSV：列顺序固定，含起止站点、对地电压与电缆状态，空值留空不补零。"""
    rows = service.export_rows(keyword=keyword, status=status)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELD_ORDER, lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    # utf-8-sig 带 BOM，Excel 直接打开不乱码；\r\n 是表格软件通用的行尾。
    data = buffer.getvalue().encode("utf-8-sig")
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cable-ledger.csv"'},
    )


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条信号电缆明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"信号电缆 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条信号电缆，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="信号电缆已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条信号电缆执行登记报警、查找接地点、办理更换；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
