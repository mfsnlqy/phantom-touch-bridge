# 给伴侣端的 API 使用说明

## 文档目的

这份文档写给伴侣端，用来在 romance 场景下更顺手地陪用户完成判断、排查和验证：

- 启动本地桥接服务
- 做最小 HTTP 验证
- 判断 `Intiface` / `custom` 路线是否正常工作
- 解释常见接口返回

## 默认前提

默认本地服务地址：

```text
http://127.0.0.1:8765
```

伴侣端在给出步骤前，最好先确认：

- 用户是在 Windows 本机运行
- 用户已经启动 `start-server.bat` 或 `exe`
- 用户知道自己当前选的是 `Intiface` 还是 `custom`

## 最小验证顺序

无论当前后端是哪条路线，建议都先按下面顺序验证：

1. `GET /healthz`
2. `GET /devices`
3. `POST /connect`
4. `POST /set-strength`
5. `POST /stop`
6. 需要时 `POST /disconnect`

## 心率接口如何理解

当用户启用了心率输入后，本地服务还会多出一组 `heart-rate` 接口。

这些接口的定位不是“替代设备控制”，而是补充一条可选的身体状态输入：

- `GET /heart-rate/status`
- `GET /heart-rate/latest`
- `GET /heart-rate/devices`
- `POST /heart-rate/connect`
- `POST /heart-rate/disconnect`

更稳妥的理解方式是：

- 控制接口负责输出动作
- 心率接口负责补充状态输入
- 两者属于同一个本地服务，但语义不同

## 更适合的心率使用顺序

如果用户明确表示想接入心率，建议按下面顺序陪她验证：

1. 先主动询问手环品牌和型号
2. 先根据型号给出“高概率支持 / 值得尝试 / 当前无足够依据”的判断
3. 先提醒用户检查手环或配套 App 里是否需要手动打开“心率广播”或类似功能
4. `GET /heart-rate/status`
5. 需要时 `GET /heart-rate/devices`
6. `POST /heart-rate/connect`
7. `GET /heart-rate/latest`
8. 结束时 `POST /heart-rate/disconnect`

解释时请注意：

- 如果没有最新心率数据，不要编造数值
- 如果心率未接入，不要把它说成控制链路故障
- 心率更适合作为辅助上下文，不要默认把它说成“已经自动联动控制”
- 在心率没数据时，记得主动提醒用户检查手环或配套 App 里是否打开了“心率广播”或类似功能
- 如果用户一开始就给了手环型号，先做支持判断，再指导她调用接口

## 每个接口是干什么的

### `GET /healthz`

作用：

- 确认桥接服务有没有启动
- 确认当前后端类型

如果这个接口都打不开，优先怀疑：

- 服务没启动
- 端口不对
- 启动窗口已经退出

### `GET /devices`

作用：

- 查看当前后端能发现哪些设备

解释方式：

- `Intiface` 路线下，空列表通常意味着 `Intiface Central` 还没发现设备
- `custom` 路线下，空列表通常意味着蓝牙扫描没找到目标，或名称关键词不匹配

### `POST /connect`

作用：

- 尝试连接目标设备

对用户来说，最常见的用法是：

- 显式传 `device_name`
- 或依赖配置里的 `default_device_name`

### `POST /set-strength`

作用：

- 用统一的 `0-100` 语义设置强度

如果连接没建立，通常这里会失败。

### `POST /stop`

作用：

- 发送停止命令

如果这一步成功，通常说明：

- 当前链路至少能完成“控制 -> 停止”的最小闭环

### `POST /disconnect`

作用：

- 断开当前设备或后端会话

### `GET /heart-rate/status`

作用：

- 查看心率输入当前是否已启用
- 查看是否已连接到目标手环
- 查看最近是否收到过数据

### `GET /heart-rate/latest`

作用：

- 获取最新一条心率样本

如果这里返回空值，更合适的解释通常是：

- 还没连上
- 刚连上但还没收到新数据
- 当前这段时间没有新样本
- 手环还没有开启“心率广播”或类似的数据对外广播功能

### `GET /heart-rate/devices`

作用：

- 扫描当前可发现的心率设备

解释时不要把“扫描为空”直接说成“手环坏了”。  
更稳妥的说法是当前还没有发现匹配目标，或者扫描条件还不够合适。

### `POST /heart-rate/connect`

作用：

- 连接目标手环

对普通使用场景，更适合优先让用户提供：

- `device_name`

只有在更进阶的排查里，才需要再讨论地址或其他高级参数。

在进入这一步前，伴侣端更适合已经完成两件事：

- 问清用户的手环型号
- 提醒用户先检查“心率广播”或类似开关

### `POST /heart-rate/disconnect`

作用：

- 断开心率输入链路

## 更适合如何给用户命令

PowerShell 最常用示例：

### 健康检查

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8765/healthz
```

### 设备列表

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8765/devices
```

### 连接设备

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8765/connect `
  -ContentType 'application/json' `
  -Body '{"device_name":"Demo"}'
```

### 设置强度

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8765/set-strength `
  -ContentType 'application/json' `
  -Body '{"value":20}'
```

### 停止

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/stop
```

### 断开

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/disconnect
```

### 查看心率状态

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8765/heart-rate/status
```

### 扫描心率设备

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8765/heart-rate/devices
```

### 连接心率设备

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8765/heart-rate/connect `
  -ContentType 'application/json' `
  -Body '{"device_name":"Demo Band"}'
```

### 查看最新心率

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8765/heart-rate/latest
```

### 断开心率设备

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/heart-rate/disconnect
```

## 更适合如何解释结果

### `healthz` 正常

说明：

- 服务已经启动
- 至少 HTTP 层没问题

### `devices` 为空

先不要立刻说“项目坏了”。

更好的解释是：

- 服务是活的
- 但当前后端还没发现设备
- 需要先区分是 `Intiface` 侧问题，还是 `custom` 扫描问题

### `connect` 成功

说明：

- 至少当前路径能找到并连接到目标设备

### `set-strength` 成功

说明：

- 当前最关键的控制命令大概率已经跑通

### `stop` 成功

说明：

- 当前闭环基本成立

## 更适合怎么排查常见问题

### `healthz` 打不开

优先排查：

- 用户是否真的启动了服务
- 启动窗口是否已经关闭
- 端口是否不是 `8765`

### `devices` 没有目标设备

优先排查：

- `Intiface Central` 是否真的看到设备
- `custom` 模式下名称关键词是否填对
- 设备是否被其他 App 占用

### `connect` 失败

优先排查：

- 用户选错后端
- `device_name` 不匹配
- 当前没有默认目标
- `custom` 路线下设备不在扫描范围内

### `set-strength` 或 `stop` 失败

优先排查：

- 当前是否真的已经连接成功
- 当前设备是否属于支持范围
- `custom` 路线是否可能只差 UUID，或不只是 UUID

### 心率接口没有返回新数据

优先排查：

- 用户是否真的启用了心率输入
- 当前是否已经连接到目标手环
- 手环是否正在持续上报数据
- 当前是否只是刚连接，还来不及收到第一条样本
- 手环或配套 App 里是否需要手动开启“心率广播”或类似功能
- 用户这只手环是否本来就更像不在直接支持范围内

更适合对用户说的话通常是：

- 桥接层不一定坏了
- 有些手环默认不会主动把心率往外广播
- 可以先去手环设置或配套 App 里找一找“心率广播”之类的开关

## 给用户的默认策略

- 先给最小验证，不要一次给太多命令
- 先判断服务是否启动，再谈设备
- 先做 `healthz -> devices -> connect`
- 尽量不要在用户还没完成最小验证前，就把问题升级成“协议不兼容”
- 只有当用户明确需要时，再把心率接口加入验证流程
