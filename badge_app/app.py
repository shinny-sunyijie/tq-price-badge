# -*- coding: utf-8 -*-
import sys

from PySide6 import QtWidgets, QtCore

from .backend import state
from .backend.market import 行情线程, 写入最近合约, 规范化合约代码
from .frontend.dialogs import 设置对话框
from .frontend.widgets import 悬浮牌窗口


class 主控制(QtCore.QObject):
    def __init__(self, 应用: QtWidgets.QApplication):
        super().__init__()
        self.应用 = 应用
        self.当前合约 = 规范化合约代码(state.合约代码)
        state.设置当前合约(self.当前合约)
        写入最近合约(self.当前合约)
        state.保存配置()
        self.悬浮牌 = 悬浮牌窗口()
        self.悬浮牌.设置请求.connect(self.打开设置)
        if state.显示大号价格默认:
            self.悬浮牌.show()

        self.行情线程 = None
        self._启动行情线程(self.当前合约)
        self._创建托盘()

    def _创建托盘(self):
        图标 = self.应用.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
        self.托盘 = QtWidgets.QSystemTrayIcon(图标, self.应用)
        菜单 = QtWidgets.QMenu()

        self.显示动作 = 菜单.addAction("隐藏大号价格" if self.悬浮牌.isVisible() else "显示大号价格")
        self.锁定动作 = 菜单.addAction("解锁悬浮牌" if self.悬浮牌.已锁定 else "锁定悬浮牌")
        菜单.addSeparator()
        self.设置动作 = 菜单.addAction("设置")
        菜单.addSeparator()
        self.退出动作 = 菜单.addAction("退出")

        self.显示动作.triggered.connect(self.切换悬浮牌可见)
        self.锁定动作.triggered.connect(self.切换锁定)
        self.设置动作.triggered.connect(self.打开设置)
        self.退出动作.triggered.connect(self.退出)

        self.托盘.setContextMenu(菜单)
        self.托盘.setToolTip(f"{self.当前合约} {state.标题前缀}: …")
        self.托盘.show()

    def 切换悬浮牌可见(self):
        if self.悬浮牌.isVisible():
            self.悬浮牌.hide()
            self.显示动作.setText("显示大号价格")
        else:
            self.悬浮牌.show()
            self.显示动作.setText("隐藏大号价格")

    def 切换锁定(self):
        self.悬浮牌.切换锁定()
        self.锁定动作.setText("解锁悬浮牌" if self.悬浮牌.已锁定 else "锁定悬浮牌")

    def 打开设置(self):
        对话 = 设置对话框(self.当前合约, self.悬浮牌)
        对话.合约切换请求.connect(self.切换合约订阅)
        if 对话.exec() == QtWidgets.QDialog.Accepted:
            self.悬浮牌.应用样式(
                字号=state.配置["badge_font_size"],
                颜色=state.配置["badge_font_color"],
                小字=state.生效小字(),
                小字字号=state.配置["subtitle_font_size"],
                小字颜色=state.配置["subtitle_font_color"],
            )
            self.悬浮牌.更新组件位置(state.读取组件位置配置())

    def _启动行情线程(self, 代码: str):
        self.行情线程 = 行情线程(代码, state.TQ_USER, state.TQ_PASS)
        self.行情线程.价格信号.connect(self.处理价格更新)
        self.行情线程.错误信号.connect(self.处理错误)
        self.行情线程.start()

    def 切换合约订阅(self, 新合约: str):
        新合约 = 规范化合约代码(新合约)
        if not 新合约 or 新合约 == self.当前合约:
            return
        旧线程 = self.行情线程
        self.当前合约 = 新合约
        state.设置当前合约(新合约)
        写入最近合约(新合约)
        state.保存配置()
        if 旧线程 is not None:
            旧线程.停止()
            旧线程.wait(1500)
        self._启动行情线程(self.当前合约)
        self.悬浮牌.应用样式(小字=state.生效小字())
        self.托盘.setToolTip(f"{self.当前合约} {state.标题前缀}: …")

    def 退出(self):
        if self.行情线程 is not None:
            self.行情线程.停止()
            self.行情线程.wait(2000)
        self.托盘.hide()
        self.应用.quit()

    def 处理价格更新(self, 文本):
        self.悬浮牌.更新价格文本(文本)
        self.托盘.setToolTip(f"{self.当前合约} {state.标题前缀}: {文本}")

    def 处理错误(self, 信息):
        self.托盘.setToolTip(f"{self.当前合约} 出错: {信息}")


def main():
    state.读取配置()
    app = QtWidgets.QApplication(sys.argv)
    主控制(app)
    sys.exit(app.exec())
