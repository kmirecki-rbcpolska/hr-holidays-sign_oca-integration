from odoo import models


class SignOcaRequestSigner(models.Model):
    _inherit = "sign.oca.request.signer"

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
