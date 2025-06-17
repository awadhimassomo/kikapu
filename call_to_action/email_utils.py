"""
Email utilities for sending CTA form submissions and auto-replies.
"""
import logging
from django.core.mail import send_mail, BadHeaderError, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

def send_auto_reply_email(recipient_email, context):
    """
    Send an auto-reply confirmation email to the form submitter.
    
    Args:
        recipient_email (str): Email address of the form submitter
        context (dict): Context data for the email template
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        subject = f"Thank You for Your {context.get('form_type', 'Inquiry')} - Kikapu"
        
        # Render HTML content
        html_message = render_to_string('call_to_action/email/auto_reply.html', context)
        
        # Create email
        msg = EmailMultiAlternatives(
            subject=subject,
            body=strip_tags(html_message),  # Plain text version
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@kikapu.co.tz'),
            to=[recipient_email],
            reply_to=[getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@kikapu.co.tz')]
        )
        msg.attach_alternative(html_message, "text/html")
        
        # Send email
        result = msg.send(fail_silently=False)
        
        if result == 1:
            logger.info(f"Auto-reply email sent to {recipient_email}")
            return True
        else:
            logger.error(f"Failed to send auto-reply to {recipient_email}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending auto-reply email to {recipient_email}: {str(e)}")
        return False

def send_cta_email(subject, message, from_email=None, recipient_emails=None):
    """
    Send an email for CTA form submissions to admin emails.
    
    Args:
        subject (str): Email subject
        message (str): Email message body (HTML)
        from_email (str, optional): Sender email. Defaults to settings.DEFAULT_FROM_EMAIL.
        recipient_emails (list, optional): Override default recipient emails.
    
    Returns:
        int: Number of successfully sent emails, or 0 if failed.
    """
    try:
        # Get recipients from settings if not provided
        if recipient_emails is None:
            recipient_emails = getattr(settings, 'ADMIN_EMAILS', [
                'awadhi.massomo@sotechtz.com',
                'athimassomo@gmail.com'
            ])
        
        # Ensure we have a list of recipients
        if not isinstance(recipient_emails, (list, tuple)):
            recipient_emails = [str(recipient_emails)]
        
        # Get sender email
        if from_email is None:
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@kikapu.co.tz')
        
        # Log the email attempt
        logger.info(f"Sending email to {recipient_emails} with subject: {subject}")
        
        # Send the email
        return send_mail(
            subject=subject,
            message=strip_tags(message),  # Plain text fallback
            from_email=from_email,
            recipient_list=recipient_emails,
            html_message=message,
            fail_silently=False
        )
        
    except BadHeaderError:
        logger.error("Invalid header found in email.")
        return 0
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return 0
