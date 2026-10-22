import frappe


def run():
	frappe.set_user("Administrator")
	from frappe_crm_xt.api.gmail_linker import search_candidate_threads

	r = search_candidate_threads("CRM Deal", "CRM-DEAL-2026-00062")
	print("rows:", len(r))
	for row in r[:3]:
		print(
			" ",
			row["name"],
			"|",
			row["num_emails"],
			"|",
			row["last_email_on"],
			"| can_open_gmail=",
			row["can_open_gmail"],
		)
