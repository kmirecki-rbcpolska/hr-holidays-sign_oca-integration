from odoo import models


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def unlink(self):
        # Before unlinking, find any hr.leave records that reference these
        # attachments as their sign_request_attachment_id and clear both
        # sign_request_attachment_id and sign_request_id so the
        # "Sign and attach" button reappears on the form view.
        leaves = self.env["hr.leave"].sudo().search(
            [("sign_request_attachment_id", "in", self.ids)]
        )
        result = super().unlink()
        if leaves:
            leaves.sudo().write(
                {
                    "sign_request_attachment_id": False,
                    "sign_request_id": False,
                }
            )
            # Return action to refresh the form view
            return {
                "type": "ir.actions.client",
                "tag": "reload",
            }
        return result
