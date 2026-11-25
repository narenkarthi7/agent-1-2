from django.db import models


class Document(models.Model):            # one uploaded resume
    name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class Chunk(models.Model):               # small piece of a resume (for searching)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    text = models.TextField()


class ChatMessage(models.Model):         # every question and answer is saved
    role = models.CharField(max_length=10)             # "user" or "assistant"
    text = models.TextField()
    tool = models.CharField(max_length=20, blank=True)  # weather / document / web
    extra = models.JSONField(null=True, blank=True)     # table + chart data, links
    created_at = models.DateTimeField(auto_now_add=True)
