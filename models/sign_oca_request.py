from odoo import fields, models


class SignOcaRequest(models.Model):
    _inherit = "sign.oca.request"

    time_off_start_date = fields.Date(string="Time Off Start Date", readonly=True)
    time_off_end_date = fields.Date(string="Time Off End Date", readonly=True)


class SignOcaRequestSigner(models.Model):
    _inherit = "sign.oca.request.signer"

    def get_info(self, access_token=False):
        info = super().get_info(access_token=access_token)
        leave = self.request_id.record_ref
        if leave and leave._name == "hr.leave":
            info["partner"].update(
                {
                    "time_off_start_date": fields.Date.to_string(
                        leave.request_date_from
                    )
                    if leave.request_date_from
                    else False,
                    "time_off_end_date": fields.Date.to_string(
                        leave.request_date_to
                    )
                    if leave.request_date_to
                    else False,
                }
            )
        return info

    def action_sign(self, items, access_token=False, latitude=False, longitude=False):
        result = super().action_sign(
            items,
            access_token=access_token,
            latitude=latitude,
            longitude=longitude,
        )
        request = self.request_id.sudo()
        leave = request.record_ref
        if leave and leave._name == "hr.leave":
            leave._sync_sign_request_attachment()
            if request.state == "2_signed":
                leave._send_signed_document_copy(self.partner_id)
        return result
