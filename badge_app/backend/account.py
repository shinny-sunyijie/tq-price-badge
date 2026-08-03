# -*- coding: utf-8 -*-
"""只读实盘账户监控。

本模块只读取账户、持仓、活动委托和行情。TqSdk 对象始终留在线程内，
跨线程信号中只发送由 Python 基本类型组成的 ``dict`` / ``list``。
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Mapping
from typing import Any

from PySide6 import QtCore
from tqsdk import TqAccount, TqApi, TqAuth


账户数值字段 = (
    "pre_balance",
    "static_balance",
    "balance",
    "available",
    "ctp_balance",
    "ctp_available",
    "float_profit",
    "position_profit",
    "close_profit",
    "frozen_margin",
    "margin",
    "frozen_commission",
    "commission",
    "frozen_premium",
    "premium",
    "deposit",
    "withdraw",
    "risk_ratio",
    "market_value",
)


def _读取字段(对象: Any, 字段名: str, 默认值: Any = None) -> Any:
    """同时兼容普通字典、测试替身和 TqSdk Entity。"""

    if 对象 is None:
        return 默认值
    if isinstance(对象, Mapping):
        return 对象.get(字段名, 默认值)
    try:
        return 对象[字段名]
    except Exception:
        return getattr(对象, 字段名, 默认值)


def _有限数字(值: Any) -> float | None:
    try:
        数值 = float(值)
    except (TypeError, ValueError, OverflowError):
        return None
    return 数值 if math.isfinite(数值) else None


def _整数(值: Any, 默认值: int = 0) -> int:
    数值 = _有限数字(值)
    if 数值 is None:
        return 默认值
    return int(数值)


def _字符串(值: Any) -> str:
    return "" if 值 is None else str(值)


def _布尔或空(值: Any) -> bool | None:
    return None if 值 is None else bool(值)


def _普通映射项(对象: Any):
    try:
        return list(对象.items())
    except (AttributeError, TypeError):
        return []


def _合约代码(键: Any, 对象: Any) -> str:
    代码 = _字符串(键).strip()
    if 代码 and not 代码.startswith("_"):
        return 代码
    交易所 = _字符串(_读取字段(对象, "exchange_id")).strip()
    合约 = _字符串(_读取字段(对象, "instrument_id")).strip()
    return f"{交易所}.{合约}" if 交易所 and 合约 else ""


def 转换账户快照(账户: Any) -> dict:
    """将账户引用转换为可跨线程发送的普通字典。"""

    快照 = {"currency": _字符串(_读取字段(账户, "currency"))}
    for 字段名 in 账户数值字段:
        快照[字段名] = _有限数字(_读取字段(账户, 字段名))
    return 快照


def 转换持仓快照(全部持仓: Any) -> list[dict]:
    """过滤空持仓，并保留多空两侧各自的浮动盈亏。"""

    结果: list[dict] = []
    for 键, 持仓 in _普通映射项(全部持仓):
        合约 = _合约代码(键, 持仓)
        多头手数 = _整数(_读取字段(持仓, "pos_long"))
        空头手数 = _整数(_读取字段(持仓, "pos_short"))
        if not 合约 or (多头手数 == 0 and 空头手数 == 0):
            continue

        多头 = {
            "volume": 多头手数,
            "today": _整数(_读取字段(持仓, "pos_long_today")),
            "history": _整数(_读取字段(持仓, "pos_long_his")),
            "open_price": _有限数字(_读取字段(持仓, "open_price_long")),
            "position_price": _有限数字(_读取字段(持仓, "position_price_long")),
            "float_profit": _有限数字(_读取字段(持仓, "float_profit_long")),
        }
        空头 = {
            "volume": 空头手数,
            "today": _整数(_读取字段(持仓, "pos_short_today")),
            "history": _整数(_读取字段(持仓, "pos_short_his")),
            "open_price": _有限数字(_读取字段(持仓, "open_price_short")),
            "position_price": _有限数字(_读取字段(持仓, "position_price_short")),
            "float_profit": _有限数字(_读取字段(持仓, "float_profit_short")),
        }
        结果.append(
            {
                "symbol": 合约,
                "exchange_id": _字符串(_读取字段(持仓, "exchange_id")),
                "instrument_id": _字符串(_读取字段(持仓, "instrument_id")),
                "pos_long": 多头手数,
                "pos_short": 空头手数,
                "long": 多头,
                "short": 空头,
                "float_profit_long": 多头["float_profit"],
                "float_profit_short": 空头["float_profit"],
                "float_profit": _有限数字(_读取字段(持仓, "float_profit")),
            }
        )
    结果.sort(key=lambda 项: 项["symbol"])
    return 结果


def 转换活动委托快照(全部委托: Any) -> list[dict]:
    """仅返回仍有效且剩余手数大于零的委托。"""

    结果: list[dict] = []
    for 键, 委托 in _普通映射项(全部委托):
        状态 = _字符串(_读取字段(委托, "status")).upper()
        剩余手数 = _整数(_读取字段(委托, "volume_left"))
        if 状态 != "ALIVE" or 剩余手数 <= 0:
            continue
        合约 = _合约代码("", 委托)
        if not 合约:
            continue
        原始手数 = _整数(_读取字段(委托, "volume_orign"))
        结果.append(
            {
                "order_id": _字符串(_读取字段(委托, "order_id", 键)) or _字符串(键),
                "exchange_order_id": _字符串(_读取字段(委托, "exchange_order_id")),
                "symbol": 合约,
                "exchange_id": _字符串(_读取字段(委托, "exchange_id")),
                "instrument_id": _字符串(_读取字段(委托, "instrument_id")),
                "direction": _字符串(_读取字段(委托, "direction")),
                "offset": _字符串(_读取字段(委托, "offset")),
                "volume_orign": 原始手数,
                "volume_left": 剩余手数,
                "volume_traded": max(0, 原始手数 - 剩余手数),
                "limit_price": _有限数字(_读取字段(委托, "limit_price")),
                "price_type": _字符串(_读取字段(委托, "price_type")),
                "volume_condition": _字符串(_读取字段(委托, "volume_condition")),
                "time_condition": _字符串(_读取字段(委托, "time_condition")),
                "insert_date_time": _整数(_读取字段(委托, "insert_date_time")),
                "last_msg": _字符串(_读取字段(委托, "last_msg")),
                "status": 状态,
                "is_dead": _布尔或空(_读取字段(委托, "is_dead")),
                "is_online": _布尔或空(_读取字段(委托, "is_online")),
                "is_error": _布尔或空(_读取字段(委托, "is_error")),
                "trade_price": _有限数字(_读取字段(委托, "trade_price")),
            }
        )
    结果.sort(key=lambda 项: (项["insert_date_time"], 项["order_id"]))
    return 结果


def 转换行情快照(
    行情引用: Any,
    持仓合约: set[str] | frozenset[str],
    委托合约: set[str] | frozenset[str],
) -> list[dict]:
    """按所需合约生成行情快照，未取得首笔行情时也保留占位项。"""

    所需合约 = set(持仓合约) | set(委托合约)
    结果: list[dict] = []
    for 合约 in sorted(所需合约):
        行情 = None
        try:
            行情 = 行情引用.get(合约)
        except (AttributeError, TypeError):
            pass
        结果.append(
            {
                "symbol": 合约,
                "last_price": _有限数字(_读取字段(行情, "last_price")),
                "price_decs": (
                    None
                    if _读取字段(行情, "price_decs") is None
                    else _整数(_读取字段(行情, "price_decs"))
                ),
                "datetime": _字符串(_读取字段(行情, "datetime")),
                "from_position": 合约 in 持仓合约,
                "from_order": 合约 in 委托合约,
            }
        )
    return 结果


def 构建只读快照(
    账户: Any,
    全部持仓: Any,
    全部委托: Any,
    行情引用: Any = None,
    监控持仓行情: bool = False,
    监控委托行情: bool = False,
) -> dict:
    """纯函数：从 SDK 风格对象构建完整、可序列化的只读快照。"""

    持仓 = 转换持仓快照(全部持仓)
    活动委托 = 转换活动委托快照(全部委托)
    持仓合约 = {项["symbol"] for 项 in 持仓} if 监控持仓行情 else set()
    委托合约 = {项["symbol"] for 项 in 活动委托} if 监控委托行情 else set()
    return {
        "account": 转换账户快照(账户),
        "positions": 持仓,
        "orders": 活动委托,
        "quotes": 转换行情快照(行情引用 or {}, 持仓合约, 委托合约),
        "monitor_position_quotes": bool(监控持仓行情),
        "monitor_order_quotes": bool(监控委托行情),
    }


def _掩码账号(账号: str) -> str:
    账号 = (账号 or "").strip()
    if len(账号) <= 2:
        return "*" * len(账号)
    if len(账号) <= 6:
        return f"{账号[:1]}***{账号[-1:]}"
    return f"{账号[:2]}***{账号[-2:]}"


def _行情订阅重试间隔(失败次数: int) -> float:
    """行情订阅的有上限指数退避，既不永久放弃也不频繁请求。"""

    次数 = max(1, int(失败次数))
    return min(60.0, float(2 ** min(次数 - 1, 6)))


class 账户监控线程(QtCore.QThread):
    """应用层只构造一次的实盘监控线程，不执行下单或撤单。

    网络中断后的底层重连由 TqSdk 自身管理，本项目不会因设置切换、午休超时
    或普通快照变化而重建 ``TqApi``。
    """

    快照信号 = QtCore.Signal(dict)
    账户信号 = QtCore.Signal(dict)
    持仓信号 = QtCore.Signal(list)
    委托信号 = QtCore.Signal(list)
    行情信号 = QtCore.Signal(list)
    状态信号 = QtCore.Signal(dict)
    错误信号 = QtCore.Signal(dict)

    def __init__(
        self,
        经纪公司: str,
        资金账号: str,
        交易密码: str,
        天勤用户: str,
        天勤密码: str,
        监控持仓行情: bool = False,
        监控委托行情: bool = False,
        父=None,
    ):
        super().__init__(父)
        凭据 = {
            "经纪公司": 经纪公司,
            "资金账号": 资金账号,
            "交易密码": 交易密码,
            "天勤用户": 天勤用户,
            "天勤密码": 天勤密码,
        }
        缺少 = [名称 for 名称, 值 in 凭据.items() if not str(值 or "").strip()]
        if 缺少:
            raise ValueError(f"缺少账户连接参数: {', '.join(缺少)}")

        self.经纪公司 = str(经纪公司).strip()
        self.资金账号 = str(资金账号).strip()
        self._交易密码 = str(交易密码)
        self._天勤用户 = str(天勤用户).strip()
        self._天勤密码 = str(天勤密码)
        self._开关锁 = threading.Lock()
        self._监控持仓行情 = bool(监控持仓行情)
        self._监控委托行情 = bool(监控委托行情)
        self._停止事件 = threading.Event()

    @property
    def 监控持仓行情(self) -> bool:
        with self._开关锁:
            return self._监控持仓行情

    @property
    def 监控委托行情(self) -> bool:
        with self._开关锁:
            return self._监控委托行情

    @QtCore.Slot(bool)
    def 设置持仓行情监控(self, 开启: bool):
        with self._开关锁:
            self._监控持仓行情 = bool(开启)

    @QtCore.Slot(bool)
    def 设置委托行情监控(self, 开启: bool):
        with self._开关锁:
            self._监控委托行情 = bool(开启)

    def _读取监控开关(self) -> tuple[bool, bool]:
        with self._开关锁:
            return self._监控持仓行情, self._监控委托行情

    @QtCore.Slot()
    def 停止(self):
        self._停止事件.set()
        self.requestInterruption()

    def _已停止(self) -> bool:
        return self._停止事件.is_set() or self.isInterruptionRequested()

    def _状态(self, 状态: str, 信息: str = ""):
        self.状态信号.emit(
            {
                "state": 状态,
                "message": 信息,
                "broker_id": self.经纪公司,
                "account_id": _掩码账号(self.资金账号),
            }
        )

    def _发送快照(self, 快照: dict):
        self.快照信号.emit(快照)
        self.账户信号.emit(快照["account"])
        self.持仓信号.emit(快照["positions"])
        self.委托信号.emit(快照["orders"])
        self.行情信号.emit(快照["quotes"])

    def run(self):
        api = None
        self._状态("connecting", "正在连接实盘账户")
        try:
            if self._已停止():
                return

            # TqAccount 登录本身会遵循 TqSdk 的结算确认及断线重连机制；本模块
            # 不调用任何委托、撤单、转账或目标持仓接口。
            实盘账户 = TqAccount(self.经纪公司, self.资金账号, self._交易密码)
            api = TqApi(
                account=实盘账户,
                auth=TqAuth(self._天勤用户, self._天勤密码),
                disable_print=True,
            )
            账户引用 = api.get_account()
            持仓引用 = api.get_position()
            委托引用 = api.get_order()
            行情引用: dict[str, Any] = {}
            # symbol -> (连续失败次数, 下次可重试的 monotonic 时刻)
            订阅重试: dict[str, tuple[int, float]] = {}
            上次快照 = None
            上次发送时间 = 0.0
            self._状态("connected", "实盘账户只读监控已连接")

            while not self._已停止():
                api.wait_update(deadline=time.time() + 0.5)
                if self._已停止():
                    break

                监控持仓行情, 监控委托行情 = self._读取监控开关()
                持仓快照 = 转换持仓快照(持仓引用)
                委托快照 = 转换活动委托快照(委托引用)
                持仓合约 = {项["symbol"] for 项 in 持仓快照} if 监控持仓行情 else set()
                委托合约 = {项["symbol"] for 项 in 委托快照} if 监控委托行情 else set()
                所需合约 = 持仓合约 | 委托合约
                for 合约 in list(订阅重试):
                    if 合约 not in 所需合约:
                        订阅重试.pop(合约, None)
                订阅时间 = time.monotonic()
                新合约 = sorted(
                    合约 for 合约 in 所需合约 - set(行情引用)
                    if 订阅重试.get(合约, (0, 0.0))[1] <= 订阅时间
                )
                if 新合约:
                    try:
                        新行情 = list(api.get_quote_list(新合约))
                        if len(新行情) != len(新合约):
                            raise RuntimeError("行情订阅返回数量与请求合约数量不一致")
                        行情引用.update(zip(新合约, 新行情))
                        for 合约 in 新合约:
                            订阅重试.pop(合约, None)
                    except Exception as 异常:
                        最大重试间隔 = 0.0
                        for 合约 in 新合约:
                            失败次数 = 订阅重试.get(合约, (0, 0.0))[0] + 1
                            重试间隔 = _行情订阅重试间隔(失败次数)
                            订阅重试[合约] = (失败次数, 订阅时间 + 重试间隔)
                            最大重试间隔 = max(最大重试间隔, 重试间隔)
                        self.错误信号.emit(
                            {
                                "type": "quote_subscription_error",
                                "message": str(异常),
                                "symbols": list(新合约),
                                "retry_after_seconds": 最大重试间隔,
                                "fatal": False,
                            }
                        )

                快照 = {
                    "account": 转换账户快照(账户引用),
                    "positions": 持仓快照,
                    "orders": 委托快照,
                    "quotes": 转换行情快照(行情引用, 持仓合约, 委托合约),
                    "monitor_position_quotes": 监控持仓行情,
                    "monitor_order_quotes": 监控委托行情,
                }
                当前时间 = time.monotonic()
                内容变化 = 快照 != 上次快照
                到达心跳 = 当前时间 - 上次发送时间 >= 2.0
                if (内容变化 and 当前时间 - 上次发送时间 >= 0.25) or 到达心跳:
                    self._发送快照(快照)
                    上次快照 = 快照
                    上次发送时间 = 当前时间
        except Exception as 异常:
            错误 = {
                "type": "account_monitor_error",
                "message": str(异常),
                "fatal": True,
            }
            self.错误信号.emit(错误)
            self._状态("error", 错误["message"])
        finally:
            if api is not None:
                try:
                    api.close()
                except Exception:
                    pass
            self._状态("stopped", "实盘账户监控已停止")


AccountMonitorThread = 账户监控线程
