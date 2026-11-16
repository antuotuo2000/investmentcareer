#!/usr/bin/env python3
"""Open the persistent local homepage and keep its disk index up to date."""
from pathlib import Path
import time
import webbrowser
from build_snapshot import build_snapshot

DOCS = Path(__file__).resolve().parent / "docs"


def directory_version():
    return tuple(sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size)
                        for p in (DOCS / "Components").iterdir()
                        if p.is_file() and not p.is_symlink()
                        and p.suffix.lower() in (".html", ".htm")))


def main():
    version = directory_version()
    count = build_snapshot()
    url = (DOCS / "index.html").as_uri()
    print("已保存 " + str(count) + " 份财报的本地索引。\n主页：" + url +
          "\n关闭此窗口后，已收录财报仍可阅读、刷新和重新打开。" +
          "\n保持窗口开启可自动收录新文件；按 Ctrl+C 停止自动收录。", flush=True)
    webbrowser.open(url)
    try:
        while True:
            time.sleep(2)
            try:
                current = directory_version()
                if current != version:
                    count = build_snapshot()
                    version = current
                    print("已保存最新索引：" + str(count) + " 份财报", flush=True)
            except OSError as error:
                print("文件暂时无法读取，将重试：" + str(error), flush=True)
    except KeyboardInterrupt:
        print("自动收录已停止，已保存的财报继续可用。", flush=True)


if __name__ == "__main__":
    main()
