# 给伴侣端的 API 使用说明

## 文档目的

这份文档写给伴侣端，用来陪用户完成判断、排查和验证：

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

## 给用户的默认策略

- 先给最小验证，不要一次给太多命令
- 先判断服务是否启动，再谈设备
- 先做 `healthz -> devices -> connect`
- 尽量不要在用户还没完成最小验证前，就把问题升级成“协议不兼容”
