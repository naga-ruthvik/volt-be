import uuid

from django.db import models


# Create your models here.
class Platform(models.TextChoices):
    CODEFORCES = "codeforces", "Codeforces"
    CODECHEF = "codechef", "CodeChef"
    LEETCODE = "leetcode", "LeetCode"
    HACKERRANK = "hackerrank", "HackerRank"
    GITHUB = "github", "GitHub"


class PlatformAccount(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    platform = models.CharField(choices=Platform.choices, max_length=20)
    username = models.CharField(max_length=100)
    last_fetched = models.DateTimeField(null=True, blank=True)
    fetch_error = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.platform + " - " + self.username

    class Meta:  # noqa: DJ012
        unique_together = ("user", "platform")


class GenerationRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    last_synced_at = models.DateField(auto_now=True)
    error_message = models.TextField(null=True, blank=True)
    # TODO: MODIFY THIS TO FILE URL FIELD
    svg_cache = models.TextField(null=True, blank=True)

    # STREAK DATA
    total_active_days = models.IntegerField(default=0)
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    total_activities = models.IntegerField(default=0)

    def __str__(self):
        return f"{str(self.id)[:6]}-{self.user.username}"


class Activity(models.Model):
    id = models.AutoField(primary_key=True)
    generation_request = models.ForeignKey(
        "GenerationRequest", on_delete=models.CASCADE, related_name="activities"
    )
    platform = models.CharField(choices=Platform.choices, max_length=20)
    activity_date = models.DateField()
    activity_count = models.IntegerField(default=0)
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ("platform", "activity_date")

    def __str__(self):
        return str(self.id) + " - " + str(self.activity_date)
