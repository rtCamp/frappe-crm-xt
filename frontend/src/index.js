/**
 * frappe_crm_xt — IIFE frontend bundle
 *
 * Injected into the FCRM SPA page via <script defer>.  Mounts a Vue 3 app
 * on a portal div: sidebar list views, the Events tab and the follow button.
 */
import { createApp } from 'vue'
import App from './components/App.vue'
// Global styles for the bundle — Vite extracts these into the built CSS file
// (frappe-crm-xt-frontend.css), so we get HMR, linting, and proper editor
// syntax highlighting instead of a template-string blob.
import './styles/bundle.css'

function mount() {
  const el = document.createElement('div')
  el.id = 'crm-xt-app'
  document.body.appendChild(el)
  createApp(App).mount(el)
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mount)
} else {
  mount()
}
