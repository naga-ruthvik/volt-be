from rest_framework import serializers

from .models import Activity, GenerationRequest, PlatformAccount, UserMetrics


class PlatformListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformAccount
        fields = ["id", "platform", "username"]


class PlatformCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformAccount
        fields = ["platform", "username"]

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if (
            user
            and PlatformAccount.objects.filter(
                user=user, platform=attrs["platform"]
            ).exists()
        ):
            raise serializers.ValidationError(
                {"non_field_errors": ["Platform already exists for this user."]}
            )
        return attrs


class PlatformUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformAccount
        fields = ["username"]


class GenerateRequestsCreateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")

    class Meta:
        model = GenerationRequest
        fields = ["username"]


class ActivityListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ["id", "platform", "activity_date", "activity_count", "metadata"]


class GenerationMetricsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationRequest
        fields = [
            "id",
            "created_at",
            "status",
            "gen_active_days",
            "gen_longest_streak",
            "gen_total_activities",
        ]


class UserMetricsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserMetrics
        fields = [
            "total_active_days",
            "current_streak",
            "longest_streak",
            "total_activities",
            "total_questions_solved",
            "easy_questions_solved",
            "medium_questions_solved",
            "hard_questions_solved",
            "total_contests",
            "updated_at",
        ]


class UserPlatformMetadataSerializer(serializers.Serializer):
    platforms = serializers.DictField(
        child=serializers.JSONField(),
        read_only=True,
    )
