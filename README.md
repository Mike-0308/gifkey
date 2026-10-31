# GIF 去背景（绿幕抠像）

把带纯色背景（通常是绿幕）的 GIF / WebP 动画抠成透明背景，输出 GIF 或 WebP。
纯 CPU 的像素运算，不需要 GPU、不需要 ffmpeg，所有处理都在本机完成，文件不上传外网。

- **两种用法**：Windows 双击 `GIF去背景.bat` 直接用；或者用 Docker 跑在 NAS / 服务器上
- **实时预览**：调背景色、容差、边缘柔和度时，浏览器里即时看到抠像效果
- **四档体积优化**：从「原画质」到「极限」可选，同一段素材最大可压到 1/3
- **批量格式**：GIF（兼容性最好）或 WebP（半透明平滑、体积更小）

## 一、镜像里有什么

- 基础：`python:3.12-slim`
- 依赖：Flask + Pillow + numpy（都自带 wheel，不编译，构建约 1 分钟）
- 不需要 ffmpeg、不需要 GPU、不需要显卡驱动 —— 纯 CPU 的像素运算

镜像体积约 220MB。

## 二、镜像从哪来（三条路，选一条）

**先说结论：自用不需要发布到 GitHub，也不需要任何镜像仓库。** Docker 镜像是「本地构建、本地运行」的东西，源码在哪它就能在哪构建。GitHub 只在「想让别人也能拉」或者「想让它自动构建」时才需要。

| 方式 | 适合场景 | 需要联网拉基础镜像 | 难度 |
|---|---|---|---|
| A. NAS 上直接构建 | 只有这一台机器用（**推荐**） | 是 | 最简单 |
| B. 别处构建好，导出 tar 再传 | NAS 不方便联网 / 想省一次构建 | 否 | 中等 |
| C. 推到镜像仓库（GHCR / Docker Hub） | 多台机器部署、给别人用 | 是 | 最麻烦 |

### 方式 A：在 fnOS 上直接构建（推荐）

源码已经在你 NAS 上了，`docker compose up -d --build` 就是全部操作，见下一章。镜像只存在本机，不会上传到任何地方。

### 方式 B：构建好导出成 tar，再 load 进去

在没有 docker 的机器上不行，需要任意一台装了 Docker 的机器（Windows/Mac 装 Docker Desktop 也算）：

```bash
# ① 在那台机器上构建（把项目目录拷过去）
docker build -t gifkey:1.1 .

# ② 导出成单个文件（约 220MB，gzip 后 90MB 左右）
docker save gifkey:1.1 | gzip > gifkey-1.1.tar.gz

# ③ 传到 NAS（SMB / scp / fnOS 文件管理器都行），然后
gunzip -c gifkey-1.1.tar.gz | docker load
```

load 完直接 `docker compose up -d`（compose 里已经写了 `image: gifkey:1.1`，会直接用这个镜像，不会重新构建。**注意此时要把 compose 里的 `build:` 段删掉或注释，否则还是会走构建**）。

### 方式 C：推到镜像仓库（想让别的机器 pull 才需要）

以 GitHub Container Registry（GHCR）为例，免费、跟源码放一起：

```bash
# ① 先去 GitHub 建一个 Personal Access Token，勾选 write:packages
echo 你的TOKEN | docker login ghcr.io -u 你的GitHub用户名 --password-stdin

# ② 打标签（ghcr.io/用户名/仓库名:版本）
docker tag gifkey:1.1 ghcr.io/你的用户名/gifkey:1.1

# ③ 推送
docker push ghcr.io/你的用户名/gifkey:1.1
```

然后在 NAS 上把 compose 改成不构建、直接拉：

```yaml
services:
  gifkey:
    image: ghcr.io/你的用户名/gifkey:1.1
    # build 段删掉
```

```bash
docker compose pull && docker compose up -d
```

> ⚠️ 国内直连 `ghcr.io` 和 `docker.io` 基本都会超时。要么在 NAS 上配代理，要么改用阿里云容器镜像服务（ACR）—— 免费的个人版够用，`docker login registry.cn-hangzhou.aliyuncs.com` 推上去，拉取速度正常。

**如果你想让 GitHub 自动帮你构建**（push 代码就出新镜像），需要在仓库里加一个 workflow 文件，我可以直接给你生成，说一声即可。

## 三、部署（fnOS）

### 步骤 1：把项目放到 NAS 上

把整个 `GIF去背景` 目录传到 fnOS，比如：

```
/vol1/1000/docker/gifkey/
├── app.py
├── keying.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── static/
```

用 SMB 共享、FileBrowser，或者 `scp` 都行。`.venv/` 不用传，容器里会自己装。

### 步骤 2：启动

fnOS 的 Docker 应用里新建「Compose 项目」，把 `docker-compose.yml` 的内容粘进去，
或者在 SSH 里：

```bash
cd /vol1/1000/docker/gifkey
docker compose up -d --build
```

第一次会构建镜像（拉基础镜像 + 装依赖），大概 1~3 分钟。

### 步骤 3：访问

浏览器打开 `http://NAS的IP:8849`。

端口被占用的话，改 `docker-compose.yml` 里的两处 `8849`（左边是宿主机端口，右边是容器内端口，只改左边即可），然后 `docker compose up -d`。

## 四、目录与数据

| 宿主机 | 容器内 | 说明 |
|---|---|---|
| `./output` | `/app/output` | 处理好的成品，删容器也不会丢 |

`/app/work` 是上传缓存，容器内临时目录，不用挂出来。策略是「只保留当前这一个任务的源文件」：
新素材上传、任务处理完成、点「退出」、容器重启，四个时机都会清掉多余的。

## 五、体积优化档位

同一段素材（800×1076、30fps）实测：

| 档位 | 说明 | GIF | WebP |
|---|---|---|---|
| 原画质 | 每帧 256 色，与旧版一致 | 7.07 MB | 6.39 MB |
| 标准 | 全片共用一套调色板 | 6.59 MB (-7%) | 4.09 MB |
| 强力 | 降到 96 色 | 5.53 MB (-22%) | 3.06 MB (-57%) |
| 极限 | 64 色 + 帧率减半 | 2.33 MB (-67%) | 1.18 MB (-83%) |

外加「画面尺寸」可以再叠一层：强力档 + 50% 尺寸 = 1.53 MB（-78%）。

结论：**GIF 这个格式本身已经压不动了**。它只有 1 位透明、每帧最多 256 色，
再优化也只能在「颜色数 / 帧率 / 尺寸」三者之间换。同样的画质想要更小，
直接换 WebP —— 体积通常只有 GIF 的 1/3 到 1/2，而且透明边缘是平滑的，不会一圈锯齿。

## 六、常见问题

**打不开 8849**
先 `docker compose logs` 看容器有没有起来。健康检查失败通常是端口没对上。

**上传大文件失败**
默认上限 300MB（`app.py` 里 `MAX_CONTENT_LENGTH`），帧数上限 2000 帧。

**处理时内存飙高**
程序会把所有帧读进内存：300 帧 800×1076 大约吃 1GB，抠像时峰值 2GB 左右。
8G 内存的 NAS 够用，但不要给这个容器设 1G 以下的内存上限，否则会被 OOM 杀掉。

**「打开输出文件夹」按钮报错**
容器里没有桌面环境，这个按钮本来就没法用，点「下载文件」即可。

**中文文件名乱码**
`docker-compose.yml` 里已经设了 `TZ=Asia/Shanghai`；文件名按 UTF-8 传输，正常不会乱。
如果宿主机 SMB 挂载时用了非 UTF-8 编码，下载下来的名字可能变形，换用浏览器直接下载即可。

## 七、Windows 本地版

原来的 `GIF去背景.bat` 双击即用，逻辑与容器版完全一致（同一份代码）。
`安装依赖.bat` 会在项目下建 `.venv` 并装 `requirements.txt` 里的依赖。
