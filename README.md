# 足彩预测SKIL — 自动运行项目

> GitHub Actions 每日自动预测 + GitHub Pages 发布结果 + 自学习反馈闭环

## 工作原理

```
每日 10:30 (北京时间)
    │
    ▼
┌──────────────────────┐
│ GitHub Actions 触发   │
│ daily-predict.yml     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 加载比赛列表          │
│ data/today_matches   │
│ .json                │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 运行预测引擎          │
│ football_predictor   │
│ 6组件融合            │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 生成预测页面          │
│ docs/index.html      │
│ GitHub Pages         │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 反馈闭环              │
│ 检查过往预测结果      │
│ 更新知识库            │
│ 触发自学习            │
└──────────────────────┘
```

## 快速开始

### 1. Fork 本仓库

```bash
git clone https://github.com/YOUR_USERNAME/football-prediction-auto.git
cd football-prediction-auto
```

### 2. 配置比赛列表

编辑 `data/today_matches.json`:

```json
{
  "date": "2026-05-25",
  "matches": [
    {"lg": "E0", "home": "Arsenal", "away": "Chelsea"},
    {"lg": "D1", "home": "Bayern Munich", "away": "Dortmund"},
    {"lg": "I1", "home": "Inter", "away": "Milan"},
    {"lg": "SP1", "home": "Barcelona", "away": "Real Madrid"}
  ]
}
```

### 3. 启用 GitHub Pages

Settings → Pages → Source: `gh-pages` branch → Save

### 4. 启用 GitHub Actions

Actions 标签 → 启用 workflows → 手动触发或等定时执行

## 文件结构

```
football-prediction-auto/
├── .github/workflows/
│   └── daily-predict.yml     # GitHub Actions 工作流
├── scripts/
│   ├── run_predict.py        # 每日预测主脚本
│   └── feedback_loop.py      # 自学习反馈闭环
├── data/
│   ├── today_matches.json    # 每日比赛列表
│   ├── knowledge_base.json   # 进化引擎知识库
│   └── Matches.csv           # (可选) xgabora数据
├── docs/                     # GitHub Pages 发布目录
│   ├── index.html            # 最新预测结果
│   └── archive.html          # 历史归档
├── results/                  # 原始预测JSON
└── models/                   # 模型文件
```

## 功能特性

- **全自动**: GitHub Actions 定时触发，无需人工干预
- **结果发布**: GitHub Pages 自动部署，浏览器直接查看
- **自学习**: 比赛结果反馈后自动更新融合权重
- **可追溯**: 每天预测结果 JSON 存档
- **手动触发**: 支持 workflow_dispatch 随时运行

## 预测页面

预测结果自动发布到 GitHub Pages:

```
https://YOUR_USERNAME.github.io/football-prediction-auto/
```

包含:
- 当日所有比赛预测卡片
- 胜平负概率条
- xG预期进球
- Elo差值
- 数据来源说明

## 免责声明

本系统仅供技术研究和学习参考。足球比赛存在极大的不确定性，任何预测模型都无法保证准确。理性购彩，切勿沉迷。
