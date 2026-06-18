# 🌐 支持的视频平台及使用说明

## ✅ 已验证可用平台

### YouTube
- **状态**: ✅ 完全支持
- **测试结果**: 解析正常，下载正常
- **支持功能**: 
  - 视频信息解析
  - 多画质下载（480P/720P/1080P/4K）
  - 纯音频提取
- **测试链接**: https://www.youtube.com/watch?v=dQw4w9WgXcQ

### 其他海外平台（yt-dlp支持的）
- **Twitter/X**: ✅ 支持
- **Instagram**: ✅ 支持
- **TikTok**: ✅ 支持
- **Facebook**: ✅ 支持
- **Reddit**: ✅ 支持
- **Vimeo**: ✅ 支持

查看完整支持列表: https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md

---

## ⚠️ 特殊说明平台

### B站（Bilibili）
- **状态**: ⚠️ 部分支持
- **问题**: 
  1. **412错误**: B站有严格的反爬虫机制，部分视频会遇到"Precondition Failed"
  2. **会员专属**: 大会员专属内容需要登录cookie才能下载
  
- **解决方案**:

#### 方案1: 手动添加Cookie（推荐）
1. 浏览器登录B站账号
2. 打开开发者工具 (F12)
3. 访问任意B站视频页面
4. 在 Network 标签找到请求，复制Cookie
5. 在后端配置中添加:

```python
# backend/app/config.py
YTDLP_BASE_OPTS = {
    # ... 其他配置
    "cookiefile": "/path/to/cookies.txt",  # 或使用cookiesfrombrowser
}
```

#### 方案2: 使用浏览器Cookie（更简单）
```python
YTDLP_BASE_OPTS = {
    # ... 其他配置
    "cookiesfrombrowser": ("chrome",),  # 或 "firefox", "edge" 等
}
```

#### 方案3: 使用公开视频
- 大部分公开、非会员视频可以正常下载
- 建议先测试公开视频

### 抖音（Douyin）
- **状态**: ⚠️ 需要特殊处理
- **问题**: 国内版抖音链接格式复杂，可能需要提取真实视频ID
- **建议**: 使用TikTok国际版链接更稳定

---

## 🔧 平台支持优化建议

### 如果遇到解析失败

#### 1. 检查链接格式
确保链接是完整的视频页面URL，而不是分享链接或短链。

**正确示例**:
- ✅ `https://www.youtube.com/watch?v=xxxxx`
- ✅ `https://www.bilibili.com/video/BVxxxxxx`

**错误示例**:
- ❌ `b23.tv/xxxxx` (B站短链)
- ❌ `youtu.be/xxxxx` (YouTube短链，需展开)

#### 2. 检查视频权限
- 私密视频无法下载
- 会员专属需要登录
- 地区限制视频可能需要代理

#### 3. 更新yt-dlp版本
```bash
cd backend
source venv/bin/activate
pip install --upgrade yt-dlp
```

---

## 📝 B站Cookie配置详细步骤

### 方法1: 导出Cookie文件

1. **安装浏览器扩展**
   - Chrome: "Get cookies.txt LOCALLY"
   - Firefox: "cookies.txt"

2. **导出Cookie**
   - 登录B站
   - 点击扩展图标
   - 选择bilibili.com
   - 导出为 `cookies.txt`

3. **放置文件**
   ```bash
   cp cookies.txt backend/cookies.txt
   ```

4. **修改配置**
   ```python
   # backend/app/config.py
   YTDLP_BASE_OPTS = {
       # ...
       "cookiefile": str(BASE_DIR / "cookies.txt"),
   }
   ```

5. **重启后端**
   ```bash
   cd backend
   pkill -f uvicorn
   source venv/bin/activate
   uvicorn main:app --reload
   ```

### 方法2: 直接从浏览器读取（推荐）

修改配置文件:
```python
# backend/app/config.py
YTDLP_BASE_OPTS = {
    "noplaylist": False,
    "socket_timeout": 30,
    "retries": 3,
    "quiet": True,
    "no_warnings": True,
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.bilibili.com/",
    },
    "cookiesfrombrowser": ("chrome",),  # 使用Chrome的登录状态
}
```

支持的浏览器: `chrome`, `firefox`, `edge`, `safari`, `opera`, `brave`

---

## 🎯 推荐测试链接

### YouTube（已验证）
```
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/watch?v=jNQXAC9IVRw
```

### Twitter
```
https://twitter.com/user/status/xxxxx
```

### Instagram
```
https://www.instagram.com/p/xxxxx/
```

### TikTok（国际版）
```
https://www.tiktok.com/@username/video/xxxxx
```

---

## ❓ 常见问题

### Q: 为什么有些视频解析失败？
A: 可能原因：
1. 视频需要登录或会员权限
2. 视频被删除或设为私密
3. 平台升级了反爬虫机制
4. 网络连接问题

### Q: B站视频总是失败怎么办？
A: 
1. 先尝试公开、非会员视频
2. 如需下载会员视频，必须配置Cookie
3. 确保yt-dlp版本是最新的

### Q: 如何查看详细错误信息？
A: 查看后端日志:
```bash
# 查看运行日志
docker-compose logs -f backend  # Docker方式
# 或直接查看终端输出
```

### Q: 下载速度慢怎么办？
A: 
1. 检查网络连接
2. 某些视频服务器限速，属于正常现象
3. 可以调整config.py中的MAX_WORKERS增加并发

---

## 🔄 更新日志

**2026-06-18**
- ✅ 添加完整headers支持
- ✅ 优化User-Agent和Referer
- ✅ YouTube验证通过
- ⚠️ B站部分视频需要Cookie配置

---

## 📚 相关资源

- [yt-dlp官方文档](https://github.com/yt-dlp/yt-dlp)
- [支持的网站列表](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)
- [Cookie配置说明](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)
- [常见问题解答](https://github.com/yt-dlp/yt-dlp/wiki/FAQ)
