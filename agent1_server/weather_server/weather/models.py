from django.db import models


class ChatMessage(models.Model):
    role = models.CharField(max_length=10)          # "user" / "assistant"
    text = models.TextField()
    tool = models.CharField(max_length=20, blank=True)
    extra = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
