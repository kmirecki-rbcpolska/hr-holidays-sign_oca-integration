# -*- coding: utf-8 -*-

{
    "name": "Time Off Sign Integration",
    "summary": "Generate and sign leave requests with OCA Sign",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Kacper Mirecki",
    "depends": ["hr_holidays", "sign_oca"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/hr_leave_sign_request_wizard_views.xml",
        "views/sign_oca_template_views.xml",
        "views/hr_leave_views.xml",
    ],
    "installable": True,
    "application": False,
}
