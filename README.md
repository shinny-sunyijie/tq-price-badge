# 项目简介
这是一个基于 TqSdk + PySide6 的「期货行情透明悬浮牌」，带托盘图标和简单设置界面。
# 功能说明
 - 始终置顶透明悬浮牌显示某个合约最新价
 - 除价格外，悬浮牌可以显示一行备注小字
 - 托盘菜单：显示/隐藏、锁定、设置、退出
 - 自动记住上次样式配置

项目基于天勤量化行情，登录信息需写在系统环境变量中
```chatinput
pip install -r requirements.txt
python tq_price_badge.py CZCE.PX601
```