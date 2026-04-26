/**
 * LiveBand.Ru media proxy Worker.
 *
 * Rewrites /band/{token}/images/{file} and /club/{token}/images/{file}
 * to the R2-backed CDN, then streams the response back verbatim.
 *
 * All Cloudflare features (range requests, conditional GETs, cache-control,
 * content-type) work automatically because we forward the original request
 * headers and return the CDN response unmodified.
 *
 * Deploy: wrangler deploy
 * Route:  www.liveband.ru/band/*/images/*  (set in Cloudflare dashboard or wrangler.toml)
 */

const MEDIA_BASE = 'https://internal-media.blues.ru/livebandru-media';

// URL patterns that map to R2 files at livebandru-media/{kind}/{token}/{file}:
//   /band/{token}/images/{file}  — band photos
//   /club/{token}/images/{file}  — club photos
//   /band/{token}/music/{file}   — band MP3s (relative links from /band/{token}/music/ page)
const MEDIA_RE = new RegExp('^/(band|club)/([^/]+)/(images|music)/([^/]+)$');

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const match = url.pathname.match(MEDIA_RE);

    if (!match) {
      return fetch(request);
    }

    const [, kind, token, file] = match;
    const mediaUrl = `${MEDIA_BASE}/${kind}/${token}/${file}`;

    // Forward original headers so Range, If-None-Match, etc. pass through.
    return fetch(mediaUrl, {
      method: request.method,
      headers: request.headers,
    });
  },
};
