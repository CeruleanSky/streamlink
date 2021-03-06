import json
import logging
import re

from streamlink.plugin import Plugin
from streamlink.plugin.api import validate
from streamlink.stream import HLSStream, HTTPStream
from streamlink.utils import update_scheme

log = logging.getLogger(__name__)


class INE(Plugin):
    url_re = re.compile(r"""https://streaming\.ine\.com/play\#?/
            ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/?
            (.*?)""", re.VERBOSE)
    play_url = "https://streaming.ine.com/play/{vid}/watch"
    js_re = re.compile(r'''script type="text/javascript" src="(https://content\.jwplatform\.com/players/.*?)"''')
    jwplayer_re = re.compile(r'''jwConfig\s*=\s*(\{.*\});''', re.DOTALL)
    setup_schema = validate.Schema(
        validate.transform(jwplayer_re.search),
        validate.any(
            None,
            validate.all(
                validate.get(1),
                validate.transform(json.loads),
                {"playlist": validate.text},
                validate.get("playlist")
            )
        )
    )

    @classmethod
    def can_handle_url(cls, url):
        return cls.url_re.match(url) is not None

    def _get_streams(self):
        vid = self.url_re.match(self.url).group(1)
        log.debug("Found video ID: {0}".format(vid))

        page = self.session.http.get(self.play_url.format(vid=vid))
        js_url_m = self.js_re.search(page.text)
        if js_url_m:
            js_url = js_url_m.group(1)
            log.debug("Loading player JS: {0}".format(js_url))

            res = self.session.http.get(js_url)
            metadata_url = update_scheme(self.url, self.setup_schema.validate(res.text))
            data = self.session.http.json(self.session.http.get(metadata_url))

            for source in data["playlist"][0]["sources"]:
                if source["type"] == "application/vnd.apple.mpegurl":
                    yield from HLSStream.parse_variant_playlist(self.session, source["file"]).items()
                elif source["type"] == "video/mp4":
                    yield "{0}p".format(source["height"]), HTTPStream(self.session, source["file"])


__plugin__ = INE
