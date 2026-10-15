"""Fail deployment verification if the published page is still an older UI."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
import time
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from urllib.request import Request, urlopen
from urllib.error import URLError

EXPECTED = {"trend-content", "company-content", "performance-content"}


class Panels(HTMLParser):
    def __init__(self):
        super().__init__()
        self.controls = set()
        self.collapsed = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "button" and values.get("aria-expanded") == "false":
            target = values.get("data-section-toggle")
            if target and values.get("aria-controls") == target:
                self.controls.add(target)
        if "hidden" in values and values.get("id") in EXPECTED:
            self.collapsed.add(values["id"])


def verify(content):
    parser = Panels()
    parser.feed(content)
    if not EXPECTED <= parser.controls or parser.collapsed != EXPECTED:
        raise ValueError("게시된 페이지에 3개 보기/접기 버튼과 초기 접힘 상태가 아직 반영되지 않았습니다.")


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url")
    source.add_argument("--file", type=Path)
    parser.add_argument("--revision", default="check")
    args = parser.parse_args()
    if args.file:
        verify(args.file.read_text(encoding="utf-8"))
        print("Local build contains all three collapsed analysis sections.")
        return
    parts = urlsplit(args.url)
    query = urlencode([*parse_qsl(parts.query), ("deployment", args.revision)])
    url = urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))
    for attempt in range(8):
        try:
            request = Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "OLED-Pages-Verification"})
            with urlopen(request, timeout=10) as response:
                verify(response.read().decode("utf-8"))
            print("Published page contains all three collapsed analysis sections.")
            return
        except (URLError, OSError, ValueError) as exc:
            print(f"Publication check {attempt + 1}/8: {exc}")
            if attempt == 7:
                raise SystemExit("실제 사이트에서 최신 화면을 확인하지 못했습니다. Pages 게시 상태를 확인해 주세요.")
            time.sleep(5)


if __name__ == "__main__":
    main()
