from rest_framework import serializers

from .models import Complaint


class ComplaintSerializer(serializers.ModelSerializer):
    class Meta:
        model = Complaint
        fields = [
            "id",
            "name",
            "email",
            "subject",
            "message",
            "admin_reply",
            "replied_at",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "admin_reply", "replied_at", "status", "created_at", "updated_at"]
        extra_kwargs = {
            "name": {"min_length": 1},
            "subject": {"min_length": 1},
            "message": {"min_length": 1},
        }


class ComplaintReplySerializer(serializers.Serializer):
    reply = serializers.CharField(max_length=5000)
    send_email = serializers.BooleanField(default=True)


class ComplaintStatusSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=Complaint.Status.choices)

    class Meta:
        model = Complaint
        fields = ["status"]
