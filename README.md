# GIF 去背景（绿幕抠像）

把带纯色背景（通常是绿幕）的 GIF / WebP 动画抠成透明背景，输出 GIF 或 WebP 或 PNG。
纯 CPU 的像素运算，不需要 GPU、不需要 ffmpeg，所有处理都在本机完成，文件不上传外网。

- **两种用法**：Windows 双击 `GIF去背景.bat` 直接用；或者用 Docker 跑在 NAS / 服务器上
- **实时预览**：调背景色、容差、边缘柔和度时，浏览器里即时看到抠像效果
- **四档体积优化**：从「原画质」到「极限」，同一段素材最大可压到 1/3
- **两种输出**：GIF（兼容性最好）或 WebP（半透明平滑、体积只有 GIF 的 1/3 到 1/2）

## 仓库地址

两个站点的代码完全一致，哪个快用哪个：

| 站点 | 地址 |
|---|---|
| **Gitee**（国内推荐） | https://gitee.com/jxmike/gifkey |
| **GitHub** | https://github.com/Mike-0308/gifkey |

下面的所有命令都给了两个站点两套，任选其一即可。

---

## 一、一键部署（推荐，不需要下载源码）

前提：机器上装了 Docker 和 Docker Compose（fnOS / 群晖 / 威联通都自带）。

```bash
# ① 建个目录当项目目录，输出文件会落在这里
mkdir -p /vol1/1000/docker/gifkey && cd /vol1/1000/docker/gifkey

# ② 拉取 compose 文件（Gitee）
curl -fsSL https://gitee.com/jxmike/gifkey/raw/main/docker-compose.remote.yml -o docker-compose.yml

#    GitHub 版（海外或有代理时用这条）
# curl -fsSL https://raw.githubusercontent.com/Mike-0308/gifkey/main/docker-compose.remote.yml -o docker-compose.yml

# ③ 启动（第一次会 clone 源码 + 构建镜像，1~3 分钟）
docker compose up -d
```

然后在浏览器打开 `http://NAS的IP:8849`。

**它的原理**：compose 里的 `build.context` 指向 Git 仓库地址，Docker 会自己 `clone` 下来再构建，
所以你不需要把源码拷到 NAS 上，只需要一个 compose 文件。

> 不想用命令行也可以：fnOS 的「Docker → Compose → 新建项目」里，把下面第二节「方式一」的
> 完整内容粘进去，点部署就行，效果一样。

**以后升级**：

```bash
cd /vol1/1000/docker/gifkey && docker compose up -d --build
```

会重新拉最新源码构建，`output/` 里的成品不受影响。

---

## 二、完整的 Compose 文件

两种都可用，按你的网络情况选一个。

### 方式一：远程源码构建（推荐，配合上面的一键部署）

不需要本地有源码，Docker 自己去 Git 拉。**这就是上面 `curl` 下来的那个文件。**

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
      # 左边是 NAS 上的端口（打不开就换一个），右边是容器内端口，别改
      - "8849:8849"
    volumes:
      # 成品存到当前目录下的 output/，删容器、重建镜像都不会丢
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

### 方式二：本地目录构建

适合把仓库 `git clone` 或下载 zip 到本机的情况，构建时用本地的 `Dockerfile`，不联网拉源码。

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

用法：

```bash
git clone https://gitee.com/jxmike/gifkey.git    # 或 GitHub 地址
cd gifkey
docker compose up -d --build
```

### 参数说明

| 配置项 | 作用 | 要不要改 |
|---|---|---|
| `ports` 左边 `8849` | NAS 上对外暴露的端口 | 被占用就改这里，例如 `18849:8849` |
| `ports` 右边 `8849` | 容器内监听端口 | **别改**，要和 `GIFKEY_PORT` 一致 |
| `./output:/app/output` | 成品输出目录 | 想换位置就改左边的路径，如 `/vol2/gifkey-out` |
| `TZ` | 时区，影响输出目录的时间戳命名 | 默认 `Asia/Shanghai` |
| `restart` | 开机自启 / 崩溃重启 | 默认 `unless-stopped` |
| `PIP_INDEX` | 构建时用的 pip 源 | 国内留华为云，国外可删 |
| `deploy.resources.limits.memory` | 内存上限 | 默认注释掉；要限制就别低于 4G，否则大素材会被 OOM |

`GIFKEY_HOST=0.0.0.0`、`GIFKEY_NO_BROWSER=1`、`GIFKEY_CONTAINER=1` 这三个已经写死在
镜像的 `Dockerfile` 里（容器必须监听 0.0.0.0、不能开浏览器、不能自动挪端口），compose 里不用再写。

---

## 三、其它部署方式

### 方式 A：离线部署（NAS 不能联网时）

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

再用上面「方式二」的 compose，**但要把 `build:` 整段删掉**，只留 `image: gifkey:1.1`，
否则 compose 还会去重新构建。

### 方式 B：推到镜像仓库（多台机器、给别人用）

```bash
# ① GitHub 建 Personal Access Token，勾 write:packages
echo 你的TOKEN | docker login ghcr.io -u 你的GitHub用户名 --password-stdin

# ② 打标签并推送
docker tag gifkey:1.1 ghcr.io/你的用户名/gifkey:1.1
docker push ghcr.io/你的用户名/gifkey:1.1
```

然后 compose 里换成 `image: ghcr.io/你的用户名/gifkey:1.1`、删掉 `build:` 段，
`docker compose pull && docker compose up -d`。

> ⚠️ 国内直连 `ghcr.io` 和 `docker.io` 基本都会超时。要么配代理，要么用阿里云容器镜像服务（ACR，个人版免费）。

### 镜像里有什么

- 基础 `python:3.12-slim`，依赖 Flask + Pillow + numpy（都是预编译 wheel，不编译）
- 不需要 ffmpeg、不需要 GPU、不需要显卡驱动
- 镜像体积约 230MB

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

**构建时卡在 `git clone` 不动**
Gitee 或 GitHub 那个地址当前网络拉不通。把 `context` 换成另一个站点，或者改用「方式二」本地目录构建。

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

## 七、Windows 本地版

双击 `GIF去背景.bat` 即用，逻辑与容器版完全一致（同一份代码）。
`安装依赖.bat` 会在项目下建 `.venv` 并装 `requirements.txt` 里的依赖。

`诊断启动.bat` 用于排查启动失败，会把 Python 版本、依赖状态、端口占用情况打出来。

---

## 八、文件说明

| 文件 | 作用 |
|---|---|
| `app.py` | Flask 服务：上传、任务队列、参数接口、退出 |
| `keying.py` | 抠像算法与 GIF / WebP 编码（四档压缩都在这） |
| `static/` | 前端页面 |
| `Dockerfile` | 容器镜像定义 |
| `docker-compose.yml` | 本地目录构建用 |
| `docker-compose.remote.yml` | 远程源码构建用（一键部署拉的就是这个） |
| `requirements.txt` | Python 依赖，只有 flask / pillow / numpy |
| `GIF去背景.bat` | Windows 一键启动 |
| `安装依赖.bat` | Windows 装依赖 |
| `诊断启动.bat` | Windows 排障 |
