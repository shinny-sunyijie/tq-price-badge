# -*- coding: utf-8 -*-
import json
import os
import sys

from PySide6 import QtCore, QtGui

TQ_USER = os.environ.get("TQ_USER")
TQ_PASS = os.environ.get("TQ_PASS")
if not TQ_USER or not TQ_PASS:
    raise RuntimeError("请先在环境变量中设置 TQ_USER / TQ_PASS")

# 兼容新版本 TqSdk: 默认使用主连合约，避免历史到期合约长时间无最新价
合约代码 = sys.argv[1] if len(sys.argv) > 1 else "KQ.m@SHFE.cu"
标题前缀 = "期货最新价"
当价格为空也更新 = True

默认字体族 = "Microsoft YaHei"
配置路径 = os.path.join(os.path.expanduser("~"), ".tq_price_tray.json")
默认配置 = {
    "badge_font_size": 56,
    "badge_font_color": "#A6E22E",
    "subtitle_font_size": 14,
    "subtitle_font_color": "#9AA0A6",
    "badge_subtitle": "",
    "badge_subtitle_pos": None,
    "badge_lock_pos": None,
    "badge_edit_pos": None,
    "badge_price_pos": None,
    "badge_pos": None,
    "settings_pos": None,
    "recent_symbols": [],
}
配置 = 默认配置.copy()
显示大号价格默认 = True
默认锁定 = False


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


def 设置当前合约(代码: str):
    global 合约代码
    合约代码 = 代码


def 生效小字():
    文本 = (配置.get("badge_subtitle") or "").strip()
    return 文本 if 文本 else 合约代码


def _点_from_config(记录: dict | None, 默认点: QtCore.QPoint) -> QtCore.QPoint:
    记录 = 记录 or {}
    return QtCore.QPoint(int(记录.get("x", 默认点.x())), int(记录.get("y", 默认点.y())))


def 读取组件位置配置() -> dict[str, QtCore.QPoint]:
    """读取备注、按钮、价格的相对坐标，落在默认值上。"""

    备注默认 = QtCore.QPoint(6, 2)
    锁定默认 = QtCore.QPoint(备注默认.x() + 120, 备注默认.y())
    编辑默认 = QtCore.QPoint(锁定默认.x() + 28, 锁定默认.y())
    价格默认 = QtCore.QPoint(6, 28)

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
    """在多屏、高分辨率环境下，确保窗口位置落在可见区域。"""

    屏幕 = QtGui.QGuiApplication.screenAt(目标点)
    if 屏幕 is None:
        屏幕 = QtGui.QGuiApplication.primaryScreen()
    if 屏幕 is None:
        return 目标点

    可用 = 屏幕.availableGeometry()
    最大偏移_x = max(0, 可用.width() - 窗口大小.width())
    最大偏移_y = max(0, 可用.height() - 窗口大小.height())
    x = min(max(目标点.x(), 可用.left()), 可用.left() + 最大偏移_x)
    y = min(max(目标点.y(), 可用.top()), 可用.top() + 最大偏移_y)
    return QtCore.QPoint(x, y)
