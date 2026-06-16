from odoo import _, fields, models, api
from odoo.exceptions import UserError


class HrLeave(models.Model):
    _inherit = "hr.leave"

    sign_request_id = fields.Many2one("sign.oca.request", copy=False, readonly=True)
    sign_request_attachment_id = fields.Many2one(
        "ir.attachment", copy=False, readonly=True
    )

    is_planned = fields.Boolean(
        string="Planned Request",
        help="This request is only a plan and cannot be approved."
    )

    display_status = fields.Selection(
        selection=[
            ("planned", "Planned"),
            ("confirm", "To Approve"),
            ("validate1", "Second Approval"),
            ("validate", "Approved"),
            ("refuse", "Refused"),
            ("cancel", "Cancelled"),
            ("draft", "Draft"),
        ],
        compute="_compute_display_status",
        store=False,
    )

    display_state = fields.Char(
        compute="_compute_display_state"
    )

    @api.depends("state", "is_planned")
    def _compute_display_state(self):
        states = dict(self._fields["state"].selection)

        for leave in self:
            leave.display_state = (
                "Planned"
                if leave.is_planned
                else states.get(leave.state)
            )

    @api.depends("state", "is_planned")
    def _compute_display_status(self):
        for leave in self:
            if leave.is_planned:
                leave.display_status = "planned"
            else:
                leave.display_status = leave.state

    def action_approve(self, check_state=True):
        planned = self.filtered("is_planned")
        if planned:
            raise UserError(
                _("Planned requests cannot be approved.")
            )

        return super().action_approve(check_state=check_state)

    def action_validate(self, check_state=True):
        planned = self.filtered("is_planned")
        if planned:
            raise UserError(
                _("Planned requests cannot be validated.")
            )

        return super().action_validate(check_state=check_state)

    def action_open_sign_request_wizard(self):
        self.ensure_one()
        if not self.employee_id:
            raise UserError(
                _(
                    "Please select an employee on the time off request before starting the signing flow."
                )
            )
        if self.sign_request_id:
            current_signer = self.sign_request_id.signer_ids.filtered(
                lambda signer: signer.partner_id == self.env.user.partner_id
                and signer.is_allow_signature
            )[:1]
            if current_signer:
                return current_signer.sign()
            if self.sign_request_id.signed:
                return self.sign_request_id.get_formview_action()
            return self.sign_request_id.get_formview_action()
        return {
            "type": "ir.actions.act_window",
            "name": _("Podpisz i załącz wniosek"),
            "res_model": "hr.leave.sign.request.wizard",
            "view_mode": "form",
            "view_id": False,
            "target": "new",
            "context": {
                "default_leave_id": self.id,
                "default_manager_partner_id": (
                    self.employee_id.leave_manager_id.partner_id.id
                    if self.employee_id and self.employee_id.leave_manager_id
                    else False
                ),
            },
        }

    def _sync_sign_request_attachment(self):
        for leave in self:
            sign_request = leave.sign_request_id
            record_ref = sign_request.record_ref if sign_request else False
            if not sign_request or not record_ref or record_ref._name != "hr.leave":
                continue
            attachment_vals = {
                "name": sign_request.filename or f"{leave.display_name}.pdf",
                "datas": sign_request.data,
                "res_model": "hr.leave",
                "res_id": leave.id,
                "type": "binary",
                "mimetype": "application/pdf",
            }
            if leave.sign_request_attachment_id:
                leave.sign_request_attachment_id.sudo().write(attachment_vals)
            else:
                attachment = self.env["ir.attachment"].sudo().create(attachment_vals)
                leave.sudo().write({"sign_request_attachment_id": attachment.id})

    def _get_sign_request_redirect_action(self):
        self.ensure_one()
        sign_request = self.sign_request_id
        if not sign_request or sign_request.state != "0_sent":
            return False
        signer = sign_request.signer_id
        if not signer or not signer.is_allow_signature:
            return False
        return signer.sign()

    def write(self, vals):
        if "holiday_status_id" in vals and vals.get("sign_request_attachment_id") is not False:
            locked_leaves = self.filtered(
                lambda leave: leave.sign_request_attachment_id
                and leave.holiday_status_id.id != vals["holiday_status_id"]
            )
            if locked_leaves:
                raise UserError(
                    _(
                        "You cannot change the time off type while a signed document is attached. Remove the signed document first."
                    )
                )
        return super().write(vals)

    def action_approve(self, check_state=True):
        result = super().action_approve(check_state=check_state)
        if len(self) == 1:
            redirect = self._get_sign_request_redirect_action()
            if redirect:
                return redirect
        return result

    def action_validate(self, check_state=True):
        result = super().action_validate(check_state=check_state)
        if len(self) == 1:
            redirect = self._get_sign_request_redirect_action()
            if redirect:
                return redirect
        return result
