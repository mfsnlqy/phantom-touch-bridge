# 我的设备在不在支持范围内

这份文档只回答一个问题：

- 你的设备现在适不适合用 `phantom-touch-bridge`

如果你不想看太多技术解释，只想赶快判断，直接按下面步骤来。

## 最短判断法

### 第一步：先试 `Intiface Central`

先安装并打开 `Intiface Central`，然后看你的设备会不会出现在里面。

如果出现了，而且能正常连接或控制：

- 你优先走 `Intiface`
- 这是当前最推荐、最省心的路线

如果没有出现，或者出现了但明显不能正常工作：

- 再进入第二步

## 第二步：再看自己适不适合试 `custom`

下面这些情况，说明你值得继续评估 `custom`：

- 设备能被手机官方 App 正常控制
- 设备大概率是 BLE 蓝牙设备
- 你的 Windows 电脑本身有可用蓝牙，或者已经准备了蓝牙适配器
- 你愿意在启动时输入设备名称关键词
- 你知道这条路线不是“官方生态支持”，更像是一条兼容尝试
- 你已经知道自己的设备和当前项目已知路线比较接近，或者家机判断值得先试

如果只满足“官方 App 能控制”这一条，还不能直接当成项目已经支持。

如果上面这些条件大致都符合，才更适合继续试 `custom`。

如果你已经不想继续判断，只想直接开试，可以接着看：

- [quick-start.md](quick-start.md)

## 什么情况下大概率不在当前支持范围内

下面这些情况，通常说明当前项目不适合直接使用：

- 设备既不被 `Intiface` 支持
- 项目里也没有现成的 `custom` 路线
- 你也不打算做抓日志、逆向或补证据
- 你希望任意蓝牙设备都能直接开箱即用

## 用一句话判断

- `Intiface` 能看到：优先用
- `Intiface` 看不到，但设备能被官方 App 控制，而且家机也判断值得试：可以继续试 `custom`
- 两边都不行：当前大概率不在支持范围内

## 如果你还是看不懂

你可以把下面两份文档交给家机看，让它陪你一起判断：

- [project-architecture-for-ai.md](ai/project-architecture-for-ai.md)
- [device-support-for-ai.md](ai/device-support-for-ai.md)

## 如果家机说“可能支持”，你下一步做什么

- 想先上手：看 [quick-start.md](quick-start.md)
- 想补一下常见问题：看 [faq.md](faq.md)
- 想自己抓证据：看 [protocol-reverse-engineering-human.md](protocol-reverse-engineering-human.md)
- 想让家机继续指导你逆向：把 [protocol-reverse-engineering-ai.md](ai/protocol-reverse-engineering-ai.md) 一起交给它看
