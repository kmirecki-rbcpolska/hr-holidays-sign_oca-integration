from odoo import fields, models


class SignOcaTemplate(models.Model):
    _inherit = "sign.oca.template"

    time_off_type_id = fields.Many2one(
        "hr.leave.type",
        string="Time Off Type",
        help="Restrict this template to a specific time off type.",
    )