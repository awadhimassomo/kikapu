from django.db import models
from django.utils import timezone
from django.conf import settings

class CTAFormSubmission(models.Model):
    """Model to track Call-to-Action form submissions"""
    FORM_TYPES = [
        ('pitch', 'Pitch Meeting Request'),
        ('investor', 'Investor Pack Request'),
        ('partnership', 'Partnership Request'),
        ('development', 'Development Partnership Inquiry'),
    ]
    
    form_type = models.CharField(max_length=20, choices=FORM_TYPES)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    organization = models.CharField(max_length=255, blank=True, null=True)
    company = models.CharField(max_length=255, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    is_processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(blank=True, null=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_submissions'
    )
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'CTA Form Submission'
        verbose_name_plural = 'CTA Form Submissions'
    
    def __str__(self):
        return f"{self.get_form_type_display()} - {self.name} ({self.submitted_at.strftime('%Y-%m-%d %H:%M')})"
    
    def mark_processed(self, user, notes=None):
        """Mark this submission as processed"""
        self.is_processed = True
        self.processed_at = timezone.now()
        self.processed_by = user
        if notes:
            self.notes = notes
        self.save()
