# 公厕保洁巡查记录系统

面向城市公厕管养单位的巡查记录与整改闭环管理系统，覆盖 **公厕台账 → 保洁巡查 → 问题上报 → 整改跟踪 → 外包合同与费用考核** 五条业务主线。后端为 FastAPI + SQLAlchemy，前端为 React + Vite，前后端均按模块拆分，可单独开发、单独部署。

## 功能模块

| 模块 | 页面/入口 | 主要能力 |
| --- | --- | --- |
| 总览看板 | `/` | 核心指标卡、巡查与问题趋势、整改状态/分类/严重程度分布、区域运行情况、重点关注公厕、最新问题与巡查 |
| 公厕台账 | `/restrooms`、`/restrooms/:id` | 台账增删改查、区域与状态筛选、公厕详情（档案 + 历史巡查 + 历史问题 + 覆盖它的外包合同）、关联数据删除保护 |
| 保洁巡查 | `/inspections` | 8 项检查项打分、自动折算百分制得分与等级、班次/日期/结论筛选、巡查详情（含该记录纳入的考核结算）、一键转问题上报 |
| 问题上报 | `/issues`、`/issues/:id` | 问题上报（可关联巡查记录）、分类/程度/期限、整改流程流转、整改轨迹时间线、超期预警、追加跟进记录、外包考核扣款反向追溯 |
| 外包单位 | `/vendors` | 承包单位档案（信用代码、联系人、合作状态）、年度合同数/已结算金额/扣款汇总、删除保护 |
| 外包合同 | `/contracts`、`/contracts/:id` | 登记承包单位、服务范围（按区域勾选 / 指定公厕多选）、合同期限、月度费用与付款约定；到期自动置为「已到期」；合同详情含服务公厕与月度费用台账 |
| 月度费用台账 | `/settlements`、`/settlements/:id` | 按合同+月份登记结算单、考核前扣款测算预览、按巡查质量与问题整改计算考核扣款、其他扣款调整、待考核→已考核→已结算流程锁定、扣款构成/巡查明细/问题明细逐笔快照，结算金额与考核结果双向可追溯 |

其他页面不会互相混杂：台账、巡查、问题、外包各自独立成页，详情页再做跨模块的关联展示。

## 技术栈

- 后端：FastAPI 0.115、SQLAlchemy 2.0、Pydantic v2、Uvicorn；数据库默认 SQLite，容器中可切换 PostgreSQL 16
- 前端：React 18、React Router 6、Vite 6；不使用 UI 组件库，样式集中在 `src/styles/global.css`
- 部署：Docker Compose 编排 PostgreSQL + 后端 + Nginx 前端（Nginx 同时反代 `/api`）

## 目录结构

```
.
├── backend
│   ├── app
│   │   ├── api/v1/endpoints      # 路由层：restrooms / inspections / issues / stats / meta
│   │   ├── core                 # 配置、数据库、业务常量、领域异常
│   │   ├── models               # ORM 模型：公厕、巡查、问题、整改流水、单位/合同/结算
│   │   ├── schemas              # Pydantic 出入参模型
│   │   ├── services             # 业务规则层：台账、巡查、问题整改、评分、单位合同、考核结算、统计
│   │   ├── seed.py              # 演示数据生成
│   │   └── main.py              # 应用入口（含异常处理、CORS、健康检查）
│   ├── tests                    # pytest 接口测试
│   ├── Dockerfile
│   └── requirements.txt
├── frontend
│   ├── src
│   │   ├── api                  # 按资源拆分的接口封装 + 统一 fetch 客户端
│   │   ├── components           # 通用组件：表格、分页、弹窗、标签、图表、时间线等
│   │   ├── hooks                # useAsync / useListQuery / useDictionaries
│   │   ├── pages                # dashboard / restrooms / inspections / issues 四个模块
│   │   ├── utils                # 时间格式化、评分换算
│   │   └── styles/global.css
│   ├── nginx.conf
│   └── Dockerfile
└── docker-compose.yml
```

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
docker compose up -d --build
```

启动后：

- 前端界面：http://localhost:8080
- 后端接口文档：http://localhost:8000/docs （也可通过 http://localhost:8080/docs 访问）
- 健康检查：http://localhost:8000/health

三个服务均带健康检查，`backend` 等待 `db` 健康后启动，`frontend` 等待 `backend` 健康后启动。首次启动会自动建表并写入演示数据。

停止与清理：

```bash
docker compose down        # 停止容器
docker compose down -v     # 同时删除数据库卷（下次启动重新生成演示数据）
```

### 方式二：本地开发

后端（默认使用 SQLite，数据库文件为 `backend/data/app.db`）：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173，/api 自动代理到 127.0.0.1:8000
```

若后端不在默认端口，可指定代理目标：

```bash
set VITE_PROXY_TARGET=http://127.0.0.1:8020   # macOS/Linux: export VITE_PROXY_TARGET=...
npm run dev
```

## 环境变量

后端（均可用环境变量覆盖，见 `backend/app/core/config.py`）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./data/app.db` | 数据库连接串；容器中为 `postgresql+psycopg://restroom:restroom_pass@db:5432/restroom` |
| `SEED_ON_STARTUP` | `true` | 启动时若库为空则写入演示数据 |
| `CORS_ORIGINS` | `*` | 允许跨域来源，逗号分隔 |
| `SQL_ECHO` | `false` | 是否打印 SQL |

前端：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VITE_API_BASE` | `/api/v1` | 接口前缀，构建时注入 |
| `VITE_PROXY_TARGET` | `http://127.0.0.1:8000` | 仅开发模式下 Vite 代理目标 |

## 接口一览

所有接口前缀为 `/api/v1`，完整文档见 `/docs`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/restrooms` | 台账分页查询（keyword/district/status/grade/排序/分页） |
| POST | `/restrooms` | 新增公厕，编号留空自动生成 `WC-0001` |
| GET | `/restrooms/{id}` | 详情，含巡查次数、均分、未闭环问题数 |
| PATCH | `/restrooms/{id}` | 局部更新 |
| DELETE | `/restrooms/{id}?force=` | 删除；有巡查或问题记录时返回 409，`force=true` 才级联删除 |
| GET | `/restrooms/meta/districts` | 区域列表（筛选下拉用） |
| GET | `/inspections` | 巡查记录查询（restroom_id/district/inspector/shift/result/日期区间/关键字） |
| POST | `/inspections` | 新增巡查，服务端按检查项自动算分、定级、判定结论 |
| GET/PATCH/DELETE | `/inspections/{id}` | 详情 / 更新 / 删除 |
| GET | `/issues` | 问题查询（status/category/severity/district/overdue/open_only/日期区间/关键字） |
| POST | `/issues` | 上报问题，自动生成编号 `WT-YYYYMMDD-001` 并写入首条整改流水 |
| GET/PATCH/DELETE | `/issues/{id}` | 详情（含完整整改轨迹）/ 更新 / 删除 |
| GET | `/issues/{id}/transitions` | 当前状态可执行的流转动作 |
| POST | `/issues/{id}/transitions` | 推进整改状态（越级流转返回 400） |
| POST | `/issues/{id}/records` | 追加跟进记录（不改变状态） |
| GET | `/stats/overview` | 核心指标 |
| GET | `/stats/dashboard` | 看板聚合数据（趋势、分布、区域、排行、最新记录） |
| GET | `/vendors` | 外包单位分页查询（关键字/状态） |
| POST | `/vendors` | 登记外包单位，编号留空自动生成 `WB-0001` |
| GET/PATCH/DELETE | `/vendors/{id}` | 单位详情（年度合同与结算汇总）/ 更新 / 删除（有合同返回 409） |
| GET | `/vendors/meta/options` | 单位下拉选项 |
| GET | `/contracts` | 合同分页查询（单位/状态/服务范围/关键字） |
| POST | `/contracts` | 登记合同：承包单位、服务范围、期限、月度费用，自动生成 `HT-0001` |
| GET | `/contracts/{id}` | 合同详情，含服务公厕与逐月费用台账汇总 |
| PATCH/DELETE | `/contracts/{id}` | 更新 / 删除（已有结算记录返回 409） |
| GET | `/contracts/covering/{restroom_id}` | 服务范围覆盖指定公厕的合同 |
| GET | `/settlements` | 月度结算台账查询（合同/单位/状态/月份/月份区间/关键字） |
| GET | `/settlements/preview?contract_id=&period_month=` | 考核扣款测算，不写库 |
| POST | `/settlements` | 按合同+月份登记结算单（待考核），重复登记返回 400 |
| GET | `/settlements/{id}` | 结算单详情，含扣款构成、巡查与问题逐笔快照 |
| POST | `/settlements/{id}/assess` | 执行/重新执行月度考核，按当期数据计算并固化扣款 |
| POST | `/settlements/{id}/manual` | 登记其他扣款调整（可负，代表核增奖励） |
| GET/POST | `/settlements/{id}/transitions` | 可执行动作 / 状态流转（考核、结算、退回、撤销） |
| DELETE | `/settlements/{id}` | 删除结算单（已结算需先撤销） |
| GET | `/settlements/trace/inspection/{id}` | 巡查记录反向追溯其计入的考核结算单 |
| GET | `/settlements/trace/issue/{id}` | 问题记录反向追溯其产生的结算扣款 |
| GET | `/meta/dictionaries` | 枚举字典（状态、分类、程度、检查项、流转规则、外包状态、扣款规则） |
| GET | `/meta/restroom-options` | 公厕下拉选项 |
| GET | `/health` | 健康检查 |

## 业务规则

- **巡查评分**：8 个检查项各 0-10 分，得分 = 总得分 / 满分 × 100；≥90 优秀、≥80 良好、≥70 合格，其余不合格。任一检查项低于 6 分或等级为不合格时，巡查结论自动置为「发现问题」。
- **问题编号**：`WT-` + 上报日期 + 当日三位流水号。
- **整改闭环**：`待整改 → 整改中 → 待验收 → 已完成 → 已关闭`；`待验证` 阶段可被驳回退回 `整改中`，`待整改/整改中` 可直接作废关闭。每次流转都会写入一条整改流水（动作、原状态、新状态、操作人、说明），详情页以时间线呈现。
- **超期预警**：整改期限早于当前时间且状态仍处于未闭环（待整改/整改中/待验收）时，列表与详情页显示「已超期」，看板统计超期数量。
- **删除保护**：删除公厕时若已存在巡查或问题记录，接口返回 409 并提示数量，需要显式 `force=true` 才会级联删除；前端会二次确认。
- **服务范围**：合同支持「按区域」（勾选一个或多个行政区，覆盖区域内全部公厕）与「指定公厕」（多选具体公厕）两种范围；巡查与问题数据均按合同范围 + 考核周期取数。
- **月度考核扣款**：`应结算金额 = 月度费用 − 质量扣款 − 问题扣款 − 超期扣款 − 其他调整`（不低于 0）。
  - 质量扣款：当月巡查均分 ≥90 不扣；80–90 扣月费 1%；70–80 扣 3%；低于 70 扣 8%。
  - 问题扣款：当月新增问题按严重程度逐条扣款（一般 50 元 / 严重 150 元 / 紧急 300 元）。
  - 超期扣款：截至考核时仍超期未闭环（待整改/整改中/待验收且已过整改期限）的问题，每条追加 200 元。
  - 其他调整：人工登记的扣款或核增奖励，需填写说明。
- **结算流程**：`待考核 → 已考核 → 已结算`；已考核可退回待考核重做，已结算可撤销回已考核。已结算后金额锁定，不能再调整或删除。
- **双向追溯**：考核时将每一条纳入的巡查、问题连同得分、状态、扣款金额固化为快照；结算单详情可下钻到原始巡查/问题，巡查详情与问题详情可反查其被哪一期结算单计入、扣了多少款。即使原始记录之后变化，历史结算金额仍以快照为准。
- **合同期限**：「履行中」的合同到期后列表与详情自动显示为「已到期」，无需人工维护；手动「已终止」的合同不再自动变化。

## 演示数据

`SEED_ON_STARTUP=true`（默认）且数据库为空时，会自动写入：10 座公厕（4 个区域、三类等级、含维修/停用状态）、近 45 天约 280 条巡查记录、40 条不同整改阶段的问题及其完整整改轨迹；3 家外包单位与 3 份服务范围不同的外包合同，近两个月共 6 张月度结算单（涵盖已结算/已考核/待考核三种状态，含质量、问题、超期三类扣款）。数据由固定随机种子生成，结果可复现；如需重置，删除 `backend/data/app.db`（或 `docker compose down -v`）后重启即可。

## 测试与验证

```bash
cd backend && pytest -q          # 接口测试（覆盖台账 CRUD、删除保护、评分、流程流转、统计、外包单位/合同/考核扣款/双向追溯）
cd frontend && npm run build     # 生产构建
```

本项目完成时已实际运行验证：

- 后端 `pytest`：11 个用例全部通过（含外包单位 CRUD 与删除保护、合同范围与期限校验、考核扣款计算、其他调整、结算状态流转与锁定、结算金额双向追溯、优质服务零扣款、合同台账汇总）；`/health`、台账/巡查/问题/统计/字典及外包单位/合同/结算接口均返回预期数据。
- 前端 `npm run build`：构建成功（80 个模块）。
- 接口端到端验证（带演示数据启动 Uvicorn + curl 实调）：单位/合同/结算列表与详情、扣款测算、合同覆盖公厕反查、问题→结算单反向追溯均返回正确数据，6 张演示结算单扣款构成（质量/问题/超期）计算无误。
- 浏览器端到端验证（Chromium 无头模式，覆盖 10 个场景）：看板渲染与趋势图、台账列表筛选、新增公厕表单提交、公厕详情三个页签、巡查列表、巡查评分表单联动（拉低单项分数后结论文案实时变化）、提交巡查记录、问题列表状态筛选、问题整改流转（真实写入并在时间线新增节点）、从巡查记录跳转上报问题（自动带入公厕与关联巡查记录）。全程无控制台报错。
- Docker Compose：`docker compose up -d --build` 后 `db`、`backend`、`frontend` 三个容器均达到 healthy，通过 Nginx 访问前端并调用 `/api/v1/*` 数据正常，即容器化链路（Nginx → FastAPI → PostgreSQL）完整可用。

## 常见问题

- **端口被占用**：若 8000/8080 已被占用，可用覆盖文件改端口，例如 `docker compose -f docker-compose.yml -f override.yml up -d`，其中 `override.yml` 写 `services: { backend: { ports: ["8010:8000"] } }`。
- **想看 SQLite 而不是 PostgreSQL**：把 `backend` 服务的 `DATABASE_URL` 改为 `sqlite:///./data/app.db` 即可，无需 `db` 服务。
- **接口 422**：后端把参数校验错误统一转成中文可读文案，前端会直接弹出提示，例如「参数校验失败 - name: String should have at least 1 character」。
- **越级流转报错**：属于预期行为，接口会返回当前状态允许流转的目标状态列表，前端也只会展示合法动作。
