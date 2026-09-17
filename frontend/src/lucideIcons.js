/**
 * Curated Lucide icon set for crm_sidebar injection.
 *
 * Each icon is imported as raw SVG from lucide-static at build time.
 * Only these files are bundled — keeping the bundle lean.
 *
 * To add more icons:
 *   1. Find the name at https://lucide.dev/icons/
 *   2. Add:  import myIcon from 'lucide-static/icons/my-icon.svg?raw'
 *   3. Add the entry to the ICONS map below.
 */
import list from 'lucide-static/icons/list.svg?raw'
import users from 'lucide-static/icons/users.svg?raw'
import user from 'lucide-static/icons/user.svg?raw'
import briefcase from 'lucide-static/icons/briefcase.svg?raw'
import fileText from 'lucide-static/icons/file-text.svg?raw'
import pkg from 'lucide-static/icons/package.svg?raw'
import shoppingCart from 'lucide-static/icons/shopping-cart.svg?raw'
import tag from 'lucide-static/icons/tag.svg?raw'
import inbox from 'lucide-static/icons/inbox.svg?raw'
import phone from 'lucide-static/icons/phone.svg?raw'
import phoneCall from 'lucide-static/icons/phone-call.svg?raw'
import calendar from 'lucide-static/icons/calendar.svg?raw'
import squareCheck from 'lucide-static/icons/square-check.svg?raw'
import dollarSign from 'lucide-static/icons/dollar-sign.svg?raw'
import trendingUp from 'lucide-static/icons/trending-up.svg?raw'
import activity from 'lucide-static/icons/activity.svg?raw'
import star from 'lucide-static/icons/star.svg?raw'
import settings from 'lucide-static/icons/settings.svg?raw'
import grid from 'lucide-static/icons/grid-2x2.svg?raw'
import building from 'lucide-static/icons/building.svg?raw'
import building2 from 'lucide-static/icons/building-2.svg?raw'
import externalLink from 'lucide-static/icons/external-link.svg?raw'
import link from 'lucide-static/icons/link.svg?raw'
import layoutGrid from 'lucide-static/icons/layout-grid.svg?raw'
import database from 'lucide-static/icons/database.svg?raw'
import layers from 'lucide-static/icons/layers.svg?raw'
import zap from 'lucide-static/icons/zap.svg?raw'
import mail from 'lucide-static/icons/mail.svg?raw'
import chartBar from 'lucide-static/icons/chart-bar.svg?raw'
import clipboardList from 'lucide-static/icons/clipboard-list.svg?raw'
import contact from 'lucide-static/icons/contact.svg?raw'
import handshake from 'lucide-static/icons/handshake.svg?raw'
import target from 'lucide-static/icons/target.svg?raw'
import truck from 'lucide-static/icons/truck.svg?raw'
import warehouse from 'lucide-static/icons/warehouse.svg?raw'
import receipt from 'lucide-static/icons/receipt.svg?raw'
import circleCheck from 'lucide-static/icons/circle-check.svg?raw'
import flag from 'lucide-static/icons/flag.svg?raw'
import bookmark from 'lucide-static/icons/bookmark.svg?raw'
import search from 'lucide-static/icons/search.svg?raw'
import folder from 'lucide-static/icons/folder.svg?raw'
import check from 'lucide-static/icons/check.svg?raw'

/** Map of icon-name → raw SVG string from lucide-static */
const ICONS = {
  list: list,
  users: users,
  user: user,
  briefcase: briefcase,
  'file-text': fileText,
  package: pkg,
  'shopping-cart': shoppingCart,
  tag: tag,
  inbox: inbox,
  phone: phone,
  'phone-call': phoneCall,
  calendar: calendar,
  'square-check': squareCheck,
  'dollar-sign': dollarSign,
  'trending-up': trendingUp,
  activity: activity,
  star: star,
  settings: settings,
  'grid-2x2': grid,
  grid: grid, // alias
  building: building,
  'building-2': building2,
  'external-link': externalLink,
  link: link,
  'layout-grid': layoutGrid,
  database: database,
  layers: layers,
  zap: zap,
  mail: mail,
  'chart-bar': chartBar,
  'clipboard-list': clipboardList,
  contact: contact,
  handshake: handshake,
  target: target,
  truck: truck,
  warehouse: warehouse,
  receipt: receipt,
  'circle-check': circleCheck,
  flag: flag,
  bookmark: bookmark,
  search: search,
  folder: folder,
  check: check,
}

/**
 * Returns the raw SVG string for a Lucide icon by name.
 * Falls back to 'list' for unknown names.
 *
 * The returned string is a complete <svg>…</svg> element — set it as
 * innerHTML of a container element, or use it directly via v-html.
 */
export function getLucideIcon(name) {
  return ICONS[name] || ICONS['list']
}
