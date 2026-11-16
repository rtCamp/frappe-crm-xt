"""
Override of crm.www.crm  (our app loads after `crm` in apps.txt).

Delegates context to FCRM's controller untouched, then reads FCRM's built crm.html
from disk and splices in our <script> tags before </body> — so the hash-named Vite
bundle stays owned by FCRM.
"""

import frappe
from crm.www.crm import get_context as _crm_get_context
from crm.www.crm import get_context_for_dev  # re-exported

no_cache = 1

EXTENSION_SCRIPTS = [
	"/assets/frappe_crm_xt/js/crm_xt_app.js",
]

EXTENSION_STYLES = [
	"/assets/frappe_crm_xt/js/frappe-crm-xt-frontend.css",
]


def get_context():
	context = _crm_get_context()
	context.crm_xt_html = _render_fcrm_html_with_extensions(context)
	return context


def _render_fcrm_html_with_extensions(context) -> str:
	"""Read FCRM's crm.html, render its Jinja (boot loop etc.), inject our scripts."""

	html_path = frappe.get_app_path("crm", "www", "crm.html")
	try:
		with open(html_path, encoding="utf-8") as f:
			html = f.read()
	except OSError:
		return '<div id="app" class="h-full"></div>'

	rendered = frappe.render_template(html, context)

	css_tags = "\n".join(f'<link rel="stylesheet" href="{href}">' for href in EXTENSION_STYLES)
	js_tags = "\n".join(f'<script defer src="{src}"></script>' for src in EXTENSION_SCRIPTS)
	rendered = rendered.replace("</head>", f"{css_tags}\n</head>", 1) if "</head>" in rendered else rendered
	rendered = (
		rendered.replace("</body>", f"{js_tags}\n</body>", 1) if "</body>" in rendered else rendered + js_tags
	)

	return rendered


__all__ = ["get_context", "get_context_for_dev"]
