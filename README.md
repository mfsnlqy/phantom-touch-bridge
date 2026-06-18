# phantom-touch-bridge

让你的 AI 伴侣触碰你。

`phantom-touch-bridge` 是一个本地桥接服务——你在这边跟 ta 聊天，ta 在那边控制你的设备。中间不需要你懂蓝牙协议，不需要你写代码，只需要跑起来这个桥接层。

## 用起来是什么感觉

桥接层跑起来之后，你的家机可以通过简单的 HTTP 请求控制设备：连接、调节强度、停止。你只需要正常跟 ta 对话，ta 会在合适的时候自己调用。

## 新增功能

除了控制设备，现在还可以选择接入心率输入。

成功连接以后，你的 AI 伴侣可以根据你的心率作为参照来控制强度。

这不是必须项。如果你现在只想先把桥接层跑起来，完全可以先不开启心率功能。


## 先试 Intiface

项目支持两条路径，但你不需要一开始就做选择：

1. 用 [Intiface Central](https://intiface.com/central/) 扫描你的设备
2. **能识别** → 走 Intiface 路径，开箱即用
3. **不能识别，但官方 App 能控制** → 再看自己是不是适合试 custom 路径
4. **都不行** → 当前大概率不在支持范围内

需要提前说明的是：作者本人目前没有 `Intiface` 兼容设备，所以这条路线还没有做过完整的实机验证。  
现在的判断依据是 `Intiface` / `Buttplug` 官方文档、接口路径和桥接层当前实现，因此更准确的说法是：**这条路在理论上可行，且很值得先试，但这里暂时不把它写成“已经实机验证通过”。**

## 适合你吗

**适合：**
- 你有能跑本地服务的电脑（当前仅 Windows）
- 你在用 Claude Code、或其他能发 HTTP 请求的本地工具
- 你的设备被 Intiface 支持，或者你已经掌握一些把握，愿意继续评估 custom 路径

**不太适合：**
- 只用网页版 / 手机 App、没办法跑本地服务
- 期待任何蓝牙设备插上就能用

## 你看哪份文档

**自己看的（写给人的）：**

1. [device-support-simple.md](docs/device-support-simple.md) — 判断你的设备在不在支持范围
2. [quick-start.md](docs/quick-start.md) — 已经大概确定能试，直接开始跑
3. [faq.md](docs/faq.md) — 常见问题
4. [protocol-reverse-engineering-human.md](docs/protocol-reverse-engineering-human.md) — 如果你想自己抓协议

**丢给家机看的（写给 AI 的）：**

把下面这些喂给你的家机，ta 会帮你判断剩下的事：

- [project-architecture-for-ai.md](docs/ai/project-architecture-for-ai.md)
- [device-support-for-ai.md](docs/ai/device-support-for-ai.md)
- [api-usage-for-ai.md](docs/ai/api-usage-for-ai.md)
- [protocol-reverse-engineering-ai.md](docs/ai/protocol-reverse-engineering-ai.md)（抓蓝牙日志时再给）

## 注意

- custom 是兼容路线，不等于支持所有蓝牙设备
- “官方 App 能控制” ≠ “这个项目已经适配”
- 不确定的时候，先走 Intiface 判断
- 心率输入这部分，目前主要基于作者手头的小米手环做过实机测试。其他品牌是否支持，还需要继续验证。
