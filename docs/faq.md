# FAQ

## 1. 这个项目到底是干什么的

它是一个本地桥接服务。

你可以把它理解成：让你和家机能用比较简单的方式控制设备，而不用直接碰底层蓝牙协议。

## 2. 我应该选 `Intiface` 还是 `custom`

最简单的判断方式是：

- `Intiface Central` 能看到设备：优先选 `Intiface`
- `Intiface` 看不到，但官方 App 能控制，而且家机也判断值得试：再试 `custom`

## 3. 为什么按 `Q` 之后窗口直接消失了

这是正常现象。

如果你是双击 `start-server.bat` 启动，正常退出后窗口会直接关闭。

## 4. 为什么 `custom` 要输入设备名称关键词

因为 `custom` 路线通常需要先知道你要找哪台设备。

对大多数人来说，按设备名称关键词匹配，会比手动填蓝牙地址轻松很多。

## 5. 为什么设备能被手机 App 控制，不代表项目一定能直接用

因为“手机能控制”只说明：

- 设备本身能工作
- 官方 App 知道怎么和它通信

但不代表：

- `Intiface` 一定已经支持它
- 当前项目一定已经有适合它的 `custom` 适配

## 6. 为什么网页 Claude 不能直接用

因为这个项目是本地桥接服务。

它默认运行在你的电脑本机，网页 Claude 通常不能直接访问你电脑本地的服务和设备。

## 7. 为什么手机 Claude App 不能直接用

原因类似。

手机 App 通常不能稳定访问你电脑本机的桥接服务，所以这不是当前主支持路线。

## 8. 浏览器里出现 `favicon.ico 404` 算错误吗

通常不算。

这一般只是浏览器在顺手请求网站图标，不影响主要功能。

## 9. `custom` 路线是不是代表项目支持所有蓝牙设备

不是。

`custom` 只是兼容路径，不是“万能蓝牙控制器”。

它只适合当前项目已经掌握协议、或者至少和已知协议家族非常接近的设备。

如果要走这条路，你的 Windows 电脑本身也需要能用蓝牙，或者需要额外的蓝牙适配器。

## 10. 我完全看不懂这些技术词怎么办

你不需要一开始就把这些全看懂。

你可以：

- 先看 [quick-start.md](quick-start.md)
- 先看 [device-support-simple.md](device-support-simple.md)
- 再把给家机看的文档交给它，让它陪你一起判断

最适合先交给家机看的是：

- [project-architecture-for-ai.md](ai/project-architecture-for-ai.md)
- [device-support-for-ai.md](ai/device-support-for-ai.md)
- [api-usage-for-ai.md](ai/api-usage-for-ai.md)
