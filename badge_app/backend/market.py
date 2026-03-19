# -*- coding: utf-8 -*-
import math
import re
import time

from PySide6 import QtCore
from tqsdk import TqApi, TqAuth

from . import state

合约代码正则 = re.compile(r"^(?:KQ\.(?:m|i)@[A-Z]+\.[A-Za-z0-9]+|[A-Z]+\.[A-Za-z0-9]+)$")
小写品种交易所 = {"SHFE", "DCE", "INE", "GFEX"}
大写品种交易所 = {"CZCE", "CFFEX"}


def 规范化合约代码(原始: str) -> str:
    文本 = (原始 or "").strip()
    if not 文本:
        return ""

    主连匹配 = re.fullmatch(r"KQ\.([mMiI])@([A-Za-z]+)\.([A-Za-z0-9]+)", 文本)
    if 主连匹配:
        类型, 交易所, 品种 = 主连匹配.groups()
        交易所 = 交易所.upper()
        return f"KQ.{类型.lower()}@{交易所}.{_规范化品种代码(交易所, 品种)}"

    普通匹配 = re.fullmatch(r"([A-Za-z]+)\.([A-Za-z0-9]+)", 文本)
    if 普通匹配:
        交易所, 品种 = 普通匹配.groups()
        交易所 = 交易所.upper()
        return f"{交易所}.{_规范化品种代码(交易所, 品种)}"

    return 文本


def _规范化品种代码(交易所: str, 品种代码: str) -> str:
    """按交易所保留 TqSdk 需要的品种大小写，避免 SHFE.bu 被错误改成 SHFE.BU。"""

    品种代码 = (品种代码 or "").strip()
    if not 品种代码:
        return ""

    匹配 = re.fullmatch(r"([A-Za-z]+)([0-9A-Za-z]*)", 品种代码)
    if not 匹配:
        return 品种代码

    品种前缀, 后缀 = 匹配.groups()
    if 交易所 in 小写品种交易所:
        品种前缀 = 品种前缀.lower()
    elif 交易所 in 大写品种交易所:
        品种前缀 = 品种前缀.upper()
    return f"{品种前缀}{后缀}"


def 合约代码合法(代码: str) -> bool:
    return bool(合约代码正则.fullmatch(代码))


def 写入最近合约(代码: str):
    代码 = 规范化合约代码(代码)
    if not 代码:
        return
    历史 = [规范化合约代码(x) for x in state.配置.get("recent_symbols", []) if str(x).strip()]
    新历史 = [代码] + [x for x in 历史 if x != 代码]
    state.配置["recent_symbols"] = 新历史[:30]


def _读取quote字段(quote, 字段名: str):
    try:
        return quote[字段名]
    except Exception:
        return getattr(quote, 字段名, None)


def _转为有限数字(值):
    if 值 is None:
        return None
    try:
        数值 = float(值)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(数值):
        return None
    return 数值


def 格式化价格(p, 小数位: int | None = None):
    价格 = _转为有限数字(p)
    if 价格 is None:
        return "—"

    try:
        小数位 = None if 小数位 is None else max(0, int(小数位))
    except (TypeError, ValueError, OverflowError):
        小数位 = None

    if 小数位 is not None:
        return f"{价格:.{小数位}f}"
    if 价格.is_integer():
        return str(int(价格))
    return f"{价格:.10f}".rstrip("0").rstrip(".")


def 读取最新价(quote):
    return _转为有限数字(_读取quote字段(quote, "last_price"))


def 读取价格小数位(quote) -> int | None:
    小数位 = _读取quote字段(quote, "price_decs")
    try:
        小数位 = int(小数位)
    except (TypeError, ValueError, OverflowError):
        return None
    return max(0, 小数位)


class 行情线程(QtCore.QThread):
    价格信号 = QtCore.Signal(object)
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
                价格 = 读取最新价(quote)
                小数位 = 读取价格小数位(quote)
                if 价格 is None and not state.当价格为空也更新:
                    api.wait_update(deadline=time.time() + 1)
                    continue
                if 价格 is None:
                    连续无价格次数 += 1
                    if 连续无价格次数 == 200:
                        self.错误信号.emit(
                            f"合约 {self.合约} 暂无最新价，请确认合约是否可交易（建议使用主连如 KQ.m@SHFE.cu）"
                        )
                else:
                    连续无价格次数 = 0
                文本 = 格式化价格(价格, 小数位)
                if 文本 != 上次文本:
                    上次文本 = 文本
                    self.价格信号.emit(文本)
                api.wait_update(deadline=time.time() + 1)
        except Exception as e:
            self.错误信号.emit(str(e))
        finally:
            if api is not None:
                try:
                    api.close()
                except Exception:
                    pass


class 在市期货合约加载线程(QtCore.QThread):
    完成信号 = QtCore.Signal(list)
    错误信号 = QtCore.Signal(str)

    def __init__(self, 用户: str, 密码: str, 父=None):
        super().__init__(父)
        self.用户 = 用户
        self.密码 = 密码

    def run(self):
        api = None
        try:
            api = TqApi(auth=TqAuth(self.用户, self.密码))
            合约列表 = list(api.query_quotes(ins_class="FUTURE", expired=False))
            if not 合约列表:
                self.完成信号.emit([])
                return

            quote列表 = api.get_quote_list(合约列表)
            for _ in range(3):
                if self.isInterruptionRequested():
                    return
                api.wait_update(deadline=time.time() + 1)

            def _成交量(q) -> float:
                try:
                    值 = q["volume"]
                except Exception:
                    值 = getattr(q, "volume", None)
                if 值 is None:
                    return -1.0
                try:
                    值 = float(值)
                except Exception:
                    return -1.0
                return -1.0 if math.isnan(值) else 值

            带成交量 = [(代码, _成交量(quote)) for 代码, quote in zip(合约列表, quote列表)]
            带成交量.sort(key=lambda x: x[1], reverse=True)
            self.完成信号.emit([代码 for 代码, _ in 带成交量])
        except Exception as e:
            self.错误信号.emit(str(e))
        finally:
            if api is not None:
                try:
                    api.close()
                except Exception:
                    pass
