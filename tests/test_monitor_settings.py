# -*- coding: utf-8 -*-
"""设置页账户监控开关的离屏测试。"""

from __future__ import annotations

import os
import unittest
from unittest import mock


os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("TQ_USER", "offline-settings-test")
os.environ.setdefault("TQ_PASS", "offline-settings-test")

from PySide6 import QtWidgets  # noqa: E402

from badge_app.backend import state  # noqa: E402
from badge_app.frontend import dialogs as dialogs_module  # noqa: E402
from badge_app.frontend.dialogs import 设置对话框  # noqa: E402


class _离线设置对话框(设置对话框):
    def _加载在市期货合约(self):
        """测试替身：跳过会创建行情连接的合约补全加载。"""


class _假信号:
    def __init__(self):
        self.槽 = []

    def connect(self, 槽):
        self.槽.append(槽)


class _共享加载线程:
    def __init__(self):
        self.完成信号 = _假信号()
        self.错误信号 = _假信号()
        self.finished = _假信号()

    def isFinished(self):
        return False


class 账户监控设置测试(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.应用 = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self._原配置 = state.配置
        state.配置 = state.默认配置.copy()
        self.addCleanup(setattr, state, "配置", self._原配置)

    def test_两个开关独立保存且默认关闭(self):
        with mock.patch.object(state, "保存配置"):
            对话 = _离线设置对话框("KQ.m@SHFE.cu")
            self.addCleanup(对话.deleteLater)

            self.assertFalse(对话.持仓行情监控开关.isChecked())
            self.assertFalse(对话.委托行情监控开关.isChecked())
            self.assertIn("持仓合约最新价", 对话.持仓行情监控开关.text())
            self.assertIn("委托合约最新价", 对话.委托行情监控开关.text())

            对话.持仓行情监控开关.setChecked(True)
            对话.委托行情监控开关.setChecked(False)
            对话.accept()

        self.assertTrue(state.配置["monitor_position_quotes"])
        self.assertFalse(state.配置["monitor_order_quotes"])

    def test_自定义行情默认1条且可关闭为0条(self):
        with mock.patch.object(state, "保存配置"):
            对话 = _离线设置对话框("KQ.m@SHFE.cu")
            self.addCleanup(对话.deleteLater)
            self.assertTrue(对话.自定义行情显示开关.isChecked())
            self.assertIn("最多 1 条", 对话.自定义行情显示开关.text())

            对话.自定义行情显示开关.setChecked(False)
            self.assertFalse(对话.合约输入.isEnabled())
            self.assertTrue(对话.预览组件.isHidden())
            对话.accept()

        self.assertFalse(state.配置["custom_quote_enabled"])

    def test_0条自定义行情时临时勾选也不加载合约目录(self):
        state.配置["custom_quote_enabled"] = False
        with (
            mock.patch.object(state, "保存配置"),
            mock.patch.object(设置对话框, "_加载在市期货合约") as 加载,
        ):
            对话 = 设置对话框("KQ.m@SHFE.cu")
            self.addCleanup(对话.deleteLater)
            加载.assert_not_called()
            对话.自定义行情显示开关.setChecked(True)
            加载.assert_not_called()

    def test_首次目录仍在加载时多个设置窗口复用同一线程(self):
        原缓存 = dialogs_module._在市期货合约缓存
        原加载线程 = dialogs_module._在市期货合约加载中
        共享线程 = _共享加载线程()
        dialogs_module._在市期货合约缓存 = None
        dialogs_module._在市期货合约加载中 = 共享线程

        def 恢复全局状态():
            dialogs_module._在市期货合约缓存 = 原缓存
            dialogs_module._在市期货合约加载中 = 原加载线程

        self.addCleanup(恢复全局状态)
        with mock.patch.object(state, "保存配置"):
            对话一 = 设置对话框("KQ.m@SHFE.cu")
            对话二 = 设置对话框("KQ.m@SHFE.cu")
            self.addCleanup(对话一.deleteLater)
            self.addCleanup(对话二.deleteLater)

        self.assertIs(共享线程, 对话一._合约加载线程)
        self.assertIs(共享线程, 对话二._合约加载线程)
        self.assertEqual(2, len(共享线程.完成信号.槽))

    def test_账户字号与两层位置保存(self):
        with mock.patch.object(state, "保存配置"):
            对话 = _离线设置对话框("KQ.m@SHFE.cu")
            self.addCleanup(对话.deleteLater)
            对话.账户状态字号变量.setValue(10)
            对话.持仓字号变量.setValue(12)
            对话.委托字号变量.setValue(13)

            对话.账户面板位置自动开关.setChecked(False)
            对话.账户面板X变量.setValue(21)
            对话.账户面板Y变量.setValue(135)
            对话.持仓位置自动开关.setChecked(False)
            对话.持仓X变量.setValue(8)
            对话.持仓Y变量.setValue(120)
            对话.accept()

        self.assertEqual(10, state.配置["account_status_font_size"])
        self.assertEqual(12, state.配置["account_position_font_size"])
        self.assertEqual(13, state.配置["account_order_font_size"])
        self.assertEqual({"x": 21, "y": 135}, state.配置["account_panel_pos"])
        self.assertEqual({"x": 8, "y": 120}, state.配置["account_position_pos"])
        self.assertIsNone(state.配置["account_status_pos"])
        读取位置 = state.读取账户组件位置配置()
        self.assertEqual(["panel", "status", "order", "position"], list(读取位置))
        self.assertEqual((21, 135), (读取位置["panel"].x(), 读取位置["panel"].y()))
        self.assertEqual((8, 120), (读取位置["position"].x(), 读取位置["position"].y()))


if __name__ == "__main__":
    unittest.main()
