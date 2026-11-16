# investmentcareer

本地使用：双击 `启动财报主页.command`，浏览器会打开 http://127.0.0.1:8765/ 。保持启动的终端窗口开启。

将 `.html` 或 `.htm` 财报文件放入 `docs/Components`，主页启动时自动读取全部文件，并每 10 秒检查新增、修改和删除。也可以点击「检查本地更新」立即同步。无需修改 index.html 或手动维护列表。

首页从 HTML 的标题、正文、侧边栏与 KPI 卡片提取公司、摘要和全文搜索索引。建议文件名使用股票代码，标题包含公司名及 `(NASDAQ: AMD)` 这样的交易所和代码信息；缺少这些信息时仍会按文件名显示。

自动收录依赖本地服务；直接双击 index.html 无法自动枚举文件夹。网页样式和图表仍使用现有 CDN，需要网络连接。按 Ctrl+C 停止服务。也可在项目目录运行 `python3 serve.py`。

当前文件夹的全部财报也保存于 `docs/components-snapshot.js`，直接打开 `docs/index.html` 即可显示。启动服务时会自动重建这份索引；也可运行 `python3 build_snapshot.py` 手动重建。
