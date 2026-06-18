export const PLATFORM_ICONS = {
  youtube: '▶️',
  bilibili: '📺',
  douyin: '🎵',
  twitter: '🐦',
  instagram: '📷',
  tiktok: '🎶',
  weibo: '📱',
  facebook: '👥',
  unknown: '🔗'
}

export const PLATFORM_RULES = [
  ['youtube.com', 'youtube'],
  ['youtu.be', 'youtube'],
  ['bilibili.com', 'bilibili'],
  ['b23.tv', 'bilibili'],
  ['douyin.com', 'douyin'],
  ['iesdouyin.com', 'douyin'],
  ['tiktok.com', 'tiktok'],
  ['twitter.com', 'twitter'],
  ['x.com', 'twitter'],
  ['instagram.com', 'instagram'],
  ['facebook.com', 'facebook'],
  ['weibo.com', 'weibo']
]

export function isValidUrl(str) {
  try {
    const url = new URL(str)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

export function getPlatformIcon(platform) {
  return PLATFORM_ICONS[platform] || PLATFORM_ICONS.unknown
}

export function detectPlatformFromUrl(str) {
  try {
    const host = new URL(str).hostname.toLowerCase()
    const matched = PLATFORM_RULES.find(([keyword]) => host.includes(keyword))
    return matched ? matched[1] : 'unknown'
  } catch {
    return 'unknown'
  }
}

export function getFaviconUrl(str) {
  try {
    const url = new URL(str)
    return `${url.origin}/favicon.ico`
  } catch {
    return ''
  }
}

export function getUrlHost(str) {
  try {
    return new URL(str).hostname
  } catch {
    return ''
  }
}
