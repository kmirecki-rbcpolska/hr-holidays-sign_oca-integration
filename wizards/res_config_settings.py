from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    time_off_signed_document_notification_emails = fields.Char(
        string="Signed Time Off Document Emails",
        config_parameter=(
            "hr_holidays_sign_oca_integration.signed_document_notification_emails"
        ),
        help="Additional email addresses that should receive signed time off documents. Use commas or semicolons.",
    )