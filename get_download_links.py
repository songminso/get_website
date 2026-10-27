import argparse
import codecs
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen


DOWNLOAD_EXTENSIONS = {
    ".7z",
    ".apk",
    ".avi",
    ".bz2",
    ".csv",
    ".conda",
    ".doc",
    ".docx",
    ".exe",
    ".gz",
    ".iso",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".tar",
    ".txt",
    ".wav",
    ".xls",
    ".xlsx",
    ".zip",
}


class DownloadLinkParser(HTMLParser):
    def __init__(self, extensions=None, all_links=False):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.extensions = extensions or DOWNLOAD_EXTENSIONS
        self.all_links = all_links

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return

        attributes = dict(attrs)
        href = attributes.get("href")
        if not href:
            return

        path = urlparse(href).path.lower()
        if (
            self.all_links
            or "download" in attributes
            or any(path.endswith(ext) for ext in self.extensions)
        ):
            self.links.append(href)


def get_download_links(page_url, timeout=60, extensions=None, all_links=False):
    parser = DownloadLinkParser(extensions=extensions, all_links=all_links)
    final_url = page_url
    charset = "utf-8"
    try:
        request = Request(page_url, headers={"User-Agent": "Mozilla/5.0 (compatible; LinkExtractor/1.0)"})
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            final_url = response.geturl()
            decoder = codecs.getincrementaldecoder(charset)(errors="replace")
            while chunk := response.read(64 * 1024):
                parser.feed(decoder.decode(chunk))
            parser.feed(decoder.decode(b"", final=True))
    except (URLError, OSError):
        curl_path = shutil.which("curl.exe") or shutil.which("curl")
        if not curl_path:
            raise

        process = subprocess.Popen(
            [curl_path, "-fLsS", "--max-time", str(timeout), page_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        decoder = codecs.getincrementaldecoder(charset)(errors="replace")
        while chunk := process.stdout.read(64 * 1024):
            parser.feed(decoder.decode(chunk))
        parser.feed(decoder.decode(b"", final=True))
        _, error_output = process.communicate()
        if process.returncode:
            raise OSError(error_output.decode(errors="replace"))

    links = []
    seen = set()
    for href in parser.links:
        absolute_url = urldefrag(urljoin(final_url, href))[0]
        if absolute_url not in seen:
            seen.add(absolute_url)
            links.append(absolute_url)
    return links


def main():
    argument_parser = argparse.ArgumentParser(
        description="提取网页中的下载链接并保存到文本文件。"
    )
    argument_parser.add_argument("url", help="要解析的网页 URL")
    argument_parser.add_argument(
        "-o", "--output", default="download_links.txt", help="输出文件路径"
    )
    argument_parser.add_argument(
        "-t", "--timeout", type=int, default=60, help="网络读取超时秒数（默认：60）"
    )
    argument_parser.add_argument(
        "-e",
        "--extensions",
        nargs="+",
        metavar="EXT",
        help="自定义文件扩展名，例如：-e .zip .conda .tar.bz2",
    )
    argument_parser.add_argument(
        "--all-links",
        action="store_true",
        help="提取页面中所有链接，而不只筛选下载链接",
    )
    args = argument_parser.parse_args()

    if urlparse(args.url).scheme not in {"http", "https"}:
        argument_parser.error("URL 必须以 http:// 或 https:// 开头")
    if args.timeout <= 0:
        argument_parser.error("--timeout 必须是大于 0 的整数")

    extensions = None
    if args.extensions:
        extensions = {
            extension.lower()
            if extension.startswith(".")
            else f".{extension.lower()}"
            for extension in args.extensions
        }

    try:
        links = get_download_links(
            args.url,
            timeout=args.timeout,
            extensions=extensions,
            all_links=args.all_links,
        )
        with open(args.output, "w", encoding="utf-8") as output_file:
            output_file.write("\n".join(links))
            if links:
                output_file.write("\n")
    except (URLError, OSError, UnicodeError) as error:
        print(f"获取网页或写入文件失败：{error}", file=sys.stderr)
        return 1

    print(f"提取到 {len(links)} 个链接，已写入：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())