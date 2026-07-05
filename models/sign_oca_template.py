from odoo import fields, models


class SignOcaTemplate(models.Model):
    _inherit = "sign.oca.template"

    time_off_type_id = fields.Many2one(
        "hr.leave.type",
        string="Time Off Type",
        help="Restrict this template to a specific time off type.",
    )

    def _prepare_sign_oca_request_vals_from_record(self, record):
        vals = super()._prepare_sign_oca_request_vals_from_record(record)
        if record._name == "hr.leave":
            vals.update(
                {
                    "time_off_start_date": record.request_date_from,
                    "time_off_end_date": record.request_date_to,
                }
            )
        return vals