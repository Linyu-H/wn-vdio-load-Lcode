# 🎬 万能视频下载器

一个现代化、高颜值的视频下载工具，支持YouTube、B站等多个平台，具备独特的UI设计和流畅的用户体验。

## ✨ 核心特色

### 🎨 差异化设计
- **独家双主题系统** - 薄荷绿配色 + 明暗模式无缝切换
- **动态切片Logo** - 三块悬浮切片动画，打造专属品牌标识
- **创新左右分栏** - 桌面端操作与预览实时联动，效率翻倍
- **智能链接识别** - 平台图标自动显示，非法链接即时标红
- **拖拽批量导入** - 支持文件/文本拖拽，交互直观流畅
- **可视化画质选择** - 分段按钮替代老旧下拉框
- **实时进度推送** - WebSocket + 流动渐变进度条
- **侧滑历史抽屉** - 记录管理 + 一键重新下载

### 🌐 支持的平台
- ✅ **YouTube** - 完全支持（已验证）
- ✅ **Twitter/X, Instagram, TikTok** - 完全支持
- ⚠️ **B站（Bilibili）** - 部分支持（公开视频可用，会员视频需配置Cookie）
- 📺 **1000+平台** - 基于yt-dlp，理论支持所有yt-dlp支持的网站

> 💡 **重要**: B站等国内平台可能遇到反爬虫限制，详见 [PLATFORMS.md](./PLATFORMS.md) 了解配置方法

## 🚀 快速开始

### 环境要求
- Python 3.9+
- Node.js 16+
- npm/yarn

### 一键启动
```bash
# 使用启动脚本（推荐）
./start.sh

# 或手动启动
# 1. 启动后端
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 2. 启动前端（新终端）
cd frontend
npm run dev
```

### 访问地址
- **前端界面**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

## 📦 项目结构

```
.
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/            # API 路由
│   │   │   ├── routes.py   # 主路由（解析、下载、文件）
│   │   │   └── history.py  # 历史记录管理
│   │   ├── services/       # 业务逻辑
│   │   │   ├── downloader.py      # yt-dlp 封装
│   │   │   ├── task_manager.py    # 任务管理器
│   │   │   └── platform.py        # 平台识别
│   │   └── config.py       # 全局配置
│   ├── main.py             # FastAPI 入口
│   ├── requirements.txt    # Python 依赖
│   └── downloads/          # 下载文件存储
│
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── components/     # Vue 组件
│   │   │   ├── AppHeader.vue      # 顶部栏
│   │   │   ├── VideoLogo.vue      # 动态Logo
│   │   │   ├── InputPanel.vue     # 输入控制区
│   │   │   ├── PreviewPanel.vue   # 预览结果区
│   │   │   └── HistoryDrawer.vue  # 历史记录抽屉
│   │   ├── stores/         # Pinia 状态管理
│   │   ├── api/            # API 封装
│   │   ├── utils/          # 工具函数
│   │   ├── App.vue         # 根组件
│   │   ├── main.js         # 入口文件
│   │   └── style.css       # 全局样式
│   ├── package.json
│   └── vite.config.js
│
├── Task-tree.md            # 开发任务树
├── TEST_REPORT.md          # 测试报告
├── ui.md                   # UI 设计方案
└── start.sh                # 快速启动脚本
```

## 🎯 功能列表

### 已实现
- ✅ 视频信息解析（标题、封面、时长、画质列表）
- ✅ 多画质选择下载（音频/480P/720P/1080P/4K）
- ✅ 纯音频提取（自动转换为MP3）
- ✅ 实时下载进度推送（WebSocket）
- ✅ 下载历史记录管理
- ✅ 多链接批量输入与标签化管理
- ✅ 拖拽导入链接/文本文件
- ✅ 剪贴板快速导入
- ✅ 明暗主题切换
- ✅ 桌面端左右分栏布局
- ✅ 移动端响应式适配

### 计划中
- ⏳ 真实下载流程完整测试
- ⏳ 批量下载队列可视化
- ⏳ Docker 一键部署
- ⏳ 更多平台优化（B站headers配置等）

## 🛠️ 开发指南

### 后端开发
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt

# 运行
uvicorn main:app --reload

# 查看API文档
open http://localhost:8000/docs
```

### 前端开发
```bash
cd frontend
npm install

# 开发模式
npm run dev

# 构建生产版本
npm run build
```

### API 端点

#### 解析视频信息
```bash
POST /api/info
{
  "url": "https://www.youtube.com/watch?v=xxxxx"
}
```

#### 创建下载任务
```bash
POST /api/download
{
  "url": "https://...",
  "quality": "1080",
  "audio_only": false
}
```

#### WebSocket 进度推送
```
WS /api/ws/{task_id}
```

#### 下载文件
```
GET /api/file/{task_id}
```

#### 历史记录
```
GET /api/history
DELETE /api/history/{task_id}
DELETE /api/history
```

## 🎨 UI 设计说明

详见 [ui.md](./ui.md)，包含：
- 双主题配色系统
- 专属品牌视觉符号
- 全局层次质感升级
- 创新左右双分栏布局
- 6大独家差异化交互

## 📝 开发日志

详见 [Task-tree.md](./Task-tree.md)，包含完整的开发计划和进度追踪。

## 🧪 测试报告

详见 [TEST_REPORT.md](./TEST_REPORT.md)，包含功能测试、已知限制和待测试项。

## 📄 许可证

本项目仅供学习交流使用。

## 🙏 致谢

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 强大的视频下载工具
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的 Python Web 框架
- [Vue3](https://vuejs.org/) - 渐进式 JavaScript 框架
- [Vite](https://vitejs.dev/) - 下一代前端构建工具
