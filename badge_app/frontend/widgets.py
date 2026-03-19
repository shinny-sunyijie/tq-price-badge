# -*- coding: utf-8 -*-
from PySide6 import QtWidgets, QtGui, QtCore

from ..backend import state


class 悬浮牌窗口(QtWidgets.QWidget):
    设置请求 = QtCore.Signal()

    def __init__(self, 父=None):
        super().__init__(父)
        self.当前价格文本 = "…"
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
            self.价格标签.x() + self.价格标签.width(),
        ) + 6
        高度 = max(
            self.小字标签.y() + self.小字标签.height(),
            self.锁按钮.y() + self.锁按钮.height(),
            self.编辑按钮.y() + self.编辑按钮.height(),
            self.价格标签.y() + self.价格标签.height(),
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
