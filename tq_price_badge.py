# -*- coding: utf-8 -*-
# 透明悬浮牌 + 托盘 + TqApi
import json
import math
import os
import re
import sys

from PySide6 import QtWidgets, QtGui, QtCore
from tqsdk import TqApi, TqAuth

# ======= 从环境变量中读取天勤登录信息=======
TQ_USER = os.environ.get("TQ_USER")
TQ_PASS = os.environ.get("TQ_PASS")
if not TQ_USER or not TQ_PASS:
    raise RuntimeError("请先在环境变量中设置 TQ_USER / TQ_PASS")
# ======= 基本配置=========
# 兼容新版本 TqSdk: 默认使用主连合约，避免历史到期合约长时间无最新价
合约代码 = sys.argv[1] if len(sys.argv) > 1 else "KQ.m@SHFE.cu"
标题前缀 = "期货最新价"
当价格为空也更新 = True  # 对应 UPDATE_WHEN_NONE

# 悬浮牌默认外观
默认字体族 = "Microsoft YaHei"  # 中文系统基本都有；找不到时 Qt 会自动回退
配置路径 = os.path.join(os.path.expanduser("~"), ".tq_price_tray.json")
默认配置 = {
    "badge_font_size": 56,          # 价格字号
    "badge_font_color": "#A6E22E",  # 柔和荧光绿，避免纯 #00FF00
    "subtitle_font_size": 14,       # 备注字号
    "subtitle_font_color": "#9AA0A6",  # 备注颜色
    "badge_subtitle": "",           # 上方小字：空=跟随合约代码
    "badge_subtitle_pos": None,     # 备注文本位置
    "badge_lock_pos": None,         # 锁定按钮位置
    "badge_edit_pos": None,         # 编辑按钮位置
    "badge_price_pos": None,        # 价格组件位置
    "badge_pos": None,              # 悬浮牌位置（持久化存储）
    "settings_pos": None,           # 设置窗口位置（持久化存储）
    "recent_symbols": []            # 最近切换过的合约（用于补全）
}
配置 = 默认配置.copy()
显示大号价格默认 = True
默认锁定 = False
# ================================


def 读取配置():
    global 配置
    try:
        if os.path.exists(配置路径):
            with open(配置路径, "r", encoding="utf-8") as f:
                数据 = json.load(f)
            for 键 in 默认配置:
                if 键 in 数据:
                    配置[键] = 数据[键]
    except Exception as e:
        print("读取配置失败:", e)


def 保存配置():
    try:
        with open(配置路径, "w", encoding="utf-8") as f:
            json.dump(配置, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("保存配置失败:", e)


def 生效小字():
    文本 = (配置.get("badge_subtitle") or "").strip()
    return 文本 if 文本 else 合约代码


合约代码正则 = re.compile(r"^(?:KQ\.(?:m|i)@[A-Z]+\.[A-Z0-9]+|[A-Z]+\.[A-Z0-9]+)$")


def 规范化合约代码(原始: str) -> str:
    return (原始 or "").strip().upper()


def 合约代码合法(代码: str) -> bool:
    return bool(合约代码正则.fullmatch(代码))


def 写入最近合约(代码: str):
    代码 = 规范化合约代码(代码)
    if not 代码:
        return
    历史 = [规范化合约代码(x) for x in 配置.get("recent_symbols", []) if str(x).strip()]
    新历史 = [代码] + [x for x in 历史 if x != 代码]
    配置["recent_symbols"] = 新历史[:30]


def 格式化价格(p):
    if p is None:
        return "—"
    s = f"{p:.2f}".rstrip("0").rstrip(".")
    if len(s) > 6:
        try:
            s_int = str(int(round(p)))
            if len(s_int) <= 6:
                return s_int
            return s[:6]
        except Exception:
            return s[:6]
    return s


def 读取最新价(quote):
    """兼容不同版本/对象形态的 quote 读取方式。"""

    价格 = None
    try:
        价格 = quote["last_price"]
    except Exception:
        价格 = getattr(quote, "last_price", None)

    if isinstance(价格, float) and math.isnan(价格):
        return None
    return 价格


def _点_from_config(记录: dict | None, 默认点: QtCore.QPoint) -> QtCore.QPoint:
    记录 = 记录 or {}
    return QtCore.QPoint(int(记录.get("x", 默认点.x())), int(记录.get("y", 默认点.y())))


def 读取组件位置配置() -> dict[str, QtCore.QPoint]:
    """读取备注、按钮、价格的相对坐标，落在默认值上。"""

    备注默认 = QtCore.QPoint(6, 2)
    锁定默认 = QtCore.QPoint(备注默认.x() + 120, 备注默认.y())
    编辑默认 = QtCore.QPoint(锁定默认.x() + 28, 锁定默认.y())
    价格默认 = QtCore.QPoint(6, 28)

    # 兼容老配置：如果旧的 badge_header_pos 存在，则把备注文本放在那里
    旧头部 = 配置.get("badge_header_pos") or {}
    if 旧头部:
        备注默认 = QtCore.QPoint(int(旧头部.get("x", 备注默认.x())), int(旧头部.get("y", 备注默认.y())))
        锁定默认 = QtCore.QPoint(备注默认.x() + 120, 备注默认.y())
        编辑默认 = QtCore.QPoint(锁定默认.x() + 28, 锁定默认.y())

    return {
        "subtitle": _点_from_config(配置.get("badge_subtitle_pos"), 备注默认),
        "lock": _点_from_config(配置.get("badge_lock_pos"), 锁定默认),
        "edit": _点_from_config(配置.get("badge_edit_pos"), 编辑默认),
        "price": _点_from_config(配置.get("badge_price_pos"), 价格默认),
    }


def 计算安全坐标(目标点: QtCore.QPoint, 窗口大小: QtCore.QSize) -> QtCore.QPoint:
    """
    在多屏、高分辨率环境下，确保窗口位置落在可见区域。

    :param 目标点: 期望的左上角坐标（逻辑坐标系）。
    :param 窗口大小: 窗口大小，通常使用 self.size()。
    """

    屏幕 = QtGui.QGuiApplication.screenAt(目标点)
    if 屏幕 is None:
        屏幕 = QtGui.QGuiApplication.primaryScreen()
    if 屏幕 is None:
        # 理论不会发生，但仍返回原位置以避免崩溃
        return 目标点

    可用 = 屏幕.availableGeometry()
    最大偏移_x = max(0, 可用.width() - 窗口大小.width())
    最大偏移_y = max(0, 可用.height() - 窗口大小.height())
    x = min(max(目标点.x(), 可用.left()), 可用.left() + 最大偏移_x)
    y = min(max(目标点.y(), 可用.top()), 可用.top() + 最大偏移_y)
    return QtCore.QPoint(x, y)


class 行情线程(QtCore.QThread):
    价格信号 = QtCore.Signal(object)  # 文本
    错误信号 = QtCore.Signal(str)

    def __init__(self, 合约, 用户, 密码, 父=None):
        super().__init__(父)
        self.合约 = 合约
        self.用户 = 用户
        self.密码 = 密码
        self._停止 = False

    def 停止(self):
        self._停止 = True

    def run(self):
        api = None
        try:
            api = TqApi(auth=TqAuth(self.用户, self.密码))
            quote = api.get_quote(self.合约)
            上次文本 = None
            连续无价格次数 = 0
            while not self._停止:
                api.wait_update()
                价格 = 读取最新价(quote)
                if 价格 is None and not 当价格为空也更新:
                    continue
                if 价格 is None:
                    连续无价格次数 += 1
                    if 连续无价格次数 == 200:
                        self.错误信号.emit(
                            f"合约 {self.合约} 暂无最新价，请确认合约是否可交易（建议使用主连如 KQ.m@SHFE.cu）"
                        )
                else:
                    连续无价格次数 = 0
                文本 = 格式化价格(价格)
                if 文本 != 上次文本:
                    上次文本 = 文本
                    self.价格信号.emit(文本)
        except Exception as e:
            self.错误信号.emit(str(e))
        finally:
            if api is not None:
                try:
                    api.close()
                except Exception:
                    pass


class 悬浮牌窗口(QtWidgets.QWidget):
    设置请求 = QtCore.Signal()

    def __init__(self, 父=None):
        super().__init__(父)
        self.当前价格文本 = "…"
        self.已锁定 = 默认锁定
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
        # 关键：开启每像素透明背景
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)

    def _初始化界面(self):
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        # 头部：小字 + 锁按钮 + 编辑按钮
        self.小字标签 = QtWidgets.QLabel(生效小字(), self)
        self.小字标签.setStyleSheet(
            f"color: {配置['subtitle_font_color']}; background: transparent;"
        )
        小字字体 = QtGui.QFont(默认字体族, 配置["subtitle_font_size"])
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

        # 大号价格
        self.价格标签 = QtWidgets.QLabel(self)
        self.价格标签.setText(self.当前价格文本)
        self.价格标签.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.价格标签.setStyleSheet(
            f"color: {配置['badge_font_color']}; background: transparent;"
        )
        价格字体 = QtGui.QFont(默认字体族, 配置["badge_font_size"])
        价格字体.setBold(True)
        self.价格标签.setFont(价格字体)

        self._应用组件位置()

    def _按钮样式(self) -> str:
        """统一定义头部按钮的样式，避免重复 CSS。"""

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
        return 读取组件位置配置()

    def _保存组件位置(self, 位置: dict[str, QtCore.QPoint]):
        配置["badge_subtitle_pos"] = {"x": int(位置["subtitle"].x()), "y": int(位置["subtitle"].y())}
        配置["badge_lock_pos"] = {"x": int(位置["lock"].x()), "y": int(位置["lock"].y())}
        配置["badge_edit_pos"] = {"x": int(位置["edit"].x()), "y": int(位置["edit"].y())}
        配置["badge_price_pos"] = {"x": int(位置["price"].x()), "y": int(位置["price"].y())}
        保存配置()

    def _应用组件位置(self, 覆盖: dict[str, QtCore.QPoint] | None = None):
        位置 = self._读取组件位置()
        if 覆盖:
            位置.update(覆盖)

        self.小字标签.adjustSize()
        self.锁按钮.adjustSize()
        self.编辑按钮.adjustSize()
        self.价格标签.adjustSize()

        self.小字标签.move(位置["subtitle"])
        self.锁按钮.move(位置["lock"])
        self.编辑按钮.move(位置["edit"])
        self.价格标签.move(位置["price"])

        宽度 = max(
            self.小字标签.x() + self.小字标签.width(),
            self.锁按钮.x() + self.锁按钮.width(),
            self.编辑按钮.x() + self.编辑按钮.width(),
            self.价格标签.x() + self.价格标签.width()
        ) + 6
        高度 = max(
            self.小字标签.y() + self.小字标签.height(),
            self.锁按钮.y() + self.锁按钮.height(),
            self.编辑按钮.y() + self.编辑按钮.height(),
            self.价格标签.y() + self.价格标签.height()
        ) + 6
        self.setFixedSize(宽度, 高度)

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
            # 理论上不会为空，但保底避免在极端环境崩溃
            self.move(12, 40)
            self._保存位置()
            return
        可用区域 = 屏幕.availableGeometry()
        w = self.width()
        h = self.height()
        x = 可用区域.right() - w - 12
        y = 可用区域.bottom() - h - 40
        self.move(x, y)
        self._保存位置()

    def _恢复或放到底部右侧(self):
        """从配置恢复悬浮牌位置；没有记录则落到底部右侧。"""

        self.adjustSize()
        记录 = 配置.get("badge_pos") or {}
        if "x" in 记录 and "y" in 记录:
            目标 = QtCore.QPoint(int(记录["x"]), int(记录["y"]))
            安全点 = 计算安全坐标(目标, self.size())
            self.move(安全点)
        else:
            self._放到底部右侧()

    # ===== 公共接口 =====
    def 更新价格文本(self, 文本: str):
        self.当前价格文本 = 文本
        self.价格标签.setText(文本)
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
            self.价格标签.setStyleSheet(
                f"color: {颜色}; background: transparent;"
            )
        if 小字字号 is not None:
            字体 = self.小字标签.font()
            字体.setPointSize(小字字号)
            self.小字标签.setFont(字体)
        if 小字颜色 is not None:
            self.小字标签.setStyleSheet(
                f"color: {小字颜色}; background: transparent;"
            )
        if 小字 is not None:
            self.小字标签.setText(小字)
        self._应用组件位置()

    # ===== 事件：拖动、双击 =====
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
        """拖动时限制在可见范围内，避免跑到屏幕外。"""

        安全点 = 计算安全坐标(目标点, self.size())
        self.move(安全点)

    def _保存位置(self):
        """记录悬浮牌位置以便下次启动恢复。"""

        配置["badge_pos"] = {"x": int(self.x()), "y": int(self.y())}
        保存配置()

    def 更新组件位置(self, 位置: dict[str, QtCore.QPoint]):
        """从设置预览中同步内部组件的位置。"""

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

        self.小字标签 = QtWidgets.QLabel(生效小字(), self)
        备注字体 = QtGui.QFont(默认字体族, 配置.get("subtitle_font_size", 14))
        备注字体.setBold(True)
        self.小字标签.setFont(备注字体)
        self.小字标签.setStyleSheet(
            f"color:{配置.get('subtitle_font_color', '#9AA0A6')}; background: transparent;"
        )

        self.锁按钮 = QtWidgets.QToolButton(self)
        self.锁按钮.setText("🔒")
        self.锁按钮.setStyleSheet("color:#ccc; background:transparent; border:0;")

        self.编辑按钮 = QtWidgets.QToolButton(self)
        self.编辑按钮.setText("✏️")
        self.编辑按钮.setStyleSheet("color:#ccc; background:transparent; border:0;")

        self.价格标签 = QtWidgets.QLabel("12345.6", self)
        价格字体 = QtGui.QFont(默认字体族, 配置.get("badge_font_size", 56))
        价格字体.setBold(True)
        self.价格标签.setFont(价格字体)
        self.价格标签.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.价格标签.setStyleSheet(
            f"color:{配置.get('badge_font_color', '#A6E22E')}; background: transparent;"
        )

        # 让按钮、标签的鼠标事件交给父级处理，避免点击时切换选中样式，便于拖拽
        for 部件 in (self.锁按钮, self.编辑按钮, self.小字标签, self.价格标签):
            部件.installEventFilter(self)

        self._应用位置(读取组件位置配置())

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


class 设置对话框(QtWidgets.QDialog):
    合约切换请求 = QtCore.Signal(str)

    def __init__(self, 当前合约: str, 父=None):
        super().__init__(父)
        self.当前合约 = 当前合约
        self.setWindowTitle("设置 - 悬浮牌样式")
        self.setModal(True)
        self.setFixedSize(520, 560)
        self._预览组件位置 = 读取组件位置配置()
        self._初始化界面()
        self._恢复位置()

    def _初始化界面(self):
        布局 = QtWidgets.QGridLayout(self)
        行 = 0

        # 价格字号
        布局.addWidget(QtWidgets.QLabel("行情字体大小："), 行, 0, QtCore.Qt.AlignRight)
        self.字号变量 = QtWidgets.QSpinBox(self)
        self.字号变量.setRange(1, 160)
        self.字号变量.setSingleStep(2)
        self.字号变量.setValue(配置["badge_font_size"])
        self.字号变量.valueChanged.connect(self._预览)
        布局.addWidget(self.字号变量, 行, 1, QtCore.Qt.AlignLeft)
        行 += 1

        # 价格颜色
        布局.addWidget(QtWidgets.QLabel("行情字体颜色："), 行, 0, QtCore.Qt.AlignRight)
        self.颜色按钮 = QtWidgets.QPushButton(配置["badge_font_color"], self)
        self.颜色按钮.clicked.connect(self._选择颜色)
        布局.addWidget(self.颜色按钮, 行, 1, QtCore.Qt.AlignLeft)
        行 += 1

        # 备注字号
        布局.addWidget(QtWidgets.QLabel("备注字体大小："), 行, 0, QtCore.Qt.AlignRight)
        self.备注字号变量 = QtWidgets.QSpinBox(self)
        self.备注字号变量.setRange(10, 80)
        self.备注字号变量.setSingleStep(1)
        self.备注字号变量.setValue(配置["subtitle_font_size"])
        self.备注字号变量.valueChanged.connect(self._预览)
        布局.addWidget(self.备注字号变量, 行, 1, QtCore.Qt.AlignLeft)
        行 += 1

        # 备注颜色
        布局.addWidget(QtWidgets.QLabel("备注字体颜色："), 行, 0, QtCore.Qt.AlignRight)
        self.备注颜色按钮 = QtWidgets.QPushButton(配置["subtitle_font_color"], self)
        self.备注颜色按钮.clicked.connect(lambda: self._选择颜色(True))
        布局.addWidget(self.备注颜色按钮, 行, 1, QtCore.Qt.AlignLeft)
        行 += 1

        # 合约切换
        布局.addWidget(QtWidgets.QLabel("订阅合约："), 行, 0, QtCore.Qt.AlignRight)
        self.合约输入 = QtWidgets.QLineEdit(self.当前合约, self)
        self.合约输入.setPlaceholderText("示例：KQ.m@SHFE.cu / SHFE.rb2501")
        self.合约输入.editingFinished.connect(self._规范化合约输入)
        self.合约补全模型 = QtCore.QStringListModel(self)
        self.合约补全 = QtWidgets.QCompleter(self.合约补全模型, self)
        self.合约补全.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.合约补全.setFilterMode(QtCore.Qt.MatchContains)
        self.合约补全.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self.合约输入.setCompleter(self.合约补全)
        self._刷新合约补全()
        布局.addWidget(self.合约输入, 行, 1, QtCore.Qt.AlignLeft)
        self.切换合约按钮 = QtWidgets.QPushButton("切换", self)
        self.切换合约按钮.clicked.connect(self._切换合约)
        布局.addWidget(self.切换合约按钮, 行, 2, QtCore.Qt.AlignLeft)
        行 += 1

        # 小字
        布局.addWidget(QtWidgets.QLabel("价格上方小字："), 行, 0, QtCore.Qt.AlignRight)
        self.小字输入 = QtWidgets.QLineEdit(
            配置.get("badge_subtitle") or 合约代码,
            self
        )
        self.小字输入.textChanged.connect(self._预览)
        布局.addWidget(self.小字输入, 行, 1, QtCore.Qt.AlignLeft)
        提示标签 = QtWidgets.QLabel("（留空=跟随合约代码）", self)
        提示标签.setStyleSheet("color:#888888;")
        布局.addWidget(提示标签, 行, 2, QtCore.Qt.AlignLeft)
        行 += 1

        # 预览
        布局.addWidget(QtWidgets.QLabel("预览："), 行, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
        self.预览组件 = 悬浮牌预览(self)
        self.预览组件.位置变更.connect(self._更新预览位置提示)
        self.预览组件.应用外部位置(self._预览组件位置)
        布局.addWidget(self.预览组件, 行, 1, 1, 2)
        行 += 1

        # 按钮
        按钮框 = QtWidgets.QHBoxLayout()
        self.确定按钮 = QtWidgets.QPushButton("保存", self)
        self.确定按钮.setDefault(True)  # Enter 键直接触发保存
        self.确定按钮.setAutoDefault(True)
        self.取消按钮 = QtWidgets.QPushButton("取消", self)
        self.确定按钮.clicked.connect(self.accept)
        self.取消按钮.clicked.connect(self.reject)
        按钮框.addStretch(1)
        按钮框.addWidget(self.确定按钮)
        按钮框.addWidget(self.取消按钮)
        布局.addLayout(按钮框, 行, 0, 1, 3)

        self._预览()

    def _候选合约列表(self) -> list[str]:
        候选 = [
            self.当前合约,
            "KQ.m@SHFE.cu",
            "KQ.m@SHFE.rb",
            "KQ.m@DCE.i",
            "KQ.m@CZCE.SR",
            "KQ.m@CFFEX.IF",
        ]
        候选.extend(配置.get("recent_symbols", []))
        结果 = []
        for 项 in 候选:
            代码 = 规范化合约代码(str(项))
            if 代码 and 代码 not in 结果:
                结果.append(代码)
        return 结果

    def _刷新合约补全(self):
        self.合约补全模型.setStringList(self._候选合约列表())

    def _规范化合约输入(self):
        self.合约输入.setText(规范化合约代码(self.合约输入.text()))

    def _切换合约(self):
        代码 = 规范化合约代码(self.合约输入.text())
        self.合约输入.setText(代码)
        if not 合约代码合法(代码):
            QtWidgets.QMessageBox.warning(
                self,
                "合约代码无效",
                "请输入天勤可识别的代码，例如：\n"
                "- KQ.m@SHFE.cu（主连）\n"
                "- SHFE.rb2501（具体合约）"
            )
            return
        self.合约切换请求.emit(代码)
        QtWidgets.QMessageBox.information(self, "已切换", f"已切换到合约：{代码}")
        self.当前合约 = 代码
        self._刷新合约补全()

    def _选择颜色(self, 用于备注=False):
        按钮 = self.备注颜色按钮 if 用于备注 else self.颜色按钮
        初始 = QtGui.QColor(按钮.text())
        颜色 = QtWidgets.QColorDialog.getColor(
            初始, self, "选择字体颜色"
        )
        if 颜色.isValid():
            # 轻微提醒避免纯 #00FF00
            if (not 用于备注) and 颜色.name().lower() == "#00ff00":
                QtWidgets.QMessageBox.information(
                    self, "提示",
                    "纯 #00FF00 绿在透明背景上会比较刺眼，",
                    "建议用稍微偏灰一点的绿。例如 #A6E22E。"
                )
            按钮.setText(颜色.name())
            self._预览()

    def _预览(self):
        字号 = self.字号变量.value()
        颜色 = self.颜色按钮.text()
        备注字号 = self.备注字号变量.value()
        备注颜色 = self.备注颜色按钮.text()
        小字原始 = (self.小字输入.text() or "").strip()
        小字文本 = 小字原始 if 小字原始 else 合约代码
        行情文本 = getattr(self.parent(), "当前价格文本", "12345.6")

        self.预览组件.更新样式(字号, 颜色, 备注字号, 备注颜色)
        self.预览组件.更新文本(小字文本, 行情文本)
        self.预览组件.应用外部位置(self._预览组件位置)

    def _更新预览位置提示(self, 位置: dict):
        self._预览组件位置 = 位置

    def accept(self):
        # 更新全局配置
        字号 = self.字号变量.value()
        颜色 = self.颜色按钮.text()
        备注字号 = self.备注字号变量.value()
        备注颜色 = self.备注颜色按钮.text()
        小字原始 = (self.小字输入.text() or "").strip()
        位置 = self._预览组件位置
        配置["badge_font_size"] = 字号
        配置["badge_font_color"] = 颜色
        配置["subtitle_font_size"] = 备注字号
        配置["subtitle_font_color"] = 备注颜色
        配置["badge_subtitle"] = "" if (小字原始 == "" or 小字原始 == 合约代码) else 小字原始
        配置["badge_subtitle_pos"] = {"x": int(位置["subtitle"].x()), "y": int(位置["subtitle"].y())}
        配置["badge_lock_pos"] = {"x": int(位置["lock"].x()), "y": int(位置["lock"].y())}
        配置["badge_edit_pos"] = {"x": int(位置["edit"].x()), "y": int(位置["edit"].y())}
        配置["badge_price_pos"] = {"x": int(位置["price"].x()), "y": int(位置["price"].y())}
        保存配置()
        super().accept()

    def keyPressEvent(self, 事件: QtGui.QKeyEvent):
        """Enter 映射为保存关闭，其他按键保持默认行为。"""

        if 事件.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.accept()
            return
        super().keyPressEvent(事件)

    def _恢复位置(self):
        """恢复设置窗口位置，若无记录则以父窗口为中心。"""

        记录 = 配置.get("settings_pos") or {}
        if "x" in 记录 and "y" in 记录:
            目标 = QtCore.QPoint(int(记录["x"]), int(记录["y"]))
        else:
            目标 = self._默认位置()

        安全点 = 计算安全坐标(目标, self.size())
        self.move(安全点)

    def _默认位置(self) -> QtCore.QPoint:
        """优先以父级窗口为中心，否则落在主屏中央。"""

        父级 = self.parentWidget()
        if 父级:
            父矩形 = 父级.frameGeometry()
            return 父矩形.center() - QtCore.QPoint(self.width() // 2, self.height() // 2)

        屏幕 = QtGui.QGuiApplication.primaryScreen()
        if 屏幕:
            可用 = 屏幕.availableGeometry()
            return 可用.center() - QtCore.QPoint(self.width() // 2, self.height() // 2)
        return QtCore.QPoint(100, 100)

    def _保存位置(self):
        """记录设置窗口位置以适配多屏、多分辨率。"""

        配置["settings_pos"] = {"x": int(self.x()), "y": int(self.y())}
        保存配置()

    def closeEvent(self, 事件: QtGui.QCloseEvent):
        self._保存位置()
        super().closeEvent(事件)


class 主控制(QtCore.QObject):
    def __init__(self, 应用: QtWidgets.QApplication):
        super().__init__()
        self.应用 = 应用
        self.当前合约 = 规范化合约代码(合约代码)
        写入最近合约(self.当前合约)
        保存配置()
        self.悬浮牌 = 悬浮牌窗口()
        # 悬浮牌上的“编辑”按钮打开同一份设置对话框
        self.悬浮牌.设置请求.connect(self.打开设置)
        if 显示大号价格默认:
            self.悬浮牌.show()

        self.行情线程 = None
        self._启动行情线程(self.当前合约)

        self._创建托盘()

    def _创建托盘(self):
        图标 = self.应用.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
        self.托盘 = QtWidgets.QSystemTrayIcon(图标, self.应用)
        菜单 = QtWidgets.QMenu()

        self.显示动作 = 菜单.addAction(
            "隐藏大号价格" if self.悬浮牌.isVisible() else "显示大号价格"
        )
        self.锁定动作 = 菜单.addAction(
            "解锁悬浮牌" if self.悬浮牌.已锁定 else "锁定悬浮牌"
        )
        菜单.addSeparator()
        self.设置动作 = 菜单.addAction("设置")
        菜单.addSeparator()
        self.退出动作 = 菜单.addAction("退出")

        self.显示动作.triggered.connect(self.切换悬浮牌可见)
        self.锁定动作.triggered.connect(self.切换锁定)
        self.设置动作.triggered.connect(self.打开设置)
        self.退出动作.triggered.connect(self.退出)

        self.托盘.setContextMenu(菜单)
        self.托盘.setToolTip(f"{self.当前合约} {标题前缀}: …")
        self.托盘.show()

    # ==== 托盘动作 ====
    def 切换悬浮牌可见(self):
        if self.悬浮牌.isVisible():
            self.悬浮牌.hide()
            self.显示动作.setText("显示大号价格")
        else:
            self.悬浮牌.show()
            self.显示动作.setText("隐藏大号价格")

    def 切换锁定(self):
        self.悬浮牌.切换锁定()
        self.锁定动作.setText(
            "解锁悬浮牌" if self.悬浮牌.已锁定 else "锁定悬浮牌"
        )

    def 打开设置(self):
        对话 = 设置对话框(self.当前合约, self.悬浮牌)
        对话.合约切换请求.connect(self.切换合约订阅)
        if 对话.exec() == QtWidgets.QDialog.Accepted:
            # 应用到悬浮牌
            self.悬浮牌.应用样式(
                字号=配置["badge_font_size"],
                颜色=配置["badge_font_color"],
                小字=生效小字(),
                小字字号=配置["subtitle_font_size"],
                小字颜色=配置["subtitle_font_color"]
            )
            位置 = 读取组件位置配置()
            self.悬浮牌.更新组件位置(位置)

    def _启动行情线程(self, 代码: str):
        self.行情线程 = 行情线程(代码, TQ_USER, TQ_PASS)
        self.行情线程.价格信号.connect(self.处理价格更新)
        self.行情线程.错误信号.connect(self.处理错误)
        self.行情线程.start()

    def 切换合约订阅(self, 新合约: str):
        global 合约代码
        新合约 = 规范化合约代码(新合约)
        if not 新合约 or 新合约 == self.当前合约:
            return
        旧线程 = self.行情线程
        self.当前合约 = 新合约
        合约代码 = 新合约
        写入最近合约(新合约)
        保存配置()
        if 旧线程 is not None:
            旧线程.停止()
            旧线程.wait(1500)
        self._启动行情线程(self.当前合约)
        self.悬浮牌.应用样式(小字=生效小字())
        self.托盘.setToolTip(f"{self.当前合约} {标题前缀}: …")

    def 退出(self):
        if self.行情线程 is not None:
            self.行情线程.停止()
            self.行情线程.wait(2000)
        self.托盘.hide()
        self.应用.quit()

    # ==== 行情回调 ====
    def 处理价格更新(self, 文本):
        self.悬浮牌.更新价格文本(文本)
        self.托盘.setToolTip(f"{self.当前合约} {标题前缀}: {文本}")

    def 处理错误(self, 信息):
        self.托盘.setToolTip(f"{self.当前合约} 出错: {信息}")
        # 可以视情况弹个提示框：
        # QtWidgets.QMessageBox.warning(None, "运行出错", 信息)


def main():
    读取配置()
    app = QtWidgets.QApplication(sys.argv)
    控制 = 主控制(app)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
