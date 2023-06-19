from fastapi import FastAPI
from fastapi.responses import Response

import xml.etree.ElementTree as ET

import requests
import os

app = FastAPI()

OLD_BASE = os.environ.get("OLD_BASE", "https://anchor.fm/")
NEW_BASE = os.environ.get("NEW_BASE", "https://podcast.sotaproject.com/")


def replace_enclosure_urls(xml_string):
    # Parse the XML string
    root = ET.fromstring(xml_string)

    # Find all <enclosure> tags and replace the URL attribute
    for enclosure in root.iter("enclosure"):
        enclosure.attrib["url"] = enclosure.attrib["url"].replace(OLD_BASE, NEW_BASE)

    # Generate the modified XML string
    modified_xml_string = ET.tostring(root, encoding="utf-8").decode()

    return modified_xml_string


@app.get("/{url:path}")
async def proxy(url: str):
    response = requests.get(OLD_BASE + url, allow_redirects=True)

    content = response.content

    headers = {}

    if (
        response.headers.get("content-type", "application/plaintext")
        == "application/rss+xml; charset=utf-8"
    ):
        content = replace_enclosure_urls(content)

        headers["content-type"] = "application/rss+xml"

    return Response(content, headers=headers)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
