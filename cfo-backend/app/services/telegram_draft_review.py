from app.models.draft_transaction import DraftTransaction


def draft_review_message(
    draft: DraftTransaction, vendor_name: str | None = None
) -> tuple[str, dict]:
    text = (
        "Here’s the current draft:\n"
        f"Vendor: {vendor_name or 'Not selected'}\n"
        f"Amount: {draft.currency} {draft.amount}\n"
        f"Date: {draft.transaction_date}\n"
        f"Type: {draft.type}\n"
        f"Description: {draft.description.removeprefix('[AI] ')}\n"
        f"Reference: {draft.reference_number or 'Not provided'}\n\n"
        "Edit any field, then choose Done / Review."
    )
    markup = {
        "inline_keyboard": [
            [
                {
                    "text": "Edit vendor",
                    "callback_data": f"edit:vendor:{draft.id}",
                },
                {
                    "text": "Edit amount",
                    "callback_data": f"edit:amount:{draft.id}",
                },
            ],
            [
                {
                    "text": "Edit currency",
                    "callback_data": f"edit:currency:{draft.id}",
                },
                {
                    "text": "Edit date",
                    "callback_data": f"edit:date:{draft.id}",
                },
            ],
            [
                {
                    "text": "Edit description",
                    "callback_data": f"edit:description:{draft.id}",
                },
                {
                    "text": "Edit reference",
                    "callback_data": f"edit:reference:{draft.id}",
                },
            ],
            [
                {
                    "text": "Edit type",
                    "callback_data": f"edit:type:{draft.id}",
                },
            ],
            [
                {
                    "text": "✅ Done / Review",
                    "callback_data": f"confirm:{draft.id}",
                },
                {
                    "text": "Cancel edit",
                    "callback_data": f"edit_cancel:{draft.id}",
                },
            ],
        ]
    }
    return text, markup
