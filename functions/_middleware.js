/**
 * Cloudflare Pages Function middleware.
 * Proxies /band/{token}/images/{file} and /band/{token}/music/{file}
 * to the R2-backed media CDN.
 */

const MEDIA_BASE = 'https://internal-media.blues.ru/livebandru-media';
const MEDIA_RE = new RegExp('^/(band|club)/([^/]+)/(images|music)/([^/]+)$');

export async function onRequest(context) {
  const url = new URL(context.request.url);
  const match = url.pathname.match(MEDIA_RE);

  if (!match) return context.next();

  const [, kind, token, subdir, file] = match;
  const mediaUrl = `${MEDIA_BASE}/${kind}/${token}/${subdir}/${file}`;

  return fetch(mediaUrl, {
    method: context.request.method,
    headers: context.request.headers,
  });
}
