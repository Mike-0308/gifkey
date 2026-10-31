# GIF 去背景（绿幕抠像）

**许可证：MIT** —— 可自由使用、修改、商用、再分发，保留版权声明即可（详见文末「许可」）。

把带纯色背景（通常是绿幕）的 GIF / WebP 动画抠成透明背景，输出 GIF 或 WebP 或 PNG。
纯 CPU 的像素运算，不需要 GPU、不需要 ffmpeg，所有处理都在本机完成，文件不上传外网。

- **两种用法**：Windows 双击 `GIF去背景.bat` 直接用；或者用 Docker 跑在 NAS / 服务器上
- **实时预览**：调背景色、容差、边缘柔和度时，浏览器里即时看到抠像效果
- **四档体积优化**：从「原画质」到「极限」，同一段素材最大可压到 1/3
- **两种输出**：GIF（兼容性最好）或 WebP（半透明平滑、体积只有 GIF 的 1/3 到 1/2）

## 仓库地址

两个站点的代码完全一致，哪个快用哪个：

| 站点 | 代码 | 镜像 |
|---|---|---|
| **Gitee**（国内推荐） | https://gitee.com/jxmike/gifkey | —（国内拉 Gitee 源码构建） |
| **GitHub** | https://github.com/Mike-0308/gifkey | `ghcr.io/mike-0308/gifkey:1.1` |

---

## 一、一键部署（推荐，不需要下载源码）

前提：机器上装了 Docker 和 Docker Compose（fnOS / 群晖 / 威联通都自带）。

```bash
# ① 建个目录当项目目录，输出文件会落在这里
mkdir -p /vol1/1000/docker/gifkey && cd /vol1/1000/docker/gifkey

# ② 拉取 compose 文件（Gitee）
curl -fsSL https://gitee.com/jxmike/gifkey/raw/main/docker-compose.yml -o docker-compose.yml

#    GitHub 版（海外或有代理时用这条）
# curl -fsSL https://raw.githubusercontent.com/Mike-0308/gifkey/main/docker-compose.yml -o docker-compose.yml

# ③ 启动（只拉镜像，几十秒；不用编译、不用装 pip 依赖）
docker compose up -d
```

然后在浏览器打开 `http://NAS的IP:8849`。

**它的原理**：compose 里写的是 `image: ghcr.io/mike-0308/gifkey:1.1`，
镜像由 GitHub Actions 在云端构建好（amd64 + arm64 双架构），你的机器只负责下载和运行。

**以后升级**：

```bash
cd /vol1/1000/docker/gifkey && docker compose pull && docker compose up -d
```

`output/` 里的成品不受影响。

> **拉不下来怎么办**：`ghcr.io` 在国内偶发抽风。见第二节「方式二」，在 NAS 上从源码构建，
> 或者给 Docker 配个加速代理。

---

## 二、完整的 Compose 文件

### 方式一：镜像版（默认，也就是上面 `curl` 下来的那个）

```yaml
services:
  gifkey:
    image: ghcr.io/mike-0308/gifkey:1.1
    container_name: gifkey
    restart: unless-stopped
    ports:
      # 左边是 NAS 上的端口（打不开就换一个），右边是容器内端口，别改
      - "8849:8849"
    volumes:
      # 成品存到当前目录下的 output/，删容器、换镜像都不会丢
      - ./output:/app/output
    environment:
      - TZ=Asia/Shanghai
      # 容器内监听端口，与上面 ports 的右边保持一致
      - GIFKEY_PORT=8849
    # 300 帧 800×1076 的素材会吃到 2GB 左右内存，别把上限设太小
    # deploy:
    #   resources:
    #     limits:
    #       memory: 4g
```

### 方式二：源码构建（GHCR 拉不动时用，也就是 `docker-compose.build.yml`）

不需要本地有源码，Docker 自己去 Git 拉（需要 Docker 23+ 的 BuildKit）：

```yaml
services:
  gifkey:
    build:
      # 国内用 Gitee（快）。拉不动就换成下面注释里的 GitHub 地址，二选一。
      context: https://gitee.com/jxmike/gifkey.git#main
      # context: https://github.com/Mike-0308/gifkey.git#main
      args:
        # 构建时走国内 pip 源，避免装依赖超时；国外可以删掉这行用官方源
        PIP_INDEX: https://mirrors.huaweicloud.com/repository/pypi/simple
    image: gifkey:1.1
    container_name: gifkey
    restart: unless-stopped
    ports:
      - "8849:8849"
    volumes:
      - ./output:/app/output
    environment:
      - TZ=Asia/Shanghai
      - GIFKEY_PORT=8849
```

```bash
curl -fsSL https://gitee.com/jxmike/gifkey/raw/main/docker-compose.build.yml -o docker-compose.yml
docker compose up -d          # 第一次 clone + 装依赖，1~3 分钟
```

### 方式三：本地目录构建（自己改了代码时用）

```yaml
services:
  gifkey:
    build:
      context: .
      args:
        PIP_INDEX: https://mirrors.huaweicloud.com/repository/pypi/simple
    image: gifkey:1.1
    container_name: gifkey
    restart: unless-stopped
    ports:
      - "8849:8849"
    volumes:
      - ./output:/app/output
    environment:
      - TZ=Asia/Shanghai
      - GIFKEY_PORT=8849
```

```bash
git clone https://gitee.com/jxmike/gifkey.git    # 或 GitHub 地址
cd gifkey
docker compose up -d --build
```

### 参数说明

| 配置项 | 作用 | 要不要改 |
|---|---|---|
| `image` | 用的镜像 | 发新版时跟着改 tag，如 `1.2` |
| `ports` 左边 `8849` | NAS 上对外暴露的端口 | 被占用就改这里，例如 `18849:8849` |
| `ports` 右边 `8849` | 容器内监听端口 | **别改**，要和 `GIFKEY_PORT` 一致 |
| `./output:/app/output` | 成品输出目录 | 想换位置就改左边的路径，如 `/vol2/gifkey-out` |
| `TZ` | 时区，影响输出目录的时间戳命名 | 默认 `Asia/Shanghai` |
| `restart` | 开机自启 / 崩溃重启 | 默认 `unless-stopped` |
| `PIP_INDEX`（构建时） | 构建时用的 pip 源 | 国内留华为云，国外可删 |
| `deploy.resources.limits.memory` | 内存上限 | 默认注释掉；要限制就别低于 4G，否则大素材会被 OOM |

`GIFKEY_HOST=0.0.0.0`、`GIFKEY_NO_BROWSER=1`、`GIFKEY_CONTAINER=1` 这三个已经写死在
镜像的 `Dockerfile` 里（容器必须监听 0.0.0.0、不能开浏览器、不能自动挪端口），compose 里不用再写。

---

## 三、镜像相关

### 镜像是怎么来的

`Dockerfile` 只是「配方」，镜像得有人构建出来再推到仓库，别人才能 `pull`。
本项目用 GitHub Actions 自动做这件事（`.github/workflows/docker-image.yml`）：

- 推代码到 `main`（且改到 `app.py` / `keying.py` / `requirements.txt` / `static/` / `Dockerfile`）→ 自动构建
- 也可以在仓库 **Actions → 构建并推送镜像 → Run workflow** 手动触发
- 一次产出 `linux/amd64` 和 `linux/arm64` 两个架构，推成两个 tag：`1.1` 和 `latest`

地址：`ghcr.io/mike-0308/gifkey:1.1`

### GHCR 匿名拉不了怎么办

GitHub 上第一次推的镜像默认是**私有**的，匿名 `docker pull` 会 401。两种解法：

**A. 把包改成公开**（一次性操作，推荐）

打开 `https://github.com/users/Mike-0308/packages/container/gifkey/settings`
→ 滑到底部 **Danger Zone → Change visibility → Public**，确认即可。

**B. 登录后拉**（不想开公开时）

在 GitHub 建 Personal Access Token，只需勾 `read:packages`，然后：

```bash
echo 你的TOKEN | docker login ghcr.io -u Mike-0308 --password-stdin
docker compose pull
```

### 其它部署方式

**离线部署（NAS 不能联网时）**

在任意一台装了 Docker 的机器上（Windows / Mac 装 Docker Desktop 也算）：

```bash
git clone https://gitee.com/jxmike/gifkey.git && cd gifkey
docker build -t gifkey:1.1 .
docker save gifkey:1.1 | gzip > gifkey-1.1.tar.gz   # 约 90MB
```

把 `gifkey-1.1.tar.gz` 传到 NAS，然后：

```bash
gunzip -c gifkey-1.1.tar.gz | docker load
```

compose 里保留 `image: gifkey:1.1`、**不要写 `build:`**，否则还会去重新构建。

**自己再发一份到别的仓库**（阿里云 ACR 等，国内更快）

```bash
docker tag gifkey:1.1 registry.cn-hangzhou.aliyuncs.com/你的命名空间/gifkey:1.1
docker login registry.cn-hangzhou.aliyuncs.com
docker push registry.cn-hangzhou.aliyuncs.com/你的命名空间/gifkey:1.1
```

### 镜像里有什么

- 基础 `python:3.12-slim`，依赖 Flask + Pillow + numpy（都是预编译 wheel，不编译）
- 不需要 ffmpeg、不需要 GPU、不需要显卡驱动
- 压缩后约 90MB，拉下来解开约 230MB

---

## 四、目录与数据

| 宿主机 | 容器内 | 说明 |
|---|---|---|
| `./output` | `/app/output` | 处理好的成品，删容器也不会丢 |
| — | `/app/work` | 上传缓存，容器内临时目录，不用挂出来 |

`work/` 的策略是「只保留当前这一个任务的源文件」：**上传新素材、处理完成、点「退出」、容器重启**，
四个时机都会清掉多余的，所以不会越积越大。

---

## 五、体积优化档位

同一段素材（800×1076、30fps、60 帧）实测：

| 档位 | 说明 | GIF | WebP |
|---|---|---|---|
| 原画质 | 每帧 256 色，与旧版一致 | 7.07 MB | 6.39 MB |
| 标准 | 全片共用一套调色板 | 6.59 MB (-7%) | 4.09 MB (-36%) |
| 强力 | 降到 96 色 | 5.53 MB (-22%) | 3.06 MB (-52%) |
| 极限 | 64 色 + 帧率减半 | 2.33 MB (-67%) | 1.18 MB (-82%) |

再加「画面尺寸」可以叠一层：强力档 + 50% 尺寸 = 1.53 MB（-78%）。

**结论：GIF 这个格式本身已经压不动了。** 它只有 1 位透明、每帧最多 256 色，
再优化只能在「颜色数 / 帧率 / 尺寸」三者之间换。同样画质想要更小，直接换 WebP。

> 试过但没用的两条路，别重复踩：`gifsicle -O3 --lossy` 只省 1~2%（变化像素分散在主体上，
> 帧差吃不到红利）；Pillow 的 `optimize=True` + 逐帧 disposal 能生成增量帧，但会重排调色板，
> 导致 11% 的像素透明索引错位。

---

## 六、常见问题

**打不开 8849**
先 `docker compose logs -f` 看容器起来没。健康检查失败通常是端口没对上。

**`docker compose up` 卡在拉镜像 / 报 `denied` 或 `unauthorized`**
镜像还是私有的，按第三节「GHCR 匿名拉不了怎么办」改成 Public 或登录。
如果是一直超时，说明 `ghcr.io` 被网络拦了，改用「方式二」源码构建。

**构建时卡在 `git clone` 不动**
Gitee 或 GitHub 那个地址当前网络拉不通。把 `context` 换成另一个站点，或者改用「方式三」本地目录构建。

**改了代码，镜像没更新**
Actions 只对 `main` 分支的特定文件变动触发。手动去 Actions 页面点一次 Run workflow。
另外别忘了升 tag（`1.1` → `1.2`），否则 NAS 上 `pull` 认为还是同一个版本，不会重新下载。

**上传大文件失败**
默认上限 300MB（`app.py` 里 `MAX_CONTENT_LENGTH`），帧数上限 2000 帧。

**处理时内存飙高**
程序会把所有帧读进内存：300 帧 800×1076 大约吃 1GB，抠像峰值 2GB 左右。
8G 内存的 NAS 够用，但不要给容器设 1G 以下的内存上限。

**「打开输出文件夹」按钮报错**
容器里没有桌面环境，这个按钮本来就没法用，点「下载文件」即可。

**中文文件名乱码**
compose 里已设 `TZ=Asia/Shanghai`，文件名按 UTF-8 传输。如果宿主机 SMB 挂载用了非 UTF-8 编码，
下载下来的名字可能变形，用浏览器直接下载即可。

---

## 七、Windows 版

### 直接下载打包好的

| 站点 | 下载地址 |
|---|---|
| **Gitee**（国内快） | https://gitee.com/jxmike/gifkey/releases/download/v1.1/gifkey-windows-v1.1.zip |
| **GitHub** | https://github.com/Mike-0308/gifkey/releases/download/v1.1/gifkey-windows-v1.1.zip |

包很小（25KB），里面是源码 + 三个 bat + 说明，不含 Python 依赖 —— 那些第一次运行时自己下。

解压后三步：

1. 双击 **`安装依赖.bat`**（只有第一次需要，联网下约 80MB，1~2 分钟）
2. 双击 **`GIF去背景.bat`**，浏览器会自动打开页面
3. 用完点网页里的「退出」，或直接关掉命令行窗口

前提：装过 Python 3.10 或更高版本（https://www.python.org/downloads/ ），
安装时务必勾选 **“Add python.exe to PATH”**，否则 `安装依赖.bat` 会提示找不到 python。

### 三个 bat 各管什么

| 文件 | 作用 |
|---|---|
| `安装依赖.bat` | 建 `.venv` 并装 flask / pillow / numpy，走华为云镜像，只跑一次 |
| `GIF去背景.bat` | 无窗口启动，浏览器自动打开；环境没装会提示你先跑上面那个 |
| `诊断启动.bat` | 带控制台启动，能看到完整报错，启动失败时用它 |

逻辑与容器版完全一致（同一份代码）。

---

## 八、文件说明

| 文件 | 作用 |
|---|---|
| `app.py` | Flask 服务：上传、任务队列、参数接口、退出 |
| `keying.py` | 抠像算法与 GIF / WebP 编码（四档压缩都在这） |
| `static/` | 前端页面 |
| `Dockerfile` | 容器镜像定义（镜像的「配方」） |
| `docker-compose.yml` | **镜像版**，一键部署拉的就是这个 |
| `docker-compose.build.yml` | 源码构建版，GHCR 拉不动时用 |
| `.github/workflows/docker-image.yml` | 自动构建并推送镜像到 GHCR |
| `requirements.txt` | Python 依赖，只有 flask / pillow / numpy |
| `LICENSE` | MIT 许可证 |
| `GIF去背景.bat` | Windows 一键启动 |
| `安装依赖.bat` | Windows 装依赖 |
| `诊断启动.bat` | Windows 排障 |

---

## 九、许可

MIT License © 2026 jxmike

你可以自由使用、修改、商用、再分发，唯一要求是保留版权声明和许可证正文。

用到的第三方组件（都兼容 MIT，可以放心一起分发）：

| 组件 | 用途 | 许可证 |
|---|---|---|
| Python 3.12 | 运行时 | PSF License |
| Flask | Web 服务 | BSD-3-Clause |
| Pillow | GIF / WebP 编码 | MIT-CMU (HPND) |
| numpy | 像素矩阵运算 | BSD-3-Clause |
| Debian (slim 基础镜像) | 容器底座 | 各自开源许可 |

本项目**没有**使用任何 GPL / AGPL 组件，所以选 MIT 不会产生传染性义务。

