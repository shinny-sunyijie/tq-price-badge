# -*- coding: utf-8 -*-
import math

from PySide6 import QtWidgets, QtGui, QtCore

from ..backend import state


def _读取字段(记录: dict, *字段名, 默认=None):
    """兼容账户快照中常见的中英文字段名。"""

    if not isinstance(记录, dict):
        return 默认
    for 字段 in 字段名:
        if 字段 in 记录 and 记录[字段] is not None:
            return 记录[字段]
    return 默认


def _有效数字(值):
    if isinstance(值, bool) or not isinstance(值, (int, float)):
        return None
    数字 = float(值)
    return 数字 if math.isfinite(数字) else None


def _格式化数值(值, 默认="—", 千分位=False, 正负号=False, 小数位=None):
    数字 = _有效数字(值)
    if 数字 is None:
        文本 = str(值).strip() if 值 is not None else ""
        return 文本 if 文本 and 文本.lower() not in {"nan", "none"} else 默认

    if 小数位 is not None:
        try:
            小数位 = max(0, min(10, int(小数位)))
        except (TypeError, ValueError):
            小数位 = None
    if 小数位 is not None:
        格式 = ("+,." if 正负号 else (",." if 千分位 else ".")) + f"{小数位}f"
    elif 数字.is_integer():
        格式 = "+,.0f" if 正负号 else (",.0f" if 千分位 else ".0f")
    else:
        格式 = "+,.2f" if 正负号 else (",.2f" if 千分位 else ".2f")
    return format(数字, 格式)


def _标准化记录列表(数据, 值字段="value") -> list[dict]:
    """允许调用端传 list，也兼容以合约或委托号为键的 dict。"""

    if 数据 is None:
        return []
    if isinstance(数据, (list, tuple)):
        return [项 for 项 in 数据 if isinstance(项, dict)]
    if not isinstance(数据, dict):
        return []

    if any(键 in 数据 for 键 in ("symbol", "instrument_id", "合约", "合约代码")):
        return [数据]

    结果 = []
    for 键, 值 in 数据.items():
        if isinstance(值, dict):
            记录 = dict(值)
            记录.setdefault("symbol", 键)
        else:
            记录 = {"symbol": 键, 值字段: 值}
        结果.append(记录)
    return 结果


class _只读表格区(QtWidgets.QWidget):
    """由可复用 ``QLabel`` 组成的小型只读表格。

    实盘快照更新频率较高。旧实现每次都会先把所有标签移出部件树，再依靠
    ``deleteLater`` 删除并重建；布局和顶层窗口会在这段空档读到只有标题的
    ``sizeHint``，从而把面板裁短。这里保留一个标签池，并在关闭绘制期间一次
    性更新文本、样式和布局位置，任何时刻都不会向屏幕提交空表格。
    """

    def __init__(self, 父=None):
        super().__init__(父)
        self._垂直布局 = QtWidgets.QVBoxLayout(self)
        self._垂直布局.setContentsMargins(0, 0, 0, 0)
        self._垂直布局.setSpacing(0)

        self.标题标签 = QtWidgets.QLabel(self)
        标题字体 = QtGui.QFont(state.默认字体族, 10)
        标题字体.setBold(True)
        self.标题标签.setFont(标题字体)
        self.标题标签.setStyleSheet("color:#DADCE0; background:transparent;")
        self._垂直布局.addWidget(self.标题标签)

        self._表格容器 = QtWidgets.QWidget(self)
        self._表格布局 = QtWidgets.QGridLayout(self._表格容器)
        self._表格布局.setContentsMargins(0, 0, 0, 0)
        self._表格布局.setHorizontalSpacing(4)
        self._表格布局.setVerticalSpacing(0)
        self._垂直布局.addWidget(self._表格容器)

        self._字号 = 9
        self._单元格池: list[QtWidgets.QLabel] = []
        self._内容签名 = None

    def _新建单元格(self, 文本, 颜色="#E8EAED", 粗体=False, 对齐=None):
        标签 = QtWidgets.QLabel(str(文本), self._表格容器)
        字体 = QtGui.QFont(state.默认字体族, self._字号)
        字体.setBold(粗体)
        标签.setFont(字体)
        标签.setTextFormat(QtCore.Qt.PlainText)
        标签.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        标签.setStyleSheet(f"color:{颜色}; background:transparent;")
        if 对齐 is not None:
            标签.setAlignment(对齐)
        return 标签

    def _取得单元格(self, 序号: int) -> QtWidgets.QLabel:
        while len(self._单元格池) <= 序号:
            标签 = self._新建单元格("")
            标签.hide()
            self._单元格池.append(标签)
        return self._单元格池[序号]

    def _设置单元格(self, 序号, 行, 列, 文本, 颜色, 粗体, 对齐, 列跨度=1):
        标签 = self._取得单元格(序号)
        字体 = 标签.font()
        字体.setFamily(state.默认字体族)
        字体.setPointSize(self._字号)
        字体.setBold(粗体)
        标签.setFont(字体)
        标签.setText(str(文本))
        标签.setStyleSheet(f"color:{颜色}; background:transparent;")
        标签.setAlignment(对齐)
        # 再次 addWidget 会把已在布局中的池标签原子地移动到新网格位置，并可
        # 同时更新空状态单元格的列跨度；标签对象本身始终保持不变。
        self._表格布局.addWidget(标签, 行, 列, 1, 列跨度)
        标签.show()

    @staticmethod
    def _生成内容签名(标题, 表头, 行数据, 空文本):
        # 行数据只含展示文本和可选颜色元组，repr 足以作为稳定且廉价的比较键。
        return (str(标题), tuple(map(str, 表头)), repr(行数据), str(空文本))

    def 应用字号(self, 字号) -> bool:
        """调整本模块字号；返回是否真的发生了变化。"""

        try:
            新字号 = max(6, min(72, int(字号)))
        except (TypeError, ValueError, OverflowError):
            return False
        if 新字号 == self._字号:
            return False

        self._字号 = 新字号
        标题字体 = self.标题标签.font()
        标题字体.setFamily(state.默认字体族)
        标题字体.setPointSize(新字号 + 1)
        标题字体.setBold(True)
        self.标题标签.setFont(标题字体)
        for 标签 in self._单元格池:
            字体 = 标签.font()
            字体.setFamily(state.默认字体族)
            字体.setPointSize(新字号)
            标签.setFont(字体)

        self._表格布局.invalidate()
        self._垂直布局.invalidate()
        self.updateGeometry()
        return True

    def 更新内容(self, 标题: str, 表头: tuple[str, ...], 行数据: list, 空文本: str):
        内容签名 = self._生成内容签名(标题, 表头, 行数据, 空文本)
        if 内容签名 == self._内容签名:
            return False

        self.setUpdatesEnabled(False)
        self.标题标签.setText(标题)
        self.标题标签.setVisible(bool(str(标题).strip()))
        try:
            for 标签 in self._单元格池:
                标签.hide()

            序号 = 0
            if not 行数据:
                self._设置单元格(
                    序号, 0, 0, 空文本, "#8A9099", False,
                    QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                    max(1, len(表头)),
                )
                序号 += 1
            else:
                for 列, 文本 in enumerate(表头):
                    对齐 = (QtCore.Qt.AlignRight if 列 else QtCore.Qt.AlignLeft) | QtCore.Qt.AlignVCenter
                    self._设置单元格(序号, 0, 列, 文本, "#8A9099", True, 对齐)
                    序号 += 1

                首行 = 1 if 表头 else 0
                for 行号, 一行 in enumerate(行数据, start=首行):
                    for 列, 单元格 in enumerate(一行):
                        颜色 = "#E8EAED"
                        文本 = 单元格
                        if isinstance(单元格, tuple):
                            文本, 颜色 = 单元格
                        对齐 = (QtCore.Qt.AlignRight if 列 else QtCore.Qt.AlignLeft) | QtCore.Qt.AlignVCenter
                        self._设置单元格(序号, 行号, 列, 文本, 颜色, False, 对齐)
                        序号 += 1

            self._内容签名 = 内容签名
            self._表格布局.invalidate()
            self._垂直布局.invalidate()
            self._表格布局.activate()
            self._垂直布局.activate()
            self.updateGeometry()
        finally:
            self.setUpdatesEnabled(True)
            self.update()
        return True


class 账户监控面板(QtWidgets.QFrame):
    """透明、只读的实盘账户摘要；不包含任何下单或撤单入口。"""

    内容尺寸变更 = QtCore.Signal()

    def __init__(self, 父=None):
        super().__init__(父)
        self.setObjectName("accountMonitorPanel")
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        self.setStyleSheet(
            "QFrame#accountMonitorPanel { background:transparent; border:0; }"
        )

        self._显示持仓监控 = False
        self._显示委托监控 = False
        self._显示设置已指定 = False
        self._收到状态 = False
        self._账户状态 = None
        self._自动行情: list[dict] = []
        self._持仓: list[dict] = []
        self._委托: list[dict] = []
        self._模块位置: dict[str, QtCore.QPoint | None] = {
            "status": None,
            "quote": None,
            "position": None,
            "order": None,
        }
        self._布局尺寸 = QtCore.QSize(1, 1)

        self.账户状态标签 = QtWidgets.QLabel(self)
        状态字体 = QtGui.QFont(state.默认字体族, 9)
        状态字体.setBold(True)
        self.账户状态标签.setFont(状态字体)
        self.账户状态标签.setTextFormat(QtCore.Qt.PlainText)
        self.账户状态标签.setWordWrap(False)
        self.账户状态标签.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)

        # 仅为兼容旧调用和旧设置保留对象；行情会按合约直接并入委托/持仓行，
        # 该区域不再作为一个独立模块显示。
        self.自动行情区 = _只读表格区(self)
        self.自动行情区.hide()
        self.持仓区 = _只读表格区(self)
        self.委托区 = _只读表格区(self)

        self.应用账户设置(state.配置, 发出尺寸信号=False)
        self._刷新界面()

    @staticmethod
    def _可选位置(值) -> QtCore.QPoint | None:
        if isinstance(值, QtCore.QPoint):
            return QtCore.QPoint(值)
        if not isinstance(值, dict) or "x" not in 值 or "y" not in 值:
            return None
        try:
            return QtCore.QPoint(max(0, int(值["x"])), max(0, int(值["y"])))
        except (TypeError, ValueError, OverflowError):
            return None

    def 应用账户设置(self, 配置: dict | None = None, *, 发出尺寸信号=True):
        """应用账户文字字号及模块位置。

        ``account_*_pos`` 坐标均相对本账户面板；缺失或 ``None`` 时，该模块
        继续参加稳定的自动纵向排列。面板整体在悬浮窗中的位置由外层窗口读取
        ``account_panel_pos`` 后决定。旧版 quote 字号/位置仍可读取，但独立
        行情表永久隐藏，避免旧配置迁移时出错。
        """

        配置 = state.配置 if 配置 is None else 配置
        if not isinstance(配置, dict):
            return

        try:
            状态字号 = max(6, min(72, int(配置.get("account_status_font_size", 9))))
        except (TypeError, ValueError, OverflowError):
            状态字号 = 9
        状态字体 = self.账户状态标签.font()
        状态字体.setFamily(state.默认字体族)
        状态字体.setPointSize(状态字号)
        状态字体.setBold(True)
        self.账户状态标签.setFont(状态字体)

        self.自动行情区.应用字号(配置.get("account_quote_font_size", 9))
        self.持仓区.应用字号(配置.get("account_position_font_size", 9))
        self.委托区.应用字号(配置.get("account_order_font_size", 9))
        self._模块位置 = {
            "status": self._可选位置(配置.get("account_status_pos")),
            "quote": self._可选位置(配置.get("account_quote_pos")),
            "position": self._可选位置(配置.get("account_position_pos")),
            "order": self._可选位置(配置.get("account_order_pos")),
        }
        self._重排模块()
        if 发出尺寸信号:
            self.内容尺寸变更.emit()

    def _重排模块(self):
        """在一帧内完成所有可见模块的测量、移动及面板尺寸提交。"""

        模块 = (
            ("status", self.账户状态标签),
            ("order", self.委托区),
            ("position", self.持仓区),
        )
        可见模块 = []
        for 名称, 部件 in 模块:
            if 部件.isHidden():
                continue
            部件.ensurePolished()
            if isinstance(部件, _只读表格区):
                部件._表格布局.invalidate()
                部件._垂直布局.invalidate()
                部件._表格布局.activate()
                部件._垂直布局.activate()
            部件.adjustSize()
            提示大小 = 部件.sizeHint().expandedTo(部件.minimumSizeHint())
            部件.resize(max(1, 提示大小.width()), max(1, 提示大小.height()))
            可见模块.append((名称, 部件))

        # 所有手工坐标先参与占位计算。因此用户只手工移动某一项时，
        # 其余保持“自动”的模块会绕开它，不会再被新字号或新内容挤在一起。
        手工矩形 = []
        for 名称, 部件 in 可见模块:
            指定位置 = self._模块位置.get(名称)
            if 指定位置 is None:
                continue
            位置 = QtCore.QPoint(max(0, 指定位置.x()), max(0, 指定位置.y()))
            手工矩形.append(QtCore.QRect(位置, 部件.size()))

        已放置自动矩形 = []
        下一自动_y = 0
        最大右边 = 1
        最大下边 = 1
        for 名称, 部件 in 可见模块:
            指定位置 = self._模块位置.get(名称)
            if 指定位置 is not None:
                目标位置 = QtCore.QPoint(max(0, 指定位置.x()), max(0, 指定位置.y()))
            else:
                目标位置 = QtCore.QPoint(0, 下一自动_y)
                while True:
                    候选矩形 = QtCore.QRect(目标位置, 部件.size())
                    冲突矩形 = [
                        矩形 for 矩形 in (*手工矩形, *已放置自动矩形)
                        if 候选矩形.intersects(矩形)
                    ]
                    if not 冲突矩形:
                        break
                    目标位置.setY(max(矩形.bottom() + 3 for 矩形 in 冲突矩形))
                已放置自动矩形.append(QtCore.QRect(目标位置, 部件.size()))
                # 状态与数据之间留一个很小的呼吸空间；委托和持仓没有表头，
                # 用稍大的空隙作为两块数据的唯一分隔。
                间距 = 6 if 名称 == "order" else 3
                下一自动_y = 目标位置.y() + 部件.height() + 间距
            部件.move(目标位置)

            最大右边 = max(最大右边, 部件.x() + 部件.width())
            最大下边 = max(最大下边, 部件.y() + 部件.height())

        新尺寸 = QtCore.QSize(最大右边, 最大下边)
        self._布局尺寸 = 新尺寸
        self.resize(新尺寸)
        self.updateGeometry()

    def sizeHint(self):
        return QtCore.QSize(self._布局尺寸)

    def minimumSizeHint(self):
        return QtCore.QSize(self._布局尺寸)

    @staticmethod
    def _合约文本(记录: dict) -> str:
        return str(_读取字段(
            记录, "symbol", "instrument_id", "代码", "合约", "合约代码", 默认="—"
        ))

    @classmethod
    def _合约简写(cls, 记录: dict) -> str:
        """行内只显示合约部分，减少透明悬浮牌的横向占用。

        账户快照仍保留完整 ``EXCHANGE.instrument`` 用于行情匹配；
        这里只将界面文本压缩为 ``instrument``。
        """

        完整代码 = cls._合约文本(记录)
        if "." not in 完整代码:
            return 完整代码
        return 完整代码.split(".", 1)[1] or 完整代码

    @staticmethod
    def _来源文本(来源) -> str:
        if isinstance(来源, (list, tuple, set)):
            原始项 = [str(项) for 项 in 来源]
        else:
            原始文本 = str(来源 or "").replace("，", ",").replace("/", ",")
            原始项 = [项.strip() for 项 in 原始文本.split(",") if 项.strip()]

        映射 = {
            "position": "持", "positions": "持", "持仓": "持", "持": "持",
            "order": "委", "orders": "委", "委托": "委", "挂单": "委", "委": "委",
        }
        结果 = []
        for 项 in 原始项:
            显示 = 映射.get(项.lower(), 映射.get(项, 项))
            if 显示 not in 结果:
                结果.append(显示)
        return "/".join(结果) if 结果 else "—"

    @staticmethod
    def _方向文本(方向) -> str:
        文本 = str(方向 or "").strip()
        return {
            "LONG": "多", "long": "多", "BUY": "多", "buy": "多", "多头": "多",
            "SHORT": "空", "short": "空", "SELL": "空", "sell": "空", "空头": "空",
        }.get(文本, 文本 or "—")

    @staticmethod
    def _委托动作文本(记录: dict) -> str:
        已组合 = _读取字段(记录, "action", "动作", "买卖开平")
        if 已组合:
            return str(已组合)

        买卖原文 = str(_读取字段(记录, "side", "direction", "买卖", "方向", 默认="")).strip()
        开平原文 = str(_读取字段(记录, "offset", "开平", 默认="")).strip()
        买卖 = {
            "BUY": "买", "buy": "买", "B": "买", "买入": "买",
            "SELL": "卖", "sell": "卖", "S": "卖", "卖出": "卖",
        }.get(买卖原文, 买卖原文)
        开平 = {
            "OPEN": "开", "open": "开", "开仓": "开",
            "CLOSE": "平", "close": "平", "平仓": "平",
            "CLOSETODAY": "平今", "closetoday": "平今",
            "CLOSEHISTORY": "平昨", "closehistory": "平昨",
        }.get(开平原文, 开平原文)
        return f"{买卖}{开平}" or "—"

    @staticmethod
    def _脱敏账号(账号) -> str:
        文本 = str(账号 or "").strip()
        if not 文本:
            return ""
        if "*" in 文本:
            return 文本
        if len(文本) <= 4:
            return "***"
        return f"{文本[0]}***{文本[-3:]}"

    def _状态文本与颜色(self):
        状态 = self._账户状态
        if isinstance(状态, str):
            状态文字 = 状态.strip() or "等待连接"
            已连接 = any(词 in 状态文字 for 词 in ("已连接", "在线", "正常"))
            已断开 = any(词 in 状态文字 for 词 in ("断开", "失败", "错误", "过期"))
            颜色 = "#66E08A" if 已连接 else ("#FF7070" if 已断开 else "#F6C85F")
            return 状态文字, 颜色, 状态文字

        记录 = 状态 if isinstance(状态, dict) else {}
        模式 = str(_读取字段(记录, "mode", "account_mode", "模式", "账户类型", 默认="实盘"))
        连接值 = _读取字段(记录, "connected", "online", "is_connected", "已连接")
        状态代码 = str(_读取字段(记录, "state", "状态代码", 默认="")).lower()
        if 连接值 is None and 状态代码:
            if 状态代码 == "connected":
                连接值 = True
            elif 状态代码 in {"error", "stopped", "disconnected"}:
                连接值 = False
        状态文字 = _读取字段(记录, "text", "status_text", "status", "message", "状态", "说明")
        已过期 = bool(_读取字段(记录, "stale", "expired", "数据过期", 默认=False))

        if 已过期:
            简短状态 = "数据过期"
            颜色 = "#FF7070"
        elif 连接值 is True or 状态代码 == "connected":
            简短状态 = "已连接"
            颜色 = "#66E08A"
        elif 连接值 is False or 状态代码 in {"error", "stopped", "disconnected"}:
            简短状态 = "连接失败"
            颜色 = "#FF7070"
        else:
            简短状态 = "连接中"
            颜色 = "#F6C85F"

        账号 = self._脱敏账号(_读取字段(记录, "account", "account_id", "账号", "资金账号"))
        显示文本 = f"{简短状态} {账号}".rstrip()

        # 主界面只保留一行最关键的连接状态；诊断信息仍可在悬停提示中查看。
        详情 = [f"账户类型：{模式}"]
        if 状态代码:
            详情.append(f"连接状态：{状态代码}")
        if 账号:
            详情.append(f"账户：{账号}")
        经纪公司 = _读取字段(记录, "broker", "broker_id", "期货公司")
        if 经纪公司:
            详情.append(f"期货公司：{经纪公司}")
        if 状态文字:
            详情.append(f"信息：{状态文字}")
        更新时间 = _读取字段(记录, "updated_at", "last_update", "更新时间")
        if 更新时间:
            详情.append(f"更新时间：{更新时间}")
        return 显示文本, 颜色, "\n".join(详情)

    def _行情索引(self):
        """按合约建立当前快照行情索引，供持仓和委托逐行复用。"""

        索引 = {}
        for 记录 in self._自动行情:
            合约 = self._合约文本(记录).strip()
            if 合约 and 合约 != "—":
                索引[合约.casefold()] = 记录
        return 索引

    def _当前价文本(self, 记录: dict, 行情索引: dict) -> str:
        行情 = 行情索引.get(self._合约文本(记录).strip().casefold(), {})
        # 只认账户线程在 quotes 中提交的同合约行情。这样没有收到首笔行情时
        # 一定显示“现—”，不会误用持仓/委托实体里可能滞后的同名字段。
        价格 = _读取字段(行情, "last_price", "price", "value", "最新价", "现价")
        小数位 = _读取字段(行情, "price_decs", "price_decimals", "小数位")
        return _格式化数值(价格, 小数位=小数位)

    def _生成持仓行(self, 行情索引):
        行 = []
        展开记录 = []
        for 原记录 in self._持仓:
            已展开 = False
            for 方向, 字段 in (("LONG", "long"), ("SHORT", "short")):
                分侧 = 原记录.get(字段)
                if not isinstance(分侧, dict):
                    continue
                手数 = _有效数字(_读取字段(分侧, "volume", "手数", 默认=0)) or 0
                if 手数 <= 0:
                    continue
                记录 = dict(原记录)
                记录.update(分侧)
                记录["direction"] = 方向
                展开记录.append(记录)
                已展开 = True
            if not 已展开:
                展开记录.append(原记录)

        for 记录 in 展开记录:
            方向 = self._方向文本(_读取字段(记录, "direction", "side", "pos_side", "方向", "多空"))
            手数 = _读取字段(记录, "volume", "qty", "position", "手数", "持仓", "持仓手数")
            均价 = _读取字段(
                记录, "open_price", "avg_open_price", "entry_price", "开仓均价", "均价"
            )
            盈亏 = _读取字段(
                记录, "float_profit", "floating_profit", "浮动盈亏"
            )
            最新价 = self._当前价文本(记录, 行情索引)
            盈亏数字 = _有效数字(盈亏)
            if 盈亏数字 is None:
                盈亏颜色 = "#E8EAED"
            elif 盈亏数字 > 0:
                盈亏颜色 = "#FF7070"
            elif 盈亏数字 < 0:
                盈亏颜色 = "#66D9EF"
            else:
                盈亏颜色 = "#E8EAED"
            行.append((
                f"{self._合约简写(记录)} {方向}{_格式化数值(手数)}",
                f"开{_格式化数值(均价)}",
                f"现{最新价}",
                (f"浮{_格式化数值(盈亏, 千分位=True, 正负号=True)}", 盈亏颜色),
            ))
        return 行

    def _生成委托行(self, 行情索引):
        行 = []
        for 记录 in self._委托:
            余量 = _读取字段(
                记录, "volume_left", "remaining", "left", "余量", "剩余", "剩余手数"
            )
            原量 = _读取字段(
                记录, "volume_orign", "volume_origin", "volume_original", "original_volume",
                "volume", "原量", "原始手数", "委托手数"
            )
            委托价 = _读取字段(记录, "limit_price", "price", "委托价")
            价格类型 = str(_读取字段(记录, "price_type", "价格类型", 默认="")).upper()
            委托价文本 = "市价" if 委托价 is None and 价格类型 in {"ANY", "MARKET"} else _格式化数值(委托价)
            行.append((
                f"{self._合约简写(记录)} {self._委托动作文本(记录)}",
                f"余{_格式化数值(余量)}/{_格式化数值(原量)}",
                f"委{委托价文本}",
                f"现{self._当前价文本(记录, 行情索引)}",
            ))
        return 行

    def _刷新界面(self):
        # 子表格和可见性在禁用绘制期间一次性提交。即使调用端仍使用三个旧的
        # 分项更新接口，屏幕上也只会看到更新前或更新后的完整一帧。
        self.setUpdatesEnabled(False)
        try:
            状态文本, 状态颜色, 状态详情 = self._状态文本与颜色()
            self.账户状态标签.setText(状态文本)
            self.账户状态标签.setStyleSheet(f"color:{状态颜色}; background:transparent;")
            self.账户状态标签.setToolTip(状态详情)

            行情索引 = self._行情索引()
            委托行 = self._生成委托行(行情索引)
            持仓行 = self._生成持仓行(行情索引)
            self.持仓区.更新内容(
                "", (), 持仓行, "暂无持仓"
            )
            self.委托区.更新内容(
                "", (), 委托行, "暂无委托"
            )

            if self._显示设置已指定:
                应显示面板 = self._显示持仓监控 or self._显示委托监控
            else:
                应显示面板 = (
                    self._显示持仓监控 or self._显示委托监控 or
                    self._收到状态
                )
            self.账户状态标签.setVisible(应显示面板)
            self.自动行情区.hide()
            self.持仓区.setVisible(应显示面板 and self._显示持仓监控)
            self.委托区.setVisible(应显示面板 and self._显示委托监控)
            self.setVisible(应显示面板)
            self._重排模块()
        finally:
            self.setUpdatesEnabled(True)
            self.update()
        self.内容尺寸变更.emit()

    def 设置监控显示(self, 持仓: bool | None = None, 委托: bool | None = None):
        """显式控制两个设置开关；关闭二者时整个账户区隐藏。"""

        已变化 = False
        if 持仓 is not None:
            新值 = bool(持仓)
            已变化 = 已变化 or 新值 != self._显示持仓监控 or not self._显示设置已指定
            self._显示持仓监控 = 新值
            self._显示设置已指定 = True
        if 委托 is not None:
            新值 = bool(委托)
            已变化 = 已变化 or 新值 != self._显示委托监控 or not self._显示设置已指定
            self._显示委托监控 = 新值
            self._显示设置已指定 = True
        if 已变化:
            self._刷新界面()

    def 更新账户状态(self, 状态: dict | str | None):
        if 状态 == self._账户状态 and self._收到状态 == (状态 is not None):
            return
        self._账户状态 = 状态
        self._收到状态 = 状态 is not None
        self._刷新界面()

    def 更新自动行情(self, 行情列表):
        新行情 = _标准化记录列表(行情列表, "last_price")
        if 新行情 == self._自动行情:
            return
        self._自动行情 = 新行情
        self._刷新界面()

    def 更新持仓(self, 持仓列表):
        新持仓 = _标准化记录列表(持仓列表)
        显示设置会变化 = not self._显示设置已指定 and self._显示持仓监控 != (持仓列表 is not None)
        if 新持仓 == self._持仓 and not 显示设置会变化:
            return
        self._持仓 = 新持仓
        if not self._显示设置已指定:
            self._显示持仓监控 = 持仓列表 is not None
        self._刷新界面()

    def 更新委托(self, 委托列表):
        新委托 = _标准化记录列表(委托列表)
        显示设置会变化 = not self._显示设置已指定 and self._显示委托监控 != (委托列表 is not None)
        if 新委托 == self._委托 and not 显示设置会变化:
            return
        self._委托 = 新委托
        if not self._显示设置已指定:
            self._显示委托监控 = 委托列表 is not None
        self._刷新界面()

    def 更新账户快照(self, 快照: dict):
        """原子替换持仓、未成委托和合约行情，仅触发一次界面与尺寸更新。"""

        if not isinstance(快照, dict):
            return
        新持仓 = _标准化记录列表(快照.get("positions"))
        新委托 = _标准化记录列表(快照.get("orders"))
        新行情 = _标准化记录列表(快照.get("quotes"), "last_price")
        if (
            新持仓 == self._持仓 and
            新委托 == self._委托 and
            新行情 == self._自动行情
        ):
            return
        self._持仓 = 新持仓
        self._委托 = 新委托
        self._自动行情 = 新行情
        if not self._显示设置已指定:
            self._显示持仓监控 = "positions" in 快照
            self._显示委托监控 = "orders" in 快照
        self._刷新界面()


class 悬浮牌窗口(QtWidgets.QWidget):
    设置请求 = QtCore.Signal()

    def __init__(self, 父=None):
        super().__init__(父)
        self.当前价格文本 = "…"
        self._显示自定义行情 = True
        self.已锁定 = state.默认锁定
        self._拖动中 = False
        self._拖动起点 = QtCore.QPoint()
        self._窗口起点 = QtCore.QPoint()

        self._初始化窗口标志()
        self._初始化界面()
        self._恢复或放到底部右侧()

    def _初始化窗口标志(self):
        标志 = (
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.Tool
        )
        self.setWindowFlags(标志)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)

    def _初始化界面(self):
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        self.小字标签 = QtWidgets.QLabel(state.生效小字(), self)
        self.小字标签.setStyleSheet(
            f"color: {state.配置['subtitle_font_color']}; background: transparent;"
        )
        小字字体 = QtGui.QFont(state.默认字体族, state.配置["subtitle_font_size"])
        小字字体.setBold(True)
        self.小字标签.setFont(小字字体)

        self.锁按钮 = QtWidgets.QToolButton(self)
        self.锁按钮.setText("🔒" if self.已锁定 else "🔓")
        self.锁按钮.setCursor(QtCore.Qt.PointingHandCursor)
        self.锁按钮.setStyleSheet(self._按钮样式())
        self.锁按钮.clicked.connect(self.切换锁定)
        self._锁按钮透明效果 = QtWidgets.QGraphicsOpacityEffect()
        self._锁按钮透明效果.setOpacity(0.25)
        self.锁按钮.setGraphicsEffect(self._锁按钮透明效果)
        self.锁按钮.installEventFilter(self)

        self.编辑按钮 = QtWidgets.QToolButton(self)
        self.编辑按钮.setText("✏️")
        self.编辑按钮.setCursor(QtCore.Qt.PointingHandCursor)
        self.编辑按钮.setStyleSheet(self._按钮样式())
        self.编辑按钮.clicked.connect(self.设置请求)
        self._编辑按钮透明效果 = QtWidgets.QGraphicsOpacityEffect()
        self._编辑按钮透明效果.setOpacity(0.25)
        self.编辑按钮.setGraphicsEffect(self._编辑按钮透明效果)
        self.编辑按钮.installEventFilter(self)

        self.价格标签 = QtWidgets.QLabel(self)
        self.价格标签.setText(self.当前价格文本)
        self.价格标签.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.价格标签.setStyleSheet(
            f"color: {state.配置['badge_font_color']}; background: transparent;"
        )
        价格字体 = QtGui.QFont(state.默认字体族, state.配置["badge_font_size"])
        价格字体.setBold(True)
        self.价格标签.setFont(价格字体)
        self.小字标签.setVisible(self._显示自定义行情)
        self.价格标签.setVisible(self._显示自定义行情)

        self.账户监控面板 = 账户监控面板(self)
        self._账户面板位置 = self._读取账户面板位置(state.配置)
        self.账户监控面板.内容尺寸变更.connect(self._应用组件位置)

        self._应用组件位置()

    def _按钮样式(self) -> str:
        return """
            QToolButton {
                color: #EEEEEE;
                background-color: rgba(34,34,34,220);
                border: 0px;
                padding: 0 4px;
            }
            QToolButton:hover {
                background-color: rgba(51,51,51,220);
            }
        """

    def _读取组件位置(self) -> dict[str, QtCore.QPoint]:
        return state.读取组件位置配置()

    @staticmethod
    def _读取账户面板位置(配置: dict) -> QtCore.QPoint | None:
        记录 = 配置.get("account_panel_pos") if isinstance(配置, dict) else None
        if not isinstance(记录, dict) or "x" not in 记录 or "y" not in 记录:
            return None
        try:
            return QtCore.QPoint(max(0, int(记录["x"])), max(0, int(记录["y"])))
        except (TypeError, ValueError, OverflowError):
            return None

    def _保存组件位置(self, 位置: dict[str, QtCore.QPoint]):
        state.配置["badge_subtitle_pos"] = {"x": int(位置["subtitle"].x()), "y": int(位置["subtitle"].y())}
        state.配置["badge_lock_pos"] = {"x": int(位置["lock"].x()), "y": int(位置["lock"].y())}
        state.配置["badge_edit_pos"] = {"x": int(位置["edit"].x()), "y": int(位置["edit"].y())}
        state.配置["badge_price_pos"] = {"x": int(位置["price"].x()), "y": int(位置["price"].y())}
        state.保存配置()

    def _应用组件位置(self, 覆盖: dict[str, QtCore.QPoint] | None = None):
        位置 = self._读取组件位置()
        if 覆盖:
            位置.update(覆盖)

        # 显示开关是窗口的持久状态；价格文本和样式更新都只能改内容，不能把
        # 已关闭的自定义行情标签意外重新显示出来。
        self.小字标签.setVisible(self._显示自定义行情)
        self.价格标签.setVisible(self._显示自定义行情)

        self.小字标签.adjustSize()
        self.锁按钮.adjustSize()
        self.编辑按钮.adjustSize()
        self.价格标签.adjustSize()

        self.小字标签.move(位置["subtitle"])
        self.锁按钮.move(位置["lock"])
        self.编辑按钮.move(位置["edit"])
        self.价格标签.move(位置["price"])

        可见基础组件 = [self.锁按钮, self.编辑按钮]
        if self._显示自定义行情:
            可见基础组件.extend((self.小字标签, self.价格标签))
        基础宽度 = max(部件.x() + 部件.width() for 部件 in 可见基础组件) + 6
        基础高度 = max(部件.y() + 部件.height() for 部件 in 可见基础组件) + 6

        宽度 = 基础宽度
        高度 = 基础高度
        # isVisible() 在父窗口尚未 show 时恒为 False；这里读取部件自身隐藏状态。
        # 账户面板不再被 setFixedSize 锁死，而是按已经原子排好的三个模块自然
        # 尺寸调整，避免布局刚收到新标签时只测得标题高度并长期裁切正文。
        if not self.账户监控面板.isHidden():
            self.账户监控面板._重排模块()
            面板大小 = self.账户监控面板.sizeHint().expandedTo(
                self.账户监控面板.minimumSizeHint()
            )
            self.账户监控面板.resize(面板大小)
            面板位置 = self._账户面板位置
            if 面板位置 is None:
                面板位置 = QtCore.QPoint(6, 基础高度 + 2)
            self.账户监控面板.move(面板位置)
            宽度 = max(基础宽度, 面板位置.x() + 面板大小.width() + 6)
            高度 = max(基础高度, 面板位置.y() + 面板大小.height() + 6)

        self.setFixedSize(宽度, 高度)
        if self.isVisible():
            self.move(state.计算安全坐标(self.pos(), self.size()))

    def eventFilter(self, obj, event):
        if obj in (self.锁按钮, self.编辑按钮):
            透明效果 = obj.graphicsEffect()
            if event.type() in (QtCore.QEvent.Enter, QtCore.QEvent.FocusIn):
                if 透明效果:
                    透明效果.setOpacity(1.0)
            elif event.type() in (QtCore.QEvent.Leave, QtCore.QEvent.FocusOut):
                if 透明效果:
                    透明效果.setOpacity(0.25)
        return super().eventFilter(obj, event)

    def _放到底部右侧(self):
        self.adjustSize()
        屏幕 = QtGui.QGuiApplication.primaryScreen()
        if 屏幕 is None:
            self.move(12, 40)
            self._保存位置()
            return
        可用区域 = 屏幕.availableGeometry()
        x = 可用区域.right() - self.width() - 12
        y = 可用区域.bottom() - self.height() - 40
        self.move(x, y)
        self._保存位置()

    def _恢复或放到底部右侧(self):
        self.adjustSize()
        记录 = state.配置.get("badge_pos") or {}
        if "x" in 记录 and "y" in 记录:
            目标 = QtCore.QPoint(int(记录["x"]), int(记录["y"]))
            安全点 = state.计算安全坐标(目标, self.size())
            self.move(安全点)
        else:
            self._放到底部右侧()

    def 更新价格文本(self, 文本: str):
        self.当前价格文本 = 文本
        self.价格标签.setText(文本)
        self._应用组件位置()

    def 设置自定义行情显示(self, 显示: bool):
        """显示或隐藏唯一一条手工行情，并保持账户监控和两个按钮可用。"""

        新值 = bool(显示)
        if 新值 == self._显示自定义行情:
            # 即使值未变也重新落实可见性，防止外部样式预览改动了子部件状态。
            self._应用组件位置()
            return
        self._显示自定义行情 = 新值
        self._应用组件位置()

    def 设置账户监控显示(self, 持仓: bool | None = None, 委托: bool | None = None):
        self.账户监控面板.设置监控显示(持仓=持仓, 委托=委托)

    def 更新账户状态(self, 状态: dict | str | None):
        self.账户监控面板.更新账户状态(状态)

    def 更新自动行情(self, 行情列表):
        self.账户监控面板.更新自动行情(行情列表)

    def 更新持仓(self, 持仓列表):
        self.账户监控面板.更新持仓(持仓列表)

    def 更新委托(self, 委托列表):
        self.账户监控面板.更新委托(委托列表)

    def 更新账户快照(self, 快照: dict):
        """原子更新账户快照；供账户线程的完整快照信号直接调用。"""

        self.账户监控面板.更新账户快照(快照)

    def 应用账户面板设置(self, 配置: dict | None = None):
        """应用账户模块字号/位置以及账户面板整体位置并立即重排。

        调用端可传一份尚未持久化的预览配置；省略时读取 ``state.配置``。
        """

        生效配置 = state.配置 if 配置 is None else 配置
        self.账户监控面板.应用账户设置(生效配置, 发出尺寸信号=False)
        self._账户面板位置 = self._读取账户面板位置(生效配置)
        self._应用组件位置()

    def 切换锁定(self):
        self.已锁定 = not self.已锁定
        self.锁按钮.setText("🔒" if self.已锁定 else "🔓")

    def 应用样式(self, 字号=None, 颜色=None, 小字=None, 小字字号=None, 小字颜色=None):
        if 字号 is not None:
            字体 = self.价格标签.font()
            字体.setPointSize(字号)
            self.价格标签.setFont(字体)
        if 颜色 is not None:
            self.价格标签.setStyleSheet(f"color: {颜色}; background: transparent;")
        if 小字字号 is not None:
            字体 = self.小字标签.font()
            字体.setPointSize(小字字号)
            self.小字标签.setFont(字体)
        if 小字颜色 is not None:
            self.小字标签.setStyleSheet(f"color: {小字颜色}; background: transparent;")
        if 小字 is not None:
            self.小字标签.setText(小字)
        self._应用组件位置()

    def mousePressEvent(self, 事件):
        if 事件.button() == QtCore.Qt.LeftButton and not self.已锁定:
            self._拖动中 = True
            self._拖动起点 = 事件.globalPosition().toPoint()
            self._窗口起点 = self.frameGeometry().topLeft()
        super().mousePressEvent(事件)

    def mouseMoveEvent(self, 事件):
        if self._拖动中 and not self.已锁定:
            当前 = 事件.globalPosition().toPoint()
            位移 = 当前 - self._拖动起点
            self._移动到安全位置(self._窗口起点 + 位移)
        super().mouseMoveEvent(事件)

    def mouseReleaseEvent(self, 事件):
        if self._拖动中 and not self.已锁定:
            self._保存位置()
        self._拖动中 = False
        super().mouseReleaseEvent(事件)

    def mouseDoubleClickEvent(self, 事件):
        if 事件.button() == QtCore.Qt.LeftButton:
            self.hide()
        super().mouseDoubleClickEvent(事件)

    def _移动到安全位置(self, 目标点: QtCore.QPoint):
        self.move(state.计算安全坐标(目标点, self.size()))

    def _保存位置(self):
        state.配置["badge_pos"] = {"x": int(self.x()), "y": int(self.y())}
        state.保存配置()

    def 更新组件位置(self, 位置: dict[str, QtCore.QPoint]):
        self._保存组件位置(位置)
        self._应用组件位置(位置)


class 悬浮牌预览(QtWidgets.QFrame):
    位置变更 = QtCore.Signal(dict)

    def __init__(self, 父=None):
        super().__init__(父)
        self.setFixedSize(320, 220)
        self.setStyleSheet("background-color:#202020; border:1px solid #444;")
        self.setMouseTracking(True)

        self._拖拽目标 = None
        self._拖拽偏移 = QtCore.QPoint()

        self.小字标签 = QtWidgets.QLabel(state.生效小字(), self)
        备注字体 = QtGui.QFont(state.默认字体族, state.配置.get("subtitle_font_size", 14))
        备注字体.setBold(True)
        self.小字标签.setFont(备注字体)
        self.小字标签.setStyleSheet(
            f"color:{state.配置.get('subtitle_font_color', '#9AA0A6')}; background: transparent;"
        )

        self.锁按钮 = QtWidgets.QToolButton(self)
        self.锁按钮.setText("🔒")
        self.锁按钮.setStyleSheet("color:#ccc; background:transparent; border:0;")

        self.编辑按钮 = QtWidgets.QToolButton(self)
        self.编辑按钮.setText("✏️")
        self.编辑按钮.setStyleSheet("color:#ccc; background:transparent; border:0;")

        self.价格标签 = QtWidgets.QLabel("12345.6", self)
        价格字体 = QtGui.QFont(state.默认字体族, state.配置.get("badge_font_size", 56))
        价格字体.setBold(True)
        self.价格标签.setFont(价格字体)
        self.价格标签.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.价格标签.setStyleSheet(
            f"color:{state.配置.get('badge_font_color', '#A6E22E')}; background: transparent;"
        )

        for 部件 in (self.锁按钮, self.编辑按钮, self.小字标签, self.价格标签):
            部件.installEventFilter(self)

        self._应用位置(state.读取组件位置配置())

    def _边界内(self, 位置: QtCore.QPoint, 部件: QtWidgets.QWidget) -> QtCore.QPoint:
        x = max(0, min(位置.x(), self.width() - 部件.width()))
        y = max(0, min(位置.y(), self.height() - 部件.height()))
        return QtCore.QPoint(x, y)

    def _应用位置(self, 位置: dict[str, QtCore.QPoint]):
        self.小字标签.adjustSize()
        self.锁按钮.adjustSize()
        self.编辑按钮.adjustSize()
        self.价格标签.adjustSize()

        self.小字标签.move(self._边界内(位置["subtitle"], self.小字标签))
        self.锁按钮.move(self._边界内(位置["lock"], self.锁按钮))
        self.编辑按钮.move(self._边界内(位置["edit"], self.编辑按钮))
        self.价格标签.move(self._边界内(位置["price"], self.价格标签))

    def 更新文本(self, 小字: str, 价格文本: str):
        self.小字标签.setText(小字)
        self.价格标签.setText(价格文本)
        self._应用位置(self.获取组件位置())

    def 更新样式(self, 价格字号: int, 价格颜色: str, 备注字号: int, 备注颜色: str):
        字体 = self.价格标签.font()
        字体.setPointSize(价格字号)
        self.价格标签.setFont(字体)
        self.价格标签.setStyleSheet(f"color:{价格颜色}; background: transparent;")

        备注字体 = self.小字标签.font()
        备注字体.setPointSize(备注字号)
        self.小字标签.setFont(备注字体)
        self.小字标签.setStyleSheet(f"color:{备注颜色}; background: transparent;")
        self._应用位置(self.获取组件位置())

    def 获取组件位置(self):
        return {
            "subtitle": self.小字标签.pos(),
            "lock": self.锁按钮.pos(),
            "edit": self.编辑按钮.pos(),
            "price": self.价格标签.pos(),
        }

    def 应用外部位置(self, 位置: dict[str, QtCore.QPoint]):
        self._应用位置(位置)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
            映射 = {
                self.小字标签: "subtitle",
                self.锁按钮: "lock",
                self.编辑按钮: "edit",
                self.价格标签: "price",
            }
            if obj in 映射:
                self._拖拽目标 = 映射[obj]
                self._拖拽偏移 = event.position().toPoint()
                return True

        if event.type() == QtCore.QEvent.MouseMove and self._拖拽目标:
            当前点 = obj.mapToParent(event.position().toPoint()) - self._拖拽偏移
            if self._拖拽目标 == "subtitle":
                安全点 = self._边界内(当前点, self.小字标签)
                self.小字标签.move(安全点)
            elif self._拖拽目标 == "lock":
                安全点 = self._边界内(当前点, self.锁按钮)
                self.锁按钮.move(安全点)
            elif self._拖拽目标 == "edit":
                安全点 = self._边界内(当前点, self.编辑按钮)
                self.编辑按钮.move(安全点)
            elif self._拖拽目标 == "price":
                安全点 = self._边界内(当前点, self.价格标签)
                self.价格标签.move(安全点)
            self.位置变更.emit(self.获取组件位置())
            return True

        if event.type() == QtCore.QEvent.MouseButtonRelease and self._拖拽目标:
            self.位置变更.emit(self.获取组件位置())
            self._拖拽目标 = None
            return True

        return super().eventFilter(obj, event)
