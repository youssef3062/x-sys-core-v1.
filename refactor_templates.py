import os
import re

TEMPLATE_DIR = r"c:\Users\moham\Desktop\Presentation Web - Copy\app\templates"

replacements = {
    "main.login": "auth.login",
    "main.logout": "auth.logout",
    "main.register": "auth.register",
    "main.doctor_login": "auth.doctor_login",
    "main.doctor_register": "auth.doctor_register",
    "main.operator_login": "auth.operator_login",
    "main.create_operator": "auth.create_operator",
    "main.dashboard": "patient.dashboard",
    "main.doctor_dashboard": "doctor.doctor_dashboard",
    "main.operator_dashboard": "operator.operator_dashboard",
    "main.visit_add": "patient.visit_add",
    "main.lab_upload": "patient.lab_upload",
    "main.guest_view": "patient.guest_view",
    "main.access_options": "patient.access_options",
    "main.export_visits": "patient.export_visits",
    "main.operator_link_patient": "operator.operator_link_patient",
    "main.operator_assign": "operator.operator_assign",
    "main.operator_edit": "operator.operator_edit",
    "main.admin_logs_view": "admin.admin_logs_view",
    "main.admin_connection_logs": "admin.admin_connection_logs",
    "main.admin_add_qr": "admin.admin_add_qr",
    "main.analytics_dashboard": "operator.analytics_dashboard",
    "main.scanner_gate": "common.scanner_gate",
    "main.scan_result": "common.scan_result",
    "main.photos": "common.photos",
    "main.labs": "common.labs",
    "main.static": "static"
}

def refactor_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    for old, new in replacements.items():
        # Replace 'main.endpoint' and "main.endpoint"
        # We need to be careful not to replace things that just happen to match, but in templates url_for strings are distinct.
        # We also handle leading spacing or context if needed, but simple replace should work for exact strings.
        content = content.replace(f"'{old}'", f"'{new}'")
        content = content.replace(f'"{old}"', f'"{new}"')
        
    if content != original_content:
        print(f"Updating {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

def main():
    if not os.path.exists(TEMPLATE_DIR):
        print("Template dir not found")
        return

    for root, dirs, files in os.walk(TEMPLATE_DIR):
        for file in files:
            if file.endswith(".html"):
                refactor_file(os.path.join(root, file))

if __name__ == "__main__":
    main()
