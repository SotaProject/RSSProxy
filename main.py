from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from urllib.parse import urlparse

from typing import Optional

from lxml import etree

import requests
import os

app = FastAPI()

OLD_BASE = os.environ.get("OLD_BASE", "https://anchor.fm/")
NEW_BASE = os.environ.get("NEW_BASE", "https://podcast.sotaproject.com/")
CLOUDFRONT_PREFIX = os.environ.get("CLOUDFRONT_PREFIX", "/staging/podcast_uploaded_")
TOKEN = os.environ.get("TOKEN", None)


def validate_url(url):
    parsed_url = urlparse(url)

    path = parsed_url.path

    if not path.lower().startswith(CLOUDFRONT_PREFIX):
        return False

    domain = parsed_url.netloc.lower()
    allowed_domain = ".cloudfront.net"

    if not domain.endswith(allowed_domain):
        return False

    file_extension = os.path.splitext(path)[1][1:]

    if file_extension.lower() not in ["jpg", "png", "jpeg", "webp"]:
        return False

    return True


def replace_urls(xml_string):
    # Parse the XML string
    root = etree.fromstring(xml_string)

    # Find all <enclosure> tags and replace the URL attribute
    for enclosure in root.xpath("//enclosure"):
        enclosure.attrib["url"] = enclosure.attrib["url"].replace(OLD_BASE, NEW_BASE)

    # Find all <atom:link> tags and replace the href attribute
    for link in root.xpath(
        "//atom:link", namespaces={"atom": "http://www.w3.org/2005/Atom"}
    ):
        link.attrib["href"] = link.attrib["href"].replace(OLD_BASE, NEW_BASE)

    # Find all <itunes:image> tags and replace the href attribute
    for link in root.xpath(
        "//itunes:image",
        namespaces={"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"},
    ):
        if not validate_url(link.attrib["href"]):
            continue
        link.attrib["href"] = (
            NEW_BASE
            + f'cloudfront?{("token=" + TOKEN + "&") if TOKEN is not None else ""}url='
            + link.attrib["href"]
        )

    # Find all <url> tags inside <image> tags and replace the text
    for url in root.xpath("//image/url"):
        if not validate_url(url.text):
            continue
        url.text = (
            NEW_BASE
            + f'cloudfront?{("token=" + TOKEN + "&") if TOKEN is not None else ""}url='
            + url.text
        )

    # Generate the modified XML string
    return etree.tostring(root, encoding=str)


@app.get("/cloudfront")
async def cloudfront(url: str, token: str | None = None):
    if TOKEN is not None and token != TOKEN:
        raise HTTPException(401)

    if not validate_url(url):
        raise HTTPException(403)

    # Make the request using requests.get
    response = requests.get(url, stream=True)

    headers = {
        "content-type": response.headers.get("content-type", "application/plaintext")
    }

    # Define a generator function to stream the response content
    def stream_generator():
        for chunk in response.iter_content(chunk_size=1024):
            yield chunk

    # Create a StreamingResponse and return it
    return StreamingResponse(stream_generator(), headers=headers)


@app.get("/{path:path}")
async def proxy(path: str, token: str | None = None):
    if TOKEN is not None and token != TOKEN:
        raise HTTPException(401)

    url = OLD_BASE + path
    response = requests.head(url, allow_redirects=True)

    headers = {
        "content-type": response.headers.get("content-type", "application/plaintext")
    }

    if headers["content-type"] == "application/rss+xml; charset=utf-8":
        response = requests.get(url, allow_redirects=True)

        content = response.content

        content = replace_urls(content)

        return Response(content, headers=headers)

    # Make the request using requests.get
    response = requests.get(url, stream=True)

    # Define a generator function to stream the response content
    def stream_generator():
        for chunk in response.iter_content(chunk_size=1024):
            yield chunk

    # Create a StreamingResponse and return it
    return StreamingResponse(stream_generator(), headers=headers)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
