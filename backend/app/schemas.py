"""接口出入参模型：列表分页、动作结果与各模块的明细结构。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    """登记或修改一条业务记录时提交的字段集合。"""

    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class ImportReport(BaseModel):
    """台账导入结果：合并数量与被跳过行号（表格行号，含表头，从 1 起）。"""

    ok: bool = True
    created: int = 0
    updated: int = 0
    imported: int = 0
    skipped_rows: list[int] = Field(default_factory=list)
    skipped: list[dict[str, Any]] = Field(default_factory=list)



class InterlockEntry(BaseModel):
    """联锁道岔明细结构。"""

    field_0: str | None = None  # 道岔编号
    field_1: str | None = None  # 所属车站
    field_2: str | None = None  # 道岔类型
    field_3: str | None = None  # 联锁关系
    field_4: str | None = None  # 锁闭方式
    field_5: str | None = None  # 动作次数
    field_6: str | None = None  # 检修周期
    field_7: str | None = None  # 道岔状态

class TrackcircuitEntry(BaseModel):
    """轨道电路明细结构。"""

    field_0: str | None = None  # 区段编号
    field_1: str | None = None  # 所属区间
    field_2: str | None = None  # 载频类型
    field_3: str | None = None  # 发送电平
    field_4: str | None = None  # 接收电平
    field_5: str | None = None  # 调整状态
    field_6: str | None = None  # 分路灵敏度
    field_7: str | None = None  # 电路状态

class SignalEntry(BaseModel):
    """信号机明细结构。"""

    field_0: str | None = None  # 信号机编号
    field_1: str | None = None  # 所属车站
    field_2: str | None = None  # 信号机类型
    field_3: str | None = None  # 灯位配置
    field_4: str | None = None  # 显示距离
    field_5: str | None = None  # 灯泡寿命
    field_6: str | None = None  # 点灯单元
    field_7: str | None = None  # 信号机状态

class PointmachineEntry(BaseModel):
    """转辙机明细结构。"""

    field_0: str | None = None  # 转辙机编号
    field_1: str | None = None  # 所属道岔
    field_2: str | None = None  # 转辙机型号
    field_3: str | None = None  # 动作电流
    field_4: str | None = None  # 摩擦电流
    field_5: str | None = None  # 表示缺口
    field_6: str | None = None  # 润滑状态
    field_7: str | None = None  # 转辙机状态

class CableEntry(BaseModel):
    """信号电缆明细结构。"""

    field_0: str | None = None  # 电缆编号
    field_1: str | None = None  # 起止站点
    field_2: str | None = None  # 电缆芯数
    field_3: str | None = None  # 绝缘电阻
    field_4: str | None = None  # 对地电压
    field_5: str | None = None  # 敷设方式
    field_6: str | None = None  # 接头数量
    field_7: str | None = None  # 电缆状态

class PowersupplyEntry(BaseModel):
    """电源屏明细结构。"""

    field_0: str | None = None  # 电源屏编号
    field_1: str | None = None  # 所属车站
    field_2: str | None = None  # 输入电压
    field_3: str | None = None  # 输出电压
    field_4: str | None = None  # 输出电流
    field_5: str | None = None  # 模块配置
    field_6: str | None = None  # 切换装置
    field_7: str | None = None  # 电源状态

class AtpEntry(BaseModel):
    """车载ATP明细结构。"""

    field_0: str | None = None  # 设备编号
    field_1: str | None = None  # 所属列车
    field_2: str | None = None  # 设备型号
    field_3: str | None = None  # 软件版本
    field_4: str | None = None  # 自检状态
    field_5: str | None = None  # 制动接口
    field_6: str | None = None  # 记录数据
    field_7: str | None = None  # 车载状态

class BaliseEntry(BaseModel):
    """应答器明细结构。"""

    field_0: str | None = None  # 应答器编号
    field_1: str | None = None  # 所在位置
    field_2: str | None = None  # 报文版本
    field_3: str | None = None  # 激活距离
    field_4: str | None = None  # 接收电平
    field_5: str | None = None  # 安装方式
    field_6: str | None = None  # 固定状态
    field_7: str | None = None  # 应答器状态

class AxlecounterEntry(BaseModel):
    """计轴器明细结构。"""

    field_0: str | None = None  # 计轴器编号
    field_1: str | None = None  # 所属区间
    field_2: str | None = None  # 检测磁头
    field_3: str | None = None  # 轮轴脉冲
    field_4: str | None = None  # 计数偏差
    field_5: str | None = None  # 复位状态
    field_6: str | None = None  # 校核记录
    field_7: str | None = None  # 计轴状态

class DispatchcenterEntry(BaseModel):
    """调度台明细结构。"""

    field_0: str | None = None  # 调度台编号
    field_1: str | None = None  # 管辖范围
    field_2: str | None = None  # 显示设备
    field_3: str | None = None  # 操作终端
    field_4: str | None = None  # 通信链路
    field_5: str | None = None  # 通道状态
    field_6: str | None = None  # 备用方式
    field_7: str | None = None  # 调度台状态

class MaintenancewindowEntry(BaseModel):
    """天窗计划明细结构。"""

    field_0: str | None = None  # 计划编号
    field_1: str | None = None  # 作业日期
    field_2: str | None = None  # 作业区间
    field_3: str | None = None  # 封锁时段
    field_4: str | None = None  # 作业内容
    field_5: str | None = None  # 作业班组
    field_6: str | None = None  # 驻站联络
    field_7: str | None = None  # 作业状态

class RelayEntry(BaseModel):
    """继电器明细结构。"""

    field_0: str | None = None  # 继电器编号
    field_1: str | None = None  # 继电器型号
    field_2: str | None = None  # 所属设备
    field_3: str | None = None  # 电气特性
    field_4: str | None = None  # 接点电阻
    field_5: str | None = None  # 检修日期
    field_6: str | None = None  # 下次检修日
    field_7: str | None = None  # 继电器状态

class FuseEntry(BaseModel):
    """熔断器明细结构。"""

    field_0: str | None = None  # 熔断器编号
    field_1: str | None = None  # 额定电流
    field_2: str | None = None  # 安装位置
    field_3: str | None = None  # 保护范围
    field_4: str | None = None  # 熔断记录
    field_5: str | None = None  # 更换日期
    field_6: str | None = None  # 备件存量
    field_7: str | None = None  # 熔断器状态

class LightningEntry(BaseModel):
    """防雷元件明细结构。"""

    field_0: str | None = None  # 元件编号
    field_1: str | None = None  # 安装位置
    field_2: str | None = None  # 防护等级
    field_3: str | None = None  # 泄露电流
    field_4: str | None = None  # 动作次数
    field_5: str | None = None  # 测试日期
    field_6: str | None = None  # 更换记录
    field_7: str | None = None  # 元件状态

class EmergencyrespEntry(BaseModel):
    """应急备品明细结构。"""

    field_0: str | None = None  # 备品编号
    field_1: str | None = None  # 备品名称
    field_2: str | None = None  # 规格型号
    field_3: str | None = None  # 适用场景
    field_4: str | None = None  # 存放地点
    field_5: str | None = None  # 保有数量
    field_6: str | None = None  # 领用记录
    field_7: str | None = None  # 备品状态

class TestrecordEntry(BaseModel):
    """试验记录明细结构。"""

    field_0: str | None = None  # 试验编号
    field_1: str | None = None  # 试验日期
    field_2: str | None = None  # 试验车站
    field_3: str | None = None  # 试验项目
    field_4: str | None = None  # 试验人员
    field_5: str | None = None  # 试验结果
    field_6: str | None = None  # 遗留问题
    field_7: str | None = None  # 试验状态

class FaultEntry(BaseModel):
    """故障记录明细结构。"""

    field_0: str | None = None  # 故障编号
    field_1: str | None = None  # 发生时间
    field_2: str | None = None  # 故障设备
    field_3: str | None = None  # 故障现象
    field_4: str | None = None  # 影响范围
    field_5: str | None = None  # 恢复时间
    field_6: str | None = None  # 处理人员
    field_7: str | None = None  # 故障状态

class ToolEntry(BaseModel):
    """检修工具明细结构。"""

    field_0: str | None = None  # 工具编号
    field_1: str | None = None  # 工具名称
    field_2: str | None = None  # 规格型号
    field_3: str | None = None  # 检定日期
    field_4: str | None = None  # 下次检定日
    field_5: str | None = None  # 存放位置
    field_6: str | None = None  # 领用人
    field_7: str | None = None  # 工具状态

class RegulationEntry(BaseModel):
    """技术规章明细结构。"""

    field_0: str | None = None  # 规章编号
    field_1: str | None = None  # 规章名称
    field_2: str | None = None  # 适用专业
    field_3: str | None = None  # 版本号
    field_4: str | None = None  # 发布日期
    field_5: str | None = None  # 实施日期
    field_6: str | None = None  # 编制单位
    field_7: str | None = None  # 规章状态

class TrainingEntry(BaseModel):
    """培训记录明细结构。"""

    field_0: str | None = None  # 培训编号
    field_1: str | None = None  # 培训主题
    field_2: str | None = None  # 培训对象
    field_3: str | None = None  # 培训日期
    field_4: str | None = None  # 培训讲师
    field_5: str | None = None  # 考核方式
    field_6: str | None = None  # 考核结果
    field_7: str | None = None  # 培训状态
