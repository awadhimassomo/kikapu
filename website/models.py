from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

# Create your models here.

class WaitlistEntry(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(default=timezone.now)
    is_contacted = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Waitlist Entry'
        verbose_name_plural = 'Waitlist Entries'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} <{self.email}>"


@receiver(post_save, sender=WaitlistEntry)
def send_waitlist_notification(sender, instance, created, **kwargs):
    """Send email notification when a new user joins the waitlist"""
    if created:
        subject = f'New Waitlist Sign-up: {instance.name}'
        message = f'''
Someone new has joined the KIKAPU App waitlist!

Name: {instance.name}
Email: {instance.email}
Phone: {instance.phone}
Sign-up Date: {instance.created_at.strftime('%Y-%m-%d %H:%M:%S')}

---
This is an automated message from the KIKAPU Waitlist System.
'''
        
        # Using a direct email rather than from settings to ensure delivery
        recipient_email = 'athimassomo@gmail.com'
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [recipient_email],
                fail_silently=False,
            )
        except Exception as e:
            # Log the error but don't crash the save process
            print(f"Error sending waitlist notification email: {e}")
