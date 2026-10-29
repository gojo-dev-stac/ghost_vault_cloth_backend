from django.conf import settings
from django.core.mail import send_mail


def send_reply_email(complaint) -> None:
    send_mail(
        subject=f"Re: {complaint.subject}",
        message=(
            f"Hi {complaint.name},\n\n{complaint.admin_reply}\n\n"
            "— GHOST\n\n"
            f"Your original message:\n> " + complaint.message.replace("\n", "\n> ")
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[complaint.email],
        fail_silently=True,  # the reply is saved and visible in-app even if email fails
    )
