export function thumbUrl(url, width) {
  if (!url) return url
  if (!url.includes('commons.wikimedia.org')) return url
  const u = new URL(url)
  u.searchParams.set('width', width)
  return u.toString()
}
