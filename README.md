# podcast-feed

> 自托管 RSS feeds for Spotify / Apple Podcasts / Amazon Music
> 用 GitHub Pages 免费分发，无需付费 RSS 服务

## 节目列表

| Show | Language | Feed URL | Status |
|---|---|---|---|
| Night Refuge | en-US | `/shows/night-refuge-en/feed.xml` | 🟢 |
| 夜栖 - 成人助眠故事 | zh-CN | `/shows/night-refuge-zh/feed.xml` | ⏳ |
| Star Mirror | en-US | `/shows/star-mirror-en/feed.xml` | ⏳ |
| 星泽 - 心灵护身电台 | zh-CN | `/shows/star-mirror-zh/feed.xml` | ⏳ |

## 目录结构

```
podcast-feed/
├── gen_rss.py                       # 扫描 yaml + mp3 → 生成 feed.xml
├── .github/workflows/rebuild-feeds.yml
└── shows/
    ├── night-refuge-en/
    │   ├── show.yaml                # 节目级元数据
    │   ├── cover.jpg                # 1400×1400 ≤ 500KB
    │   ├── feed.xml                 # ⭐ RSS feed (Spotify/Apple 抓这个)
    │   └── episodes/
    │       ├── N01.mp3              # 14 MB
    │       ├── N01.yaml
    │       ├── N02.mp3
    │       └── N02.yaml
    └── ...
```

## 添加新集（手动）

1. 把 `N0X.mp3` 放进对应 show 的 `episodes/` 文件夹
2. 创建对应 `N0X.yaml`（参考 N01.yaml）
3. `git commit + push`
4. GitHub Actions 自动跑 `gen_rss.py --all` → 更新所有 feed.xml → push 回 main
5. Spotify / Apple / Amazon **5-60 分钟内自动抓取新集**

## 添加新集（agent 自动 — 未来）

```python
# enterprise pipeline publish_episode.py
import shutil
from pathlib import Path

def publish_episode(show_id, episode_id, mp3_path, metadata):
    repo = Path("/home/nix/projects/data/output/stories-channel/_shared/podcast-feed")
    target = repo / "shows" / show_id / "episodes"
    shutil.copy(mp3_path, target / f"{episode_id}.mp3")
    write_yaml(target / f"{episode_id}.yaml", metadata)
    # git commit + push
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", f"add {show_id}/{episode_id}"], check=True)
    subprocess.run(["git", "-C", str(repo), "push"], check=True)
```

## 本地测试 gen_rss.py

```bash
pip install pyyaml
python3 gen_rss.py --show night-refuge-en
python3 gen_rss.py --all  # 重生所有 show
python3 gen_rss.py --all --base-url https://localhost  # 本地测试用
```

## Spotify / Apple / Amazon 提交流程

### Spotify for Creators
1. 删除当前的"原生 hosting" show（如有）
2. https://creators.spotify.com/ → 「Add or claim an existing podcast」
3. 粘贴 RSS URL：`https://uxth.github.io/podcast-feed/shows/night-refuge-en/feed.xml`
4. Spotify 抓你 RSS 上最新集做"验证集"，给你邮箱发 8 位验证码
5. 粘贴验证码 → 认领完成

### Apple Podcasts Connect
1. https://podcastsconnect.apple.com/ → Sign in with Apple ID
2. 「+ New Show」→ 选 "I have a podcast hosted somewhere else"
3. 粘贴 RSS URL → Apple 审核 2-7 天 → 上线

### Amazon Music for Podcasters
1. https://podcasters.amazon.com/ → Login with Amazon
2. 「Add Your Podcast」→ 粘 RSS URL
3. 通常 1-3 天审核

### iHeartRadio for Podcasters
1. https://www.iheart.com/content/iheartradio-podcasters/
2. 同样粘 RSS URL 提交

## RSS feed 字段对照（iTunes / Spotify 必填）

| 必填项 | yaml 字段 | RSS 标签 |
|---|---|---|
| 节目名 | `title` | `<title>` + `<itunes:title>` |
| 描述 | `description` | `<description>` (CDATA) + `<itunes:summary>` |
| 语言 | `language` | `<language>` (RFC 5646: en-us / zh-cn) |
| 作者 | `author` | `<itunes:author>` |
| 邮箱 | `owner_email` | `<itunes:owner><itunes:email>` |
| 封面 | `cover_image` | `<itunes:image href=...>` |
| 类别 | `itunes_category` | `<itunes:category>` |
| 显式 | `explicit` | `<itunes:explicit>` (true/false) |
| 节目类型 | `show_type` | `<itunes:type>` (episodic/serial) |

## 风险 / 限制

- ⚠️ GitHub Pages 100 GB/月带宽，每集 14MB × ~50 听众/集 = 700MB/集 × 18 集 = ~13 GB/月（很安全）
- ⚠️ GitHub 单文件 < 100 MB（mp3 14MB 没问题，**4K 视频 mp4 才会爆**）
- ⚠️ 一旦 mp3 push 到 git history，**不能完全删除**（即使你删文件，git history 仍存）。所以谨慎 push 私密内容
- ⚠️ Spotify 不直接从 GitHub Pages 抓取问题：偶尔 GitHub 边缘节点 CDN 给 5XX，Spotify 会重试 24h

## 部署到 GitHub（一次性）

```bash
# 1. 你在 GitHub 建 public repo: uxth/podcast-feed

# 2. 本地克隆 + 拷贝当前 podcast-feed/ 内容
cd /tmp
git clone https://github.com/uxth/podcast-feed.git
cp -r /home/nix/projects/data/output/stories-channel/_shared/podcast-feed/* podcast-feed/
cd podcast-feed

# 3. 首次 push
git add .
git commit -m "init: night-refuge-en N01"
git push -u origin main

# 4. GitHub 后台启用 Pages
# Settings → Pages → Source: "GitHub Actions"

# 5. 等 .github/workflows/rebuild-feeds.yml 跑完
# 5-10 min 后 https://uxth.github.io/podcast-feed/shows/night-refuge-en/feed.xml 可访问

# 6. Spotify 删旧 show，用 feed URL 重建 import-based show
```
