from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrLeaveSignRequestWizard(models.TransientModel):
    _name = "hr.leave.sign.request.wizard"
    _description = "Create a sign request for a leave"

    leave_id = fields.Many2one("hr.leave", required=True, readonly=True)
    available_manager_partner_ids = fields.Many2many(
        "res.partner", compute="_compute_available_manager_partner_ids"
    )
    template_id = fields.Many2one(
        "sign.oca.template",
        required=True,
        domain="[('model', '=', 'hr.leave'), ('active', '=', True)]",
    )
    manager_partner_id = fields.Many2one(
        "res.partner",
        string="Manager",
        required=True,
        domain="[('id', 'in', available_manager_partner_ids)]",
    )

    @api.depends_context("uid")
    def _compute_available_manager_partner_ids(self):
        managers = self.env["hr.employee"].search(
            [("leave_manager_id", "!=", False)]
        ).mapped("leave_manager_id.partner_id")
        for wizard in self:
            wizard.available_manager_partner_ids = managers

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        leave = self.env["hr.leave"].browse(self.env.context.get("default_leave_id"))
        if leave and leave.holiday_status_id and not res.get("template_id"):
            template = self.env["sign.oca.template"].search(
                [
                    ("model", "=", "hr.leave"),
                    ("active", "=", True),
                    ("time_off_type_id", "=", leave.holiday_status_id.id),
                ],
                limit=1,
            )
            if template:
                res["template_id"] = template.id
        if leave and leave.employee_id and leave.employee_id.leave_manager_id:
            res.setdefault(
                "manager_partner_id", leave.employee_id.leave_manager_id.partner_id.id
            )
        return res

    def _get_template_roles(self):
        self.ensure_one()
        roles = self.template_id.item_ids.mapped("role_id")
        if len(roles) < 2:
            raise UserError(
                _(
                    "The selected template must contain at least two roles: employee and manager."
                )
            )
        return roles[0], roles[1]

    def action_create_request(self):
        self.ensure_one()
        employee_role, manager_role = self._get_template_roles()
        leave = self.leave_id.sudo()
        if leave.sign_request_id:
            raise UserError(_("This time off request already has a sign request."))
        if self.manager_partner_id not in self.available_manager_partner_ids:
            raise UserError(
                _("Please choose a manager from the available manager list.")
            )
        if self.template_id.time_off_type_id:
            leave.write({"holiday_status_id": self.template_id.time_off_type_id.id})
        request_vals = self.template_id._prepare_sign_oca_request_vals_from_record(
            leave
        )
        request_vals.update(
            {
                "ask_location": self.template_id.ask_location,
                "signer_ids": [
                    (
                        0,
                        0,
                        {
                            "partner_id": self.env.user.partner_id.id,
                            "role_id": employee_role.id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "partner_id": self.manager_partner_id.id,
                            "role_id": manager_role.id,
                        },
                    ),
                ],
            }
        )
        request = self.env["sign.oca.request"].sudo().create(request_vals)
        leave.write({"sign_request_id": request.id})
        request.action_send(sign_now=True)
        return request.sign()


