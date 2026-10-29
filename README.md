# PostgreSQL 文档站

本项目是一个基于 Hugo 的 PostgreSQL 中英文文档站。它将上游分章节 HTML 导入为可版本管理的页面快照，提供版本与语言切换、章节目录和站内搜索，并生成可部署到静态托管平台的网页。仓库保存文档快照，不保存完整的 PostgreSQL 或 pgdoc Git 仓库。

## 文档来源

| 语言 | 上游 | 版本来源 | 本地快照 |
| --- | --- | --- | --- |
| 英文 | [postgres/postgres](https://github.com/postgres/postgres) | `master`（站内 `devel`）、`REL_19_STABLE`、`REL_18_STABLE`、`REL_17_STABLE` | `content/en/postgresql/` |
| 中文 | [pgsty/pgdoc](https://github.com/pgsty/pgdoc) | `main` 分支的 `zh/20/`、`zh/19/`、`zh/18/`、`zh/17/`；`zh/20/` 对应站内 `devel` | `content/zh/postgresql/` |

英文手册由 PostgreSQL 源码构建，中文手册由 pgdoc 的 `zh/` 源文件构建；不会从 pgdoc 的 `docs/` 目录导入译文。当前快照对应的上游提交分别记录在 `data/manual-sources.json` 和 `data/manual-sources-zh.json`。

导入器保留原有的 `*.html` 章节地址和相对链接。章节目录位于 `data/manual_nav/` 和 `static/manual-nav/`，图片等资源位于 `static/postgresql/` 与 `static/zh/postgresql/`。站点模板、样式和交互代码分别位于 `layouts/`、`static/css/` 和 `static/js/`。

## 环境搭建

- Hugo **0.144.2**：用于生成和预览站点；可以安装到 `PATH`，也可以将可执行文件放在 `.build/hugo`。
- Python 3、Git、GNU Make：用于拉取和导入文档。
- 构建上游文档时还需要 C 编译器、Bison、Flex、`xmllint`、`xsltproc`、DocBook XML/XSL 和 `rsync`。同步命令需要访问相应的 Git 远端，pgdoc 构建可能还会下载 PostgreSQL 上游归档。

Debian/Ubuntu 可安装文档构建依赖：

```bash
sudo apt-get update
sudo apt-get install -y curl git python3 make build-essential bison flex \
  libxml2-utils xsltproc docbook-xml docbook-xsl rsync
```

Linux 可从 [Hugo 0.144.2 发布页](https://github.com/gohugoio/hugo/releases/tag/v0.144.2) 下载对应架构的二进制文件，放入本仓库的 `.build/hugo`。例如 ARM64：

```bash
mkdir -p .build
curl -fL https://github.com/gohugoio/hugo/releases/download/v0.144.2/hugo_0.144.2_linux-arm64.tar.gz \
  | tar -xz -C .build hugo
.build/hugo version
```

x86-64 将下载地址中的 `linux-arm64` 改为 `linux-amd64`。也可以把 Hugo 安装到 `PATH`。若只使用已提交的快照预览或生成网站，无须安装 DocBook 构建依赖，也无须访问上游。

## 本地预览与构建

在仓库根目录执行：

```bash
make serve                              # 预览已有快照：http://localhost:1313/
hugo --cleanDestinationDir --minify     # 只渲染已有快照，输出到 public/
make build                              # 拉取上游，按需同步中文，输出到 public/
make check                              # 运行导入和版本处理测试
```

`make build` 会临时拉取 PostgreSQL 的上述四个分支和 pgdoc 的 `main`。英文手册默认使用仓库中已提交的快照，即使上游有新提交也只提示更新；中文手册在 pgdoc 提交变化或本地快照缺失时重新导入。临时源码与构建目录在命令结束后删除，`public/` 是可忽略的生成目录。可通过 `PG_REMOTE` 和 `PGDOC_REMOTE` 指定 Git 镜像，例如 `make build PG_REMOTE=file:///path/to/postgres.git`。

若 Hugo 只安装在 `.build/hugo`，将上述直接调用的 `hugo` 命令改为 `.build/hugo`；`make` 会自动查找该路径。

## 更新或导入手册

```bash
make refresh                     # 重新生成四个英文版本并更新来源提交
make sync-pgdoc                  # pgdoc main 有变化时更新四个中文版本
make refresh-pgdoc               # 强制重新生成四个中文版本
make import-pgdoc VERSION=18     # 单独导入中文 18
make import-postgres VERSION=18 HTML_DIR=/absolute/path/to/html
```

`VERSION=devel` 对应 pgdoc 的 `zh/20/`。中文导入可用 `PGDOC_DIR=/absolute/path/to/pgdoc` 指定已检出 `main` 的本地仓库；该目录需自行更新。已有中文分章节 HTML 时，可在 `make import-pgdoc` 中传入 `HTML_DIR=/absolute/path/to/html` 跳过 pgdoc 构建。若 pgdoc 无法下载其 PostgreSQL 源码归档，可传入包含相应提交的本地仓库 `PG_SOURCE=/absolute/path/to/postgres`；单版本导入还可用 `PG_COMMIT` 指定提交，否则读取本站记录的英文来源提交。

更新后将 `content/en/`、`content/zh/`、`data/manual_nav/`、`static/manual-nav/`、`static/postgresql/`、`static/zh/postgresql/` 及两份来源提交记录一起提交。手册页面由脚本生成，应在上游修改源文档后重新导入。

## 发布

`.github/workflows/pages.yml` 每天 **00:00 UTC** 执行 `make refresh`、`make sync-pgdoc` 和 Hugo 构建；构建成功后将变化的文档快照、资源、目录和来源提交记录推送到触发 workflow 的分支，再发布到 GitHub Pages。没有文档变化时跳过提交。也可在 Actions 页面手动触发。workflow 使用 GitHub Pages 提供的站点地址设置 Hugo `baseURL`。首次使用时，在仓库 **Settings → Pages → Build and deployment → Source** 中选择 **GitHub Actions**；运行时需要允许 `GITHUB_TOKEN` 写入仓库。

也可以将 `public/` 发布到其他静态托管平台。Netlify 配置见 `netlify.toml`：站点根目录为本仓库，构建命令为 `make build`，发布目录为 `public`。
