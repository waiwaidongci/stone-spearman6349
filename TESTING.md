# 实际验证结果

环境：Python 3.11.2 + SQLite（测试夹具）、NumPy 2.2.1 / SciPy 1.15.1；前端 ES modules 静态检查。
命令（在 `backend/` 下）：`DATABASE_URL=sqlite:// REDIS_URL=redis://localhost:6379/0 JWT_SECRET=test python -m pytest tests -q`

结果：**28 passed**。

| 测试 | 覆盖点 |
|---|---|
| tests/test_sequential_algorithm.py | e 值对阶乘公式逐点一致；对小整数与数值积分一致；单步期望为 1；同向/反向/并列判定 |
| tests/test_sequential_service.py | 轮内重叠、跨轮复用拒绝；试件可在测量前先成对登记；乱序补录等待前一对；并列整对跳过不动证据；同对重试幂等；首测值锁定不可覆盖；首次达线冻结并记录所用测值；反向达线；中断后重放台账续跑不重复；台账唯一约束兜底；耗尽不冻结；同批次多轮互不干扰 |
| tests/test_sequential_fwer.py | 任意时点查看下原假设（p=0.5）误报率 ≤ α；近原假设 p=0.52 仍受控；p=0.8 在 250 对内检出率 ≥95% |
| tests/test_sequential_api.py | 登录、创建轮次、乱序 measure 返回等待、viewer 只读 403、未登录 401、α 与空对/自我配对 422、measure/ingest 重试幂等 |

模拟（非单元测试，手工脚本）：4000 次原假设模拟，任意时点误报率约 3%（Ville 上界 5%）；p=0.8 首次达线中位数约 19 对，p=0.65 约 88 对。

未覆盖：MySQL 8 与 Redis 容器未在本机启动（环境无 Docker），容器内 `Base.metadata.create_all` 建表路径与 API 路由注册已通过应用导入验证；前端未做浏览器端到端点击验证，仅 `node --check` 语法检查。
